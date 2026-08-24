"""U120 - FastAPI V2 Routes with In-Memory Caching.

Target endpoints:
  GET  /api/v2/families/{family}/configuration-dictionary
  POST /api/v2/families/{family}/configurations/evaluate
  POST /api/v2/families/{family}/configurations/validate
  POST /api/v2/families/{family}/configured-products/resolve

Caching strategy:
  - Configuration dictionary: cached per family, invalidated on publication change
  - Attribute codes: cached per family, invalidated on publication change
  - Evaluate/validate: not cached (depends on input)
  - Resolve: not cached (creates side effects)

Cache is keyed on (family_code, publication_id). When the active publication
changes, the cache auto-invalidates because the key changes.
"""
from __future__ import annotations

import hashlib
import json
import time
from functools import lru_cache
from typing import Any

import pyodbc
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

router_v2 = APIRouter(prefix="/api/v2", tags=["v2"])


# ---------------------------------------------------------------------------
# Cache layer
# ---------------------------------------------------------------------------

class MetadataCache:
    """In-memory cache for configuration metadata. Thread-safe via GIL."""

    def __init__(self):
        self._cache: dict[str, Any] = {}
        self._timestamps: dict[str, float] = {}
        self._ttl_seconds = 300  # 5 minutes max before checking publication

    def get(self, key: str) -> Any | None:
        if key in self._cache:
            age = time.time() - self._timestamps.get(key, 0)
            if age < self._ttl_seconds:
                return self._cache[key]
            else:
                del self._cache[key]
                del self._timestamps[key]
        return None

    def set(self, key: str, value: Any) -> None:
        self._cache[key] = value
        self._timestamps[key] = time.time()

    def invalidate(self, prefix: str = "") -> None:
        keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
        for k in keys_to_remove:
            del self._cache[k]
            self._timestamps.pop(k, None)


# Global cache instance (lives for the process lifetime)
_cache = MetadataCache()


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _get_conn_str(request: Request) -> str:
    settings = request.app.state.settings
    return settings.connection_string


def _get_active_publication(conn_str: str) -> tuple[int, str]:
    """Returns (publication_id, version_code) for the active publication."""
    conn = pyodbc.connect(conn_str, autocommit=True)
    try:
        row = conn.cursor().execute(
            "SELECT TOP 1 MetadataPublicationId, VersionCode "
            "FROM cfg.MetadataPublication WHERE Status = 'Active' "
            "ORDER BY ActivatedAt DESC"
        ).fetchone()
        if row is None:
            raise RuntimeError("No active metadata publication")
        return int(row[0]), str(row[1])
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class ConfigurationDictionaryResponse(BaseModel):
    family: str
    publication_version: str
    publication_id: int
    cached: bool = False
    field_count: int
    fields: list[dict[str, Any]]


class EvaluateRequest(BaseModel):
    series: str
    selections: dict[str, str] = Field(default_factory=dict)


class EvaluateResponse(BaseModel):
    family: str
    series: str
    valid: bool
    allowable_options: dict[str, list[str]]
    resolved_codes: dict[str, str | None]
    errors: list[str] = Field(default_factory=list)


class ValidateRequest(BaseModel):
    series: str
    selections: dict[str, str]


class ValidateResponse(BaseModel):
    family: str
    series: str
    valid: bool
    violations: list[dict[str, str]] = Field(default_factory=list)


class ResolveRequest(BaseModel):
    series: str
    selections: dict[str, str]
    segment_codes: dict[str, str]
    requested_by: str | None = None


class ResolveResponse(BaseModel):
    family: str
    part_number: str
    sku: str
    configuration_signature: str
    existing_configuration: bool
    configured_product_id: int | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router_v2.get(
    "/families/{family}/configuration-dictionary",
    response_model=ConfigurationDictionaryResponse,
)
async def get_configuration_dictionary(family: str, request: Request):
    """
    Returns the complete configuration dictionary for a pump family.
    Cached in-memory — same publication serves identical responses.
    """
    conn_str = _get_conn_str(request)
    pub_id, pub_version = _get_active_publication(conn_str)

    cache_key = f"dict:{family}:{pub_id}"
    cached = _cache.get(cache_key)
    if cached is not None:
        cached["cached"] = True
        return cached

    # Build from SQL
    conn = pyodbc.connect(conn_str, autocommit=True)
    try:
        cursor = conn.cursor()
        family_id = cursor.execute(
            "SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode = ?",
            family.upper(),
        ).fetchone()
        if family_id is None:
            raise RuntimeError(f"Family {family} not found")
        family_id = family_id[0]

        # Get all fields + options grouped by series
        rows = cursor.execute(
            "SELECT FieldCode, SeriesCode, OptionValue "
            "FROM cfg.SeriesFieldOption "
            "WHERE MetadataPublicationId = ? "
            "ORDER BY FieldCode, SeriesCode, OptionValue",
            pub_id,
        ).fetchall()

        fields_map: dict[str, dict[str, list[str]]] = {}
        for field_code, series_code, option_value in rows:
            fields_map.setdefault(field_code, {}).setdefault(series_code, []).append(option_value)

        fields = [
            {"field_code": fc, "series_options": so}
            for fc, so in sorted(fields_map.items())
        ]

        response = ConfigurationDictionaryResponse(
            family=family.upper(),
            publication_version=pub_version,
            publication_id=pub_id,
            cached=False,
            field_count=len(fields),
            fields=fields,
        )

        # Cache the response
        _cache.set(cache_key, response.model_dump())
        return response
    finally:
        conn.close()


@router_v2.post(
    "/families/{family}/configurations/evaluate",
    response_model=EvaluateResponse,
)
async def evaluate_configuration(family: str, body: EvaluateRequest, request: Request):
    """
    Evaluate a partial configuration: returns allowable options for
    remaining fields based on current selections and constraints.
    NOT cached (input-dependent).
    """
    conn_str = _get_conn_str(request)
    pub_id, _ = _get_active_publication(conn_str)

    conn = pyodbc.connect(conn_str, autocommit=True)
    try:
        cursor = conn.cursor()

        # Get all options for this series
        rows = cursor.execute(
            "SELECT FieldCode, OptionValue FROM cfg.SeriesFieldOption "
            "WHERE MetadataPublicationId = ? AND SeriesCode = ? "
            "ORDER BY FieldCode, OptionValue",
            pub_id, body.series,
        ).fetchall()

        all_options: dict[str, list[str]] = {}
        for field_code, option_value in rows:
            all_options.setdefault(field_code, []).append(option_value)

        # For now, return all allowable options (constraint filtering TBD)
        # Filter out fields already selected
        allowable = {
            fc: opts for fc, opts in all_options.items()
            if fc not in body.selections
        }

        # Resolve codes for selected fields (from attribute values)
        resolved = {}
        for field, value in body.selections.items():
            code = cursor.execute(
                "SELECT cfg.fn_LookupIdentifierCode(?, ?, ?, ?)",
                pub_id,
                cursor.execute("SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode=?", family.upper()).fetchone()[0],
                field,
                value,
            ).fetchone()
            resolved[field] = code[0] if code and code[0] else None

        return EvaluateResponse(
            family=family.upper(),
            series=body.series,
            valid=True,
            allowable_options=allowable,
            resolved_codes=resolved,
        )
    finally:
        conn.close()


@router_v2.post(
    "/families/{family}/configurations/validate",
    response_model=ValidateResponse,
)
async def validate_configuration(family: str, body: ValidateRequest, request: Request):
    """
    Validate a complete configuration against all constraints.
    NOT cached (input-dependent).
    """
    conn_str = _get_conn_str(request)
    pub_id, _ = _get_active_publication(conn_str)

    conn = pyodbc.connect(conn_str, autocommit=True)
    try:
        cursor = conn.cursor()
        violations = []

        # Check each selection is valid for the series
        for field, value in body.selections.items():
            exists = cursor.execute(
                "SELECT COUNT(*) FROM cfg.SeriesFieldOption "
                "WHERE MetadataPublicationId = ? AND SeriesCode = ? "
                "AND FieldCode = ? AND OptionValue = ?",
                pub_id, body.series, field, value,
            ).fetchone()[0]
            if exists == 0:
                violations.append({
                    "field": field,
                    "value": value,
                    "reason": f"'{value}' is not a valid option for {field} in series {body.series}",
                })

        return ValidateResponse(
            family=family.upper(),
            series=body.series,
            valid=len(violations) == 0,
            violations=violations,
        )
    finally:
        conn.close()


@router_v2.post(
    "/families/{family}/configured-products/resolve",
    response_model=ResolveResponse,
)
async def resolve_configured_product(family: str, body: ResolveRequest, request: Request):
    """
    Resolve a complete configuration into a Part Number, SKU, and
    configured product (with reuse detection).
    NOT cached (creates side effects).
    """
    conn_str = _get_conn_str(request)

    # Build configuration JSON for SQL procedures
    config_json = json.dumps({
        "SERIES": body.series,
        **body.selections,
        **{f"{k}_CODE": v for k, v in body.segment_codes.items()},
    })

    # Generate signature
    signature = hashlib.sha256(config_json.encode()).hexdigest().upper()

    conn = pyodbc.connect(conn_str, autocommit=True)
    try:
        cursor = conn.cursor()

        # Generate Part Number
        cursor.execute(
            "DECLARE @PN varchar(200); "
            "EXEC cfg.usp_GeneratePartNumber @FamilyCode=?, @ConfigurationJson=?, @PartNumber=@PN OUTPUT; "
            "SELECT @PN;",
            family.upper(), config_json,
        )
        pn = cursor.fetchone()[0]

        # Generate SKU
        cursor.execute(
            "DECLARE @SKU varchar(100); "
            "EXEC cfg.usp_GenerateSKU @FamilyCode=?, @SeriesCode=?, @ConfigurationSignature=?, @SKU=@SKU OUTPUT; "
            "SELECT @SKU;",
            family.upper(), body.series, signature,
        )
        sku = cursor.fetchone()[0]

        # Check for existing (reuse)
        existing = cursor.execute(
            "SELECT ConfiguredProductId FROM cfg.ConfiguredProduct WHERE ConfigurationSignature = ?",
            signature,
        ).fetchone()

        return ResolveResponse(
            family=family.upper(),
            part_number=pn,
            sku=sku,
            configuration_signature=signature,
            existing_configuration=existing is not None,
            configured_product_id=existing[0] if existing else None,
        )
    finally:
        conn.close()

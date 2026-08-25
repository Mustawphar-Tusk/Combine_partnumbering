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
    segment_codes: dict[str, str] = Field(default_factory=dict)
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
    Evaluate a configuration state: given the current selections, return
    ONLY the allowable options for every remaining field.

    This is the primary interaction endpoint for both Excel and React:
    
    EXCEL FLOW:
      1. User changes a cell (e.g., selects Series = 1500)
      2. VBA collects all current cell values as selections dict
      3. VBA calls POST /evaluate with {series, selections}
      4. Response contains allowable_options for every unfilled field
      5. VBA writes allowable options into data-validation lists for remaining cells
    
    REACT FLOW:
      1. User selects a value from a dropdown (e.g., Series = 1500)
      2. React collects current form state as selections dict
      3. React calls POST /evaluate with {series, selections}
      4. Response contains allowable_options for every unfilled dropdown
      5. React re-renders remaining dropdowns with only valid choices
    
    BOTH CLIENTS GET IDENTICAL RESPONSES. The API is client-agnostic.
    
    Constraint enforcement:
      - Only options valid for the selected series are returned
      - If a selection constrains another field (via FieldOptionDependency),
        the constrained field's options are filtered accordingly
      - Fields already selected are excluded from allowable_options
      - resolved_codes maps each selection to its Part Number segment code
    
    NOT cached (input-dependent).
    """
    conn_str = _get_conn_str(request)
    pub_id, _ = _get_active_publication(conn_str)

    conn = pyodbc.connect(conn_str, autocommit=True)
    try:
        cursor = conn.cursor()
        family_upper = family.upper()

        family_row = cursor.execute(
            "SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode = ?",
            family_upper,
        ).fetchone()
        if family_row is None:
            raise RuntimeError(f"Family {family} not found")
        family_id = family_row[0]

        # Get ALL options for this series (searching across all publications for this family)
        rows = cursor.execute(
            "SELECT FieldCode, OptionValue FROM cfg.SeriesFieldOption "
            "WHERE MetadataPublicationId = ? AND SeriesCode = ? "
            "ORDER BY FieldCode, OptionValue",
            pub_id, body.series,
        ).fetchall()

        if not rows:
            # No options found — family may not have metadata loaded
            return EvaluateResponse(
                family=family_upper,
                series=body.series,
                valid=False,
                allowable_options={},
                resolved_codes={},
                errors=[f"No configuration options found for {family_upper} series {body.series}. Metadata may not be loaded for this family."],
            )

        all_options: dict[str, list[str]] = {}
        for field_code, option_value in rows:
            all_options.setdefault(field_code, []).append(option_value)

        # Filter out fields already selected — return only what's still chooseable
        allowable = {
            fc: opts for fc, opts in all_options.items()
            if fc.upper() not in {k.upper() for k in body.selections}
        }

        # CONSTRAINT ENFORCEMENT: Apply FeasibleConstraint rules
        # For each user selection, find constraints and remove disallowed values
        for sel_field, sel_value in body.selections.items():
            # Find the constraint field name for this SFO field
            constraint_field_row = cursor.execute(
                "SELECT ConstraintFieldName FROM cfg.ConstraintFieldMap WHERE SFOFieldCode = ?",
                sel_field.upper()
            ).fetchone()
            if not constraint_field_row:
                continue
            constraint_field = constraint_field_row[0]

            # Find all "Not Allowed" constraints where this field+value is Option1
            not_allowed_rows = cursor.execute(
                "SELECT Option2Field, Option2Value FROM cfg.FeasibleConstraint "
                "WHERE Option1Field = ? AND LOWER(Option1Value) LIKE ? AND LOWER(Allowed) LIKE '%not allowed%'",
                constraint_field, f"%{sel_value.lower()[:20]}%"
            ).fetchall()

            for target_constraint_field, not_allowed_value in not_allowed_rows:
                # Map the target constraint field back to SFO field code
                target_sfo_row = cursor.execute(
                    "SELECT SFOFieldCode FROM cfg.ConstraintFieldMap WHERE ConstraintFieldName = ?",
                    target_constraint_field
                ).fetchone()
                if not target_sfo_row:
                    continue
                target_sfo_field = target_sfo_row[0]

                # Remove the not-allowed value from allowable options
                if target_sfo_field in allowable:
                    original_count = len(allowable[target_sfo_field])
                    allowable[target_sfo_field] = [
                        v for v in allowable[target_sfo_field]
                        if not_allowed_value.lower().strip() not in v.lower()
                    ]

        # Resolve identifier codes for already-selected fields
        resolved = {}
        for field, value in body.selections.items():
            code_row = cursor.execute(
                "SELECT cfg.fn_LookupIdentifierCode(?, ?, ?, ?)",
                pub_id, family_id, field.upper(), value,
            ).fetchone()
            resolved[field] = code_row[0] if code_row and code_row[0] else None

        return EvaluateResponse(
            family=family_upper,
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
)
async def resolve_configured_product(family: str, body: ResolveRequest, request: Request):
    """
    Resolve a complete configuration into a Part Number, SKU, and
    configured product (with reuse detection). Also returns pricing.
    NOT cached (creates side effects).
    """
    conn_str = _get_conn_str(request)

    # Build configuration JSON for SQL procedures
    config_json = json.dumps({
        **body.selections,
        **{f"{k}_CODE": v for k, v in body.segment_codes.items()},
    })

    # Generate signature
    signature = hashlib.sha256(config_json.encode()).hexdigest().upper()

    conn = pyodbc.connect(conn_str, autocommit=True)
    try:
        cursor = conn.cursor()
        pub_id, _ = _get_active_publication(conn_str)
        family_upper = family.upper()

        family_row = cursor.execute(
            "SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode = ?", family_upper
        ).fetchone()
        if family_row is None:
            raise RuntimeError(f"Family {family} not found")
        family_id = family_row[0]

        # Build Part Number from resolved attribute codes
        brand = "F" if family_upper == "FYBROC" else "D"

        # Look up each code
        def lookup(field, value):
            if not value:
                return None
            row = cursor.execute(
                "SELECT cfg.fn_LookupIdentifierCode(?, ?, ?, ?)",
                pub_id, family_id, field, value
            ).fetchone()
            return row[0] if row and row[0] else None

        series_val = body.selections.get("SERIES", body.series)
        flange_val = body.selections.get("FLANGE_TYPE", "")
        
        # Map FLANGE_TYPE option values to the short codes used in SERIES AttributeValue
        flange_map = {"ansi flange": "ANSI", "din/iso flange": "Din", "jis flange": "JIS", "ansi": "ANSI", "din": "Din", "jis": "JIS"}
        flange_short = flange_map.get(flange_val.lower(), "ANSI") if flange_val else "ANSI"
        
        series_key = f"{series_val} ({flange_short})"
        series_code = lookup("SERIES", series_key) or lookup("SERIES", series_val) or "?"

        size_code = lookup("SIZE", body.selections.get("ALT_SIZE", body.selections.get("SIZE", ""))) or "?"
        material_code = lookup("PUMP_MATERIAL", body.selections.get("PUMP_MATERIAL", "")) or "?"
        trim_code = lookup("IMPELLER_TRIM", body.selections.get("IMPELLER_TRIM", "")) or "??"

        # Composite segment codes — build exact combination key and match
        # The combination key = all field values joined by '|' in fixed order
        # Values include '*' suffix for standard/default values
        
        PUMP_OPTIONS_FIELDS = [
            "CASING_DRAINS", "SUCTION_DISCHARGE", "SHAFT_MATERIAL", "IMPELLER_SLEEVE",
            "CASING_HARDWARE", "PUMP_ELASTOMERS", "BEARING_OPTION", "POWER_FRAME_HARDWARE",
            "GLAND_HARDWARE", "FLUSH", "CYCLONE_SEPARATOR", "DYNAMIC_IMPELLER",
        ]
        # SFO field code -> combo field code mapping (some differ)
        SFO_TO_COMBO_FIELD = {
            "CASING_DRAINS": "CASING_DRAINS",
            "SUCTION_DISCHARGE_TAPS": "SUCTION_DISCHARGE",
            "SHAFT_MATERIAL": "SHAFT_MATERIAL",
            "SLEEVE": "IMPELLER_SLEEVE",
            "CASING_HARDWARE": "CASING_HARDWARE",
            "PUMP_ELASTOMERS": "PUMP_ELASTOMERS",
            "BEARING_OPTION": "BEARING_OPTION",
            "POWER_FRAME_HARDWARE": "POWER_FRAME_HARDWARE",
            "GLAND_HARDWARE": "GLAND_HARDWARE",
            "FLUSH": "FLUSH",
            "CYCLONE_SEPERATOR": "CYCLONE_SEPARATOR",
            "IMPELLER_BALANCE": "DYNAMIC_IMPELLER",
        }
        
        def translate_to_combo_with_star(field_code, sfo_value):
            """Translate SFO value to combo value (with * if it's the standard/default)."""
            if not sfo_value:
                return None
            combo_field = SFO_TO_COMBO_FIELD.get(field_code, field_code)
            row = cursor.execute(
                "SELECT ComboValue FROM cfg.VocabularyMap WHERE FieldCode = ? AND LOWER(SFOValue) = ?",
                combo_field, sfo_value.lower().strip()
            ).fetchone()
            return row[0] if row else None
        
        def lookup_segment_by_key(segment_code, field_order, sfo_field_map):
            """Build combination key from translated values and search."""
            # For fields the user didn't select, we can't build the full key
            # Fall back to LIKE search with available values
            translated_vals = []
            for combo_field in field_order:
                # Find which SFO field maps to this combo field
                sfo_field = None
                for sf, cf in SFO_TO_COMBO_FIELD.items():
                    if cf == combo_field:
                        sfo_field = sf
                        break
                
                sfo_val = body.selections.get(sfo_field, "") if sfo_field else ""
                if sfo_val:
                    combo_val = translate_to_combo_with_star(sfo_field, sfo_val)
                    if combo_val:
                        translated_vals.append(combo_val.lower())
            
            if not translated_vals:
                return None
            
            # Use LIKE with translated values (most reliable approach for partial selections)
            conditions = ["LOWER(SelectionsJson) LIKE ?"] * min(len(translated_vals), 4)
            params = [segment_code] + [f"%{v}%" for v in translated_vals[:4]]
            
            where = " AND ".join(conditions)
            sql = f"SELECT TOP 1 SegmentValue FROM cfg.vw_SegmentCombinationLookup WHERE SegmentCode = ? AND {where}"
            try:
                row = cursor.execute(sql, *params).fetchone()
                return row[0] if row else None
            except:
                return None

        # PUMP_OPTIONS lookup - use vertical table for vertical series
        VERTICAL_SERIES = {"5500", "5530", "6000", "7500", "7530", "8500"}
        is_vertical = body.series in VERTICAL_SERIES
        
        if is_vertical:
            pump_opts = lookup_segment_by_key("PUMP_OPTIONS_VERTICAL", PUMP_OPTIONS_FIELDS, SFO_TO_COMBO_FIELD) or body.segment_codes.get("PUMP_OPTIONS", "????")
        else:
            pump_opts = lookup_segment_by_key("PUMP_OPTIONS", PUMP_OPTIONS_FIELDS, SFO_TO_COMBO_FIELD) or body.segment_codes.get("PUMP_OPTIONS", "????")

        # SEAL_ASSEMBLY lookup
        # Seal Mfg code from VocabularyMap (S/F/J/C)
        seal_mfg_val = body.selections.get("SEAL_MFG", "")
        if seal_mfg_val:
            mfg_row = cursor.execute(
                "SELECT SFOValue FROM cfg.VocabularyMap WHERE FieldCode='SEAL_MFG' AND LOWER(ComboValue)=?",
                seal_mfg_val.lower().strip()
            ).fetchone()
            seal_mfg = mfg_row[0] if mfg_row else "S"
        else:
            seal_mfg = body.segment_codes.get("SEAL_MFG", "S")
        
        # Seal Assembly hex
        seal_option_val = body.selections.get("SEAL_OPTION", "")
        seal_type_val = body.selections.get("SEAL_TYPE", "")
        seal_assy = "??"
        
        if seal_option_val and ("noseal" in seal_option_val.lower() or "customer" in seal_option_val.lower()):
            # NoSeal/Customer - search by option alone
            t_opt = translate_to_combo_with_star("SEAL_OPTION", seal_option_val)
            if t_opt:
                try:
                    row = cursor.execute("SELECT TOP 1 SegmentValue FROM cfg.vw_SegmentCombinationLookup WHERE SegmentCode='SEAL_ASSEMBLY' AND LOWER(SelectionsJson) LIKE ?", f"%{t_opt.lower()}%").fetchone()
                    if row: seal_assy = row[0]
                except: pass
        elif seal_type_val:
            # Has seal type - try option+type first, fallback to type alone
            t_opt = translate_to_combo_with_star("SEAL_OPTION", seal_option_val) if seal_option_val else None
            t_type = translate_to_combo_with_star("SEAL_TYPE", seal_type_val)
            
            if t_opt and t_type:
                try:
                    row = cursor.execute("SELECT TOP 1 SegmentValue FROM cfg.vw_SegmentCombinationLookup WHERE SegmentCode='SEAL_ASSEMBLY' AND LOWER(SelectionsJson) LIKE ? AND LOWER(SelectionsJson) LIKE ?", f"%{t_opt.lower()}%", f"%{t_type.lower()}%").fetchone()
                    if row: seal_assy = row[0]
                except: pass
            
            # Fallback: type alone
            if seal_assy == "??" and t_type:
                try:
                    row = cursor.execute("SELECT TOP 1 SegmentValue FROM cfg.vw_SegmentCombinationLookup WHERE SegmentCode='SEAL_ASSEMBLY' AND LOWER(SelectionsJson) LIKE ?", f"%{t_type.lower()}%").fetchone()
                    if row: seal_assy = row[0]
                except: pass

        # OPTIONS lookup
        opt_keywords = []
        for sfo_f in ["COUPLING_OPTION", "BASEPLATE_OPTION"]:
            v = body.selections.get(sfo_f, "")
            if v:
                t = translate_to_combo_with_star(sfo_f, v)
                if t:
                    opt_keywords.append(t.lower())
        if opt_keywords:
            conditions = " AND ".join(["LOWER(SelectionsJson) LIKE ?"] * len(opt_keywords))
            params = ["OPTIONS"] + [f"%{k}%" for k in opt_keywords]
            try:
                row = cursor.execute(f"SELECT TOP 1 SegmentValue FROM cfg.vw_SegmentCombinationLookup WHERE SegmentCode = ? AND {conditions}", *params).fetchone()
                options_code = row[0] if row else "??"
            except:
                options_code = "??"
        else:
            options_code = body.segment_codes.get("OPTIONS", "??")

        # MOTOR_ASSEMBLY lookup
        motor_opt = body.selections.get("MOTOR_OPTION", "")
        if motor_opt:
            t_motor = translate_to_combo_with_star("MOTOR_OPTION", motor_opt)
            if t_motor:
                try:
                    row = cursor.execute("SELECT TOP 1 SegmentValue FROM cfg.vw_SegmentCombinationLookup WHERE SegmentCode = ? AND LOWER(SelectionsJson) LIKE ?", "MOTOR_ASSEMBLY", f"%{t_motor.lower()}%").fetchone()
                    motor_assy = row[0] if row else "???"
                except:
                    motor_assy = "???"
            else:
                motor_assy = "???"
        else:
            motor_assy = body.segment_codes.get("MOTOR_ASSY", "???")
        
        motor_mods = body.segment_codes.get("MOTOR_MODS", "XXX")
        testing = body.segment_codes.get("TESTING", "00")

        # Frame size from selection
        import re
        frame_val = body.selections.get("FRAME_SIZE", "")
        if frame_val:
            digits = re.sub(r'[^0-9]', '', frame_val)
            frame_size = digits[:2] if len(digits) >= 2 else "??"
        else:
            frame_size = body.segment_codes.get("FRAME_SIZE", "??")

        pn = f"{brand}{series_code}{size_code}{material_code}{trim_code}-{pump_opts}-{seal_mfg}{seal_assy}-{options_code}-{frame_size}{motor_assy}-{motor_mods}-{testing}"

        # Debug info for segment resolution
        segment_debug = {
            "brand": brand,
            "series_code": series_code,
            "size_code": size_code,
            "material_code": material_code,
            "trim_code": trim_code,
            "pump_options": pump_opts,
            "seal_mfg": seal_mfg,
            "seal_assy": seal_assy,
            "options": options_code,
            "frame_size": frame_size,
            "motor_assy": motor_assy,
            "motor_mods": motor_mods,
            "testing": testing,
            "failed_segments": [k for k, v in {
                "seal_assy": seal_assy, "motor_assy": motor_assy,
                "pump_options": pump_opts, "options": options_code,
            }.items() if "?" in str(v)],
        }

        # Generate SKU
        cursor.execute(
            "DECLARE @SKU varchar(100); "
            "EXEC cfg.usp_GenerateSKU @FamilyCode=?, @SeriesCode=?, @ConfigurationSignature=?, @SKU=@SKU OUTPUT; "
            "SELECT @SKU;",
            family_upper, body.series, signature,
        )
        sku = cursor.fetchone()[0]

        # Check for existing (reuse)
        existing = cursor.execute(
            "SELECT ConfiguredProductId FROM cfg.ConfiguredProduct WHERE ConfigurationSignature = ?",
            signature,
        ).fetchone()

        # Pricing lookup
        pricing = []
        size_val = body.selections.get("ALT_SIZE") or body.selections.get("SIZE") or ""
        size_upper = size_val.upper()
        material_display = body.selections.get("PUMP_MATERIAL", "").lower()

        # Normalize material for matching: 'vr-1' should match 'VR-1 (Standard)'
        # Build a LIKE pattern from the material selection
        mat_pattern = material_display.replace(" ", "%")
        if mat_pattern and not mat_pattern.endswith("%"):
            mat_pattern = f"%{mat_pattern}%"

        # Base pump price - search with series LIKE and material LIKE
        base_row = cursor.execute("""
            SELECT TOP 1 pr.Amount, pr.SourceOptionValue
            FROM price.PriceRule pr
            JOIN price.PriceBookVersion pbv ON pbv.PriceBookVersionId = pr.PriceBookVersionId AND pbv.IsCurrent = 1
            WHERE pr.ComponentCode = 'BASE_PUMP' AND pr.IsActive = 1
              AND (pr.SeriesCode = ? OR pr.SeriesCode LIKE ?)
              AND UPPER(pr.SourceSizeValue) LIKE ?
              AND LOWER(pr.SourceOptionValue) LIKE ?
            ORDER BY pr.Priority
        """, body.series, f"{body.series}%", f"{size_upper}%", mat_pattern).fetchone()

        if base_row:
            pricing.append({"component": "Base Pump", "amount": float(base_row[0]), "detail": base_row[1]})
        else:
            # Fallback: any price for this size in this series family
            base_row2 = cursor.execute("""
                SELECT TOP 1 pr.Amount, pr.SourceOptionValue
                FROM price.PriceRule pr
                JOIN price.PriceBookVersion pbv ON pbv.PriceBookVersionId = pr.PriceBookVersionId AND pbv.IsCurrent = 1
                WHERE pr.ComponentCode = 'BASE_PUMP' AND pr.IsActive = 1
                  AND (pr.SeriesCode = ? OR pr.SeriesCode LIKE ?)
                  AND UPPER(pr.SourceSizeValue) LIKE ?
                ORDER BY pr.Priority
            """, body.series, f"{body.series}%", f"{size_upper}%").fetchone()
            if base_row2:
                pricing.append({"component": "Base Pump (std material)", "amount": float(base_row2[0]), "detail": base_row2[1]})

        # Seal pricing
        seal_type = body.selections.get("SEAL_TYPE", "")
        if seal_type:
            seal_pattern = f"%{seal_type[:10]}%"
            seal_row = cursor.execute("""
                SELECT TOP 1 pr.Amount, pr.SourceOptionValue
                FROM price.PriceRule pr
                JOIN price.PriceBookVersion pbv ON pbv.PriceBookVersionId = pr.PriceBookVersionId AND pbv.IsCurrent = 1
                WHERE pr.ComponentCode = 'SEAL' AND pr.IsActive = 1
                  AND (pr.SeriesCode = ? OR pr.SeriesCode LIKE ?)
                  AND LOWER(pr.SourceOptionValue) LIKE ?
                ORDER BY pr.Priority
            """, body.series, f"{body.series}%", seal_pattern).fetchone()
            if seal_row:
                pricing.append({"component": "Seal", "amount": float(seal_row[0]), "detail": seal_row[1]})

        total = sum(p["amount"] for p in pricing)

        return {
            "family": family_upper,
            "part_number": pn,
            "sku": sku,
            "configuration_signature": signature,
            "existing_configuration": existing is not None,
            "configured_product_id": existing[0] if existing else None,
            "pricing": pricing,
            "total_price": total,
            "segment_debug": segment_debug,
        }
    finally:
        conn.close()

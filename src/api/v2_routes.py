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
import re
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


# Short-lived cache of the active publication. It changes only when a new
# metadata publication is activated (rare), so caching it avoids an extra DB
# round-trip on every request - which matters a lot when the DB is reached over
# a remote tunnel (e.g. ngrok) where each query has real network latency.
_ACTIVE_PUB_CACHE: dict[str, object] = {"value": None, "expires": 0.0}
_ACTIVE_PUB_TTL_SECONDS = 60.0


def _get_active_publication(
    conn_str: str, conn: "pyodbc.Connection | None" = None
) -> tuple[int, str]:
    """Return (publication_id, version_code) for the active publication.

    Reuses the caller's open connection when provided (avoids a second
    TCP+TLS+login handshake per request), and caches the result for a short TTL
    since the active publication rarely changes.
    """
    now = time.monotonic()
    cached = _ACTIVE_PUB_CACHE["value"]
    if cached is not None and now < float(_ACTIVE_PUB_CACHE["expires"]):
        return cached  # type: ignore[return-value]

    owns_conn = conn is None
    if owns_conn:
        conn = pyodbc.connect(conn_str, autocommit=True)
    try:
        row = conn.cursor().execute(
            "SELECT TOP 1 MetadataPublicationId, VersionCode "
            "FROM cfg.MetadataPublication WHERE Status = 'Active' "
            "ORDER BY ActivatedAt DESC"
        ).fetchone()
        if row is None:
            raise RuntimeError("No active metadata publication")
        result = (int(row[0]), str(row[1]))
        _ACTIVE_PUB_CACHE["value"] = result
        _ACTIVE_PUB_CACHE["expires"] = now + _ACTIVE_PUB_TTL_SECONDS
        return result
    finally:
        if owns_conn:
            conn.close()


# ---------------------------------------------------------------------------
# Authoritative configuration hierarchy (Fybroc)
# ---------------------------------------------------------------------------
# The engineering hierarchy from the Rev0.3 Constraints / To Do ordering.
# Configuration constraints are hierarchical: a field becomes reachable only
# after every preceding APPLICABLE field is selected. This order is the single
# server-side authority for progressive gating and reset-on-upstream-change;
# the UI consumes the server's decision rather than re-deriving it.
FYBROC_FIELD_HIERARCHY: tuple[str, ...] = (
    # Primary configuration
    "ALT_SIZE", "PUMP_MATERIAL", "FLANGE_TYPE",
    # Pump Options group (horizontal)
    "SHAFT_MATERIAL", "CASING_DRAINS", "SUCTION_DISCHARGE_TAPS", "SLEEVE",
    "PUMP_ELASTOMERS", "GLAND_HARDWARE", "FLUSH", "FLUSH_MATERIAL",
    "CYCLONE_SEPERATOR", "IMPELLER_BALANCE",
    "CASING_HARDWARE", "BEARING_OPTION", "POWER_FRAME_HARDWARE",
    # Pump Options group (vertical-specific)
    "WETTED_HARDWARE", "WETTED_HARDWARE_SELECTION",
    "FLUSH_OPTIONS", "VAPOR_SEAL", "STRAINER",
    # Seal Assembly group (in order)
    "SEAL_OPTION", "SEAL_TYPE", "SEAL_MATERIALS", "SEAL_ELASTOMERS",
    "SEAL_GUARD", "SEAL_MFG",
    # Options group
    "COUPLING_OPTION", "COUPLING_GUARD", "BASEPLATE_OPTION", "BASEPLATEHARDWARE",
    "MOUNTING_PLATE_OPTION",
    # Impeller
    "IMPELLER_TRIM", "DYNAMIC_IMPELLER",
    # Vertical-specific
    "SETTING", "SETTING/LENGTH", "LENGTH", "TAILPIPE_OPTION", "TAILPIPE_LENGTH",
    # Motor group
    "MOTOR_OPTION", "MOTOR_CONTROL", "MOTOR_HP", "MOTOR_RPM",
    "MOTOR_VOLTAGE", "MOTOR_HERTZ", "FRAME_SIZE",
    "MOTOR_ENCLOSURE", "MOTOR_EFFICIENCY", "MOTOR_MFG",
    # Testing / Other
    "PERFORMANCE_TESTING", "HYDROTEST_CERTIFICATE", "VIBRATION_TESTING",
    "SOUND_LEVEL_TESTING", "NAMEPLATE", "CUSTOMER_NAMEPLATE", "PAINT_UPGRADE",
    "SHAFT_GROUNDING", "C_FACE_ADAPTOR",
)

# Fields not in the explicit hierarchy sort after it, alphabetically, so an
# unknown/new field is still ordered deterministically (never silently first).
_HIERARCHY_INDEX = {fc: i for i, fc in enumerate(FYBROC_FIELD_HIERARCHY)}


def _hierarchy_rank(field_code: str) -> tuple[int, str]:
    fc = field_code.upper()
    return (_HIERARCHY_INDEX.get(fc, len(FYBROC_FIELD_HIERARCHY)), fc)


def _order_fields(field_codes) -> list[str]:
    """Return field codes sorted by the authoritative hierarchy."""
    return sorted(field_codes, key=_hierarchy_rank)


# Fields whose option values are numeric and must be presented in ASCENDING
# NUMERIC order (not string order, which mixes "1, 1.5, 10, 100, 15, 2, ...").
NUMERIC_OPTION_FIELDS = {"MOTOR_HP", "MOTOR_RPM", "MOTOR_HERTZ", "MOTOR_VOLTAGE"}

# DIMENSIONAL fields whose option values are compound sizes like "10x12x16"
# (suction x discharge x impeller). Plain string order mis-sorts these
# ("10x12x16" before "2x3x6" because '1' < '2'); they must sort by the tuple of
# their numeric parts so the UI shows an ascending, logical progression.
DIMENSIONAL_OPTION_FIELDS = {"ALT_SIZE"}

_DIM_SPLIT = re.compile(r"\s*x\s*", re.IGNORECASE)


def _numeric_option_key(value: str):
    """Sort key that orders numeric option strings by value, text last.

    Returns (0, number) for parseable numerics and (1, lowercased text) for
    non-numeric values, so numbers sort ascending and any stray text sorts
    after them deterministically.
    """
    try:
        return (0, float(str(value).strip()))
    except (TypeError, ValueError):
        return (1, str(value).strip().lower())


def _dimensional_option_key(value: str):
    """Sort key for compound "NxNxN" sizes by their numeric parts.

    "1x1.5x6" -> (0, (1.0, 1.5, 6.0)). Values that do not parse as all-numeric
    parts sort last as (1, lowercased text), deterministically.
    """
    parts = _DIM_SPLIT.split(str(value).strip())
    try:
        return (0, tuple(float(p) for p in parts))
    except (TypeError, ValueError):
        return (1, str(value).strip().lower())


def _sort_field_options(field_code: str, options: list[str]) -> list[str]:
    """Order a field's options for presentation.

    Numeric fields (e.g. MOTOR_HP) sort ascending by numeric value; dimensional
    fields (e.g. ALT_SIZE "10x12x16") sort ascending by their numeric parts;
    all other fields keep their existing (SQL string) order. Presentation only -
    the option data itself is unchanged.
    """
    fc = field_code.upper()
    if fc in NUMERIC_OPTION_FIELDS:
        return sorted(options, key=_numeric_option_key)
    if fc in DIMENSIONAL_OPTION_FIELDS:
        return sorted(options, key=_dimensional_option_key)
    return options


def _prune_to_prefix(
    ordered_fields: list[str],
    selections: dict[str, str],
) -> tuple[dict[str, str], set[str]]:
    """Enforce reset-on-upstream-change.

    Walk the applicable fields in hierarchy order. Keep a selection only while
    every preceding applicable field is also selected (a contiguous completed
    prefix). Once the first unselected applicable field is hit, every later
    selection is dropped - so changing/clearing an upstream step forces the
    user to re-progress from that step and cannot skip ahead.

    Returns (effective_selections, dropped_field_codes).
    """
    sel_upper = {k.upper(): v for k, v in selections.items()}
    effective: dict[str, str] = {}
    dropped: set[str] = set()
    broken = False  # becomes True at the first incomplete step
    for fc in ordered_fields:
        if broken:
            if fc in sel_upper:
                dropped.add(fc)
            continue
        if fc in sel_upper:
            effective[fc] = sel_upper[fc]
        else:
            # First incomplete applicable step: everything after is downstream.
            broken = True
    return effective, dropped


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


class FieldHierarchyState(BaseModel):
    field_code: str
    order: int
    status: str  # "selected" | "current" | "locked"


class EvaluateResponse(BaseModel):
    family: str
    series: str
    valid: bool
    allowable_options: dict[str, list[str]]
    # Field-code -> the STANDARD (STD) default option value for this series,
    # per Rev0.3 Selections. Additive; clients that ignore it are unaffected.
    # The configurator/UI should pre-select these when a field is unset.
    standard_defaults: dict[str, str] = Field(default_factory=dict)
    resolved_codes: dict[str, str | None]
    # Hierarchy enforcement (server is the authority):
    #  - ordered_fields: applicable fields in authoritative hierarchy order
    #  - hierarchy: per-field status (selected / current / locked)
    #  - current_field: the single next field the user may edit (or None if done)
    #  - effective_selections: selections after reset-on-upstream-change pruning
    #  - dropped_selections: selections removed because an upstream step changed
    ordered_fields: list[str] = Field(default_factory=list)
    hierarchy: list[FieldHierarchyState] = Field(default_factory=list)
    current_field: str | None = None
    effective_selections: dict[str, str] = Field(default_factory=dict)
    dropped_selections: list[str] = Field(default_factory=list)
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

    conn = pyodbc.connect(conn_str, autocommit=True)
    try:
        # Reuse this connection for the publication lookup (no second handshake).
        pub_id, _ = _get_active_publication(conn_str, conn)
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
            "SELECT FieldCode, OptionValue, IsStandard FROM cfg.SeriesFieldOption "
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
                standard_defaults={},
                resolved_codes={},
                errors=[f"No configuration options found for {family_upper} series {body.series}. Metadata may not be loaded for this family."],
            )

        all_options: dict[str, list[str]] = {}
        # Field-code -> STANDARD (STD) default option value for this series.
        standard_defaults: dict[str, str] = {}
        for field_code, option_value, is_standard in rows:
            all_options.setdefault(field_code, []).append(option_value)
            if is_standard:
                standard_defaults[field_code] = option_value

        # Present numeric-valued fields (MOTOR_HP, etc.) in ascending numeric
        # order rather than the SQL string order (which mixes 1, 1.5, 10, 100,
        # 15, 2, ...). Value data is unchanged - this is presentation ordering.
        for field_code in all_options:
            all_options[field_code] = _sort_field_options(
                field_code, all_options[field_code]
            )

        # HIERARCHY ENFORCEMENT (server is the authority).
        # Applicable fields for this series, in authoritative hierarchy order.
        ordered_fields = _order_fields(all_options.keys())
        # CONDITIONAL FIELD APPLICABILITY (Rev0.3 dependent fields).
        # Some fields apply only when a controlling field holds a specific value.
        # WETTED_HARDWARE_SELECTION applies ONLY when WETTED_HARDWARE ==
        # "select material". When WETTED_HARDWARE == "match shaft material" the
        # wetted hardware inherits the already-chosen Shaft Material, so there is
        # no separate material to pick - the selection field must be SKIPPED (not
        # shown as an empty dead-end step). Removing it from ordered_fields drops
        # it from the required-step walk, current-field computation, pruning, and
        # the returned field set. If WETTED_HARDWARE is not yet chosen we leave
        # the selection field in place (hierarchy gating hides it until then).
        _sel_upper_raw = {k.upper(): str(v).strip().lower()
                          for k, v in body.selections.items()}
        _wh = _sel_upper_raw.get("WETTED_HARDWARE")
        if _wh is not None and _wh != "select material":
            ordered_fields = [fc for fc in ordered_fields
                              if fc != "WETTED_HARDWARE_SELECTION"]
            all_options.pop("WETTED_HARDWARE_SELECTION", None)
        # Reset-on-upstream-change: keep only the contiguous completed prefix of
        # selections. Any selection after the first incomplete step is dropped,
        # so changing/clearing an earlier step forces re-progression and never
        # skips ahead. Constraint enforcement then runs on the effective set.
        effective_selections, dropped = _prune_to_prefix(ordered_fields, body.selections)
        selected_upper = set(effective_selections)
        # The current step = first applicable field not yet selected.
        current_field = next(
            (fc for fc in ordered_fields if fc not in selected_upper),
            None,
        )

        # Filter out fields already selected — return only what's still chooseable
        allowable = {
            fc: opts for fc, opts in all_options.items()
            if fc.upper() not in selected_upper
        }

        # FEASIBLE-CONSTRAINT ENFORCEMENT (Rev0.3 Feasible Constraints sheet).
        # cfg.FeasibleConstraint holds "Not Allowed" combinations across 2 or 3
        # fields (e.g. Alt Size + Non Sparking Coupling Guard; Casing Drains
        # Supplied + VR-1V Pump Material; Alt Size + Pump Material + Length).
        # A row's fields are its "legs". Rule: if EVERY leg except one is already
        # selected and matches (case-insensitive, exact), the remaining leg's
        # value is illegal in that context and is removed from its allowable
        # options. This handles pairs BIDIRECTIONALLY (either field selected
        # first blocks the other) and TRIPLES (two selected -> filter the third),
        # and it makes invalid options fail closed. cfg.ConstraintFieldMap bridges
        # the constraint field LABELS to SFO FieldCodes.
        #
        # Series scoping: SeriesApplicability is 'ALL_SERIES' or a series-scoped
        # marker (e.g. '5500_ONLY'). A scoped row applies only when the requested
        # series matches.

        # constraint field label -> SFO field code, and reverse
        _cfmap = cursor.execute(
            "SELECT ConstraintFieldName, SFOFieldCode FROM cfg.ConstraintFieldMap"
        ).fetchall()
        label_to_sfo = {r[0]: r[1] for r in _cfmap}

        def _series_in_scope(scope: str) -> bool:
            s = (scope or "ALL_SERIES").strip().upper()
            if s == "ALL_SERIES":
                return True
            # scoped markers embed the series code, e.g. "5500_ONLY"
            return body.series.upper() in s

        # Pull all Not-Allowed rows in one query (small table, ~4.5k rows).
        not_allowed = cursor.execute(
            "SELECT Option1Field, Option1Value, Option2Field, Option2Value, "
            "       Option3Field, Option3Value, SeriesApplicability "
            "FROM cfg.FeasibleConstraint "
            "WHERE LOWER(Allowed) = 'not allowed'"
        ).fetchall()

        # Effective selections, case-normalized by SFO field code, for matching.
        _sel_norm = {
            k.upper(): str(v).strip().lower()
            for k, v in effective_selections.items()
        }

        for (o1f, o1v, o2f, o2v, o3f, o3v, scope) in not_allowed:
            if not _series_in_scope(scope):
                continue
            # Assemble the row's legs as (sfo_field_code, value) pairs.
            legs = []
            ok = True
            for label, value in ((o1f, o1v), (o2f, o2v), (o3f, o3v)):
                if not label:
                    continue
                sfo = label_to_sfo.get(str(label).strip())
                if not sfo:
                    ok = False  # unmapped field -> skip this row safely
                    break
                legs.append((sfo.upper(), str(value).strip().lower()))
            if not ok or len(legs) < 2:
                continue

            # For each leg, treat it as the "target" and the others as "context".
            # If every context leg is selected and matches, the target value is
            # illegal -> remove it from that field's allowable options.
            for ti in range(len(legs)):
                target_field, target_value = legs[ti]
                context = [legs[i] for i in range(len(legs)) if i != ti]
                if all(_sel_norm.get(cf) == cv for cf, cv in context):
                    if target_field in allowable:
                        allowable[target_field] = [
                            v for v in allowable[target_field]
                            if str(v).strip().lower() != target_value
                        ]

        # MOTOR CONSTRAINT ENFORCEMENT (cfg.MotorConstraint — an ALLOW-LIST).
        # Unlike FeasibleConstraint (which removes "Not Allowed" values), Motor
        # Constraints list the ALLOWED pairs. When the user selects a driving
        # dimension (Alt_Size), restrict the dependent motor field (Frame Size)
        # to only the values the workbook allows for that (series-scope, size).
        # SFO field  -> MotorConstraint dimension field:
        MOTOR_DIM_FIELD = {
            "ALT_SIZE": "Alt_Size",
            "FRAME_SIZE": "F_Frame_Size",
        }
        # Which series scope does the requested series belong to?
        scope_row = cursor.execute(
            "SELECT DISTINCT SeriesScope FROM cfg.MotorConstraint "
            "WHERE MetadataPublicationId=? AND PumpFamilyId=? "
            "AND (SeriesScope = ? OR SeriesScope LIKE ?)",
            pub_id, family_id, body.series, f"%{body.series}%",
        ).fetchone()
        motor_scope = scope_row[0] if scope_row else None

        if motor_scope and "ALT_SIZE" in effective_selections:
            size_value = effective_selections.get("ALT_SIZE")
            if size_value and "FRAME_SIZE" in allowable:
                allowed_frames = cursor.execute(
                    "SELECT Dimension2Value FROM cfg.MotorConstraint "
                    "WHERE MetadataPublicationId=? AND PumpFamilyId=? AND SeriesScope=? "
                    "AND Dimension1Field='Alt_Size' AND Dimension2Field='F_Frame_Size' "
                    "AND LOWER(Dimension1Value)=LOWER(?)",
                    pub_id, family_id, motor_scope, size_value,
                ).fetchall()
                allowed_set = {r[0].strip().lower() for r in allowed_frames}
                if allowed_set:
                    allowable["FRAME_SIZE"] = [
                        v for v in allowable["FRAME_SIZE"]
                        if v.strip().lower() in allowed_set
                    ]

        # MOTOR Hp -> RPM ENFORCEMENT (Rev0.3 Combine Variables MotorHpRpm table).
        # The valid (Hp, RPM) pairs are enumerated by the composite F_MotorHpRPM
        # key (e.g. "1-1200"): 1 HP allows only 1200/1800 RPM (no 3600), while
        # 1.5 HP and up allow 1200/1800/3600. When MOTOR_HP is selected, restrict
        # MOTOR_RPM to the RPMs the workbook pairs with that Hp.
        if "MOTOR_HP" in effective_selections and "MOTOR_RPM" in allowable:
            hp_value = str(effective_selections["MOTOR_HP"]).strip()
            allowed_rpms = cursor.execute(
                "SELECT cv_rpm.ValueValue "
                "FROM cfg.CombineVariable cv_hp "
                "JOIN cfg.CombineVariable cv_rpm "
                "  ON cv_rpm.MetadataPublicationId = cv_hp.MetadataPublicationId "
                " AND cv_rpm.PumpFamilyId = cv_hp.PumpFamilyId "
                " AND cv_rpm.TableName = cv_hp.TableName "
                " AND cv_rpm.KeyValue = cv_hp.KeyValue "
                "WHERE cv_hp.MetadataPublicationId = ? AND cv_hp.PumpFamilyId = ? "
                "  AND cv_hp.TableName = 'MotorHpRpm_to_HpAndRpm' "
                "  AND cv_hp.ValueField = 'MotorHp' AND LOWER(cv_hp.ValueValue) = LOWER(?) "
                "  AND cv_rpm.ValueField = 'MotorRPM'",
                pub_id, family_id, hp_value,
            ).fetchall()
            allowed_rpm_set = {
                str(r[0]).strip().lower() for r in allowed_rpms if r[0] is not None
            }
            if allowed_rpm_set:
                allowable["MOTOR_RPM"] = [
                    v for v in allowable["MOTOR_RPM"]
                    if str(v).strip().lower() in allowed_rpm_set
                ]

        # Resolve identifier codes for the effective (pruned) selections.
        resolved = {}
        for field, value in effective_selections.items():
            code_row = cursor.execute(
                "SELECT cfg.fn_LookupIdentifierCode(?, ?, ?, ?)",
                pub_id, family_id, field.upper(), value,
            ).fetchone()
            resolved[field] = code_row[0] if code_row and code_row[0] else None

        # Expose STD default only for the CURRENT field (the one the user may
        # edit now) where the default survived constraint filtering. Downstream
        # fields are locked, so their defaults are not surfaced yet.
        exposed_defaults = {}
        if current_field and current_field in allowable:
            dv = standard_defaults.get(current_field)
            if dv and dv in allowable[current_field]:
                exposed_defaults[current_field] = dv

        # Build per-field hierarchy status:
        #   selected -> already chosen (in the effective/pruned prefix)
        #   current  -> the single next field the user may edit
        #   locked   -> a later field, gated until its predecessors are chosen
        hierarchy_state: list[FieldHierarchyState] = []
        for i, fc in enumerate(ordered_fields):
            if fc in selected_upper:
                status = "selected"
            elif fc == current_field:
                status = "current"
            else:
                status = "locked"
            hierarchy_state.append(
                FieldHierarchyState(field_code=fc, order=i, status=status)
            )

        return EvaluateResponse(
            family=family_upper,
            series=body.series,
            valid=True,
            allowable_options=allowable,
            standard_defaults=exposed_defaults,
            resolved_codes=resolved,
            ordered_fields=ordered_fields,
            hierarchy=hierarchy_state,
            current_field=current_field,
            effective_selections=effective_selections,
            dropped_selections=sorted(dropped),
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

    conn = pyodbc.connect(conn_str, autocommit=True)
    try:
        pub_id, _ = _get_active_publication(conn_str, conn)
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
        pub_id, _ = _get_active_publication(conn_str, conn)
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
                "SELECT ComboValue FROM cfg.VocabularyMap WHERE FieldCode = ? AND LOWER(SFOValue) LIKE ?",
                combo_field, f"%{sfo_value.lower().strip()}%"
            ).fetchone()
            return row[0] if row else None
        
        def lookup_segment_by_key(segment_code, field_order, sfo_field_map):
            """Look up hex code by matching SFO values directly against re-indexed SelectionsJson."""
            keywords = []
            for combo_field in field_order:
                # Find which SFO field maps to this combo field
                sfo_field = None
                for sf, cf in SFO_TO_COMBO_FIELD.items():
                    if cf == combo_field:
                        sfo_field = sf
                        break
                
                sfo_val = body.selections.get(sfo_field, "") if sfo_field else ""
                if sfo_val and len(sfo_val) > 2:
                    keywords.append(sfo_val.lower().strip())
            
            if not keywords:
                return None
            
            # Direct match — SelectionsJson is now in SFO vocabulary
            conditions = ["LOWER(SelectionsJson) LIKE ?"] * min(len(keywords), 4)
            params = [segment_code] + [f"%{kw}%" for kw in keywords[:4]]
            
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
            # Vertical combo table fields: SHAFT_MATERIAL, IMPELLER_SLEEVE, WETTED_HARDWARE,
            # PUMP_ELASTOMERS, FLUSH, FLUSH_OPTIONS, IMPELLER_BALANCE, VAPOR_PROTECTION, STRAINER
            # SFO field → vertical combo field mapping:
            VERTICAL_SFO_TO_COMBO = {
                "SHAFT_MATERIAL": "SHAFT_MATERIAL",
                "SLEEVE": "IMPELLER_SLEEVE",
                "WETTED_HARDWARE": "WETTED_HARDWARE",
                "WETTED_HARDWARE_SELECTION": "WETTED_HARDWARE",
                "PUMP_ELASTOMERS": "PUMP_ELASTOMERS",
                "FLUSH": "FLUSH",
                "FLUSH_OPTIONS": "FLUSH_OPTIONS",
                "IMPELLER_BALANCE": "IMPELLER_BALANCE",
                "VAPOR_SEAL": "VAPOR_PROTECTION",
                "STRAINER": "STRAINER",
            }
            
            # Collect keywords from vertical SFO fields
            vert_keywords = []
            for sfo_field, combo_field in VERTICAL_SFO_TO_COMBO.items():
                sfo_val = body.selections.get(sfo_field, "")
                if sfo_val and len(sfo_val) > 2:
                    vert_keywords.append(sfo_val.lower().strip())
            
            if vert_keywords:
                # Progressive matching for vertical pump options
                pump_opts = None
                for n in range(len(vert_keywords), 0, -1):
                    use_kw = vert_keywords[:n]
                    conditions = " AND ".join(["LOWER(SelectionsJson) LIKE ?"] * len(use_kw))
                    params = ["PUMP_OPTIONS_VERTICAL"] + [f"%{k}%" for k in use_kw]
                    try:
                        row = cursor.execute(
                            f"SELECT TOP 1 SegmentValue FROM cfg.vw_SegmentCombinationLookup "
                            f"WHERE SegmentCode=? AND {conditions}",
                            *params
                        ).fetchone()
                        if row:
                            pump_opts = row[0]
                            break
                    except:
                        continue
                pump_opts = pump_opts or "0000"  # Default: standard vertical pump options
            else:
                # No vertical pump option fields available for this series — use default
                pump_opts = "0000"
        else:
            pump_opts = lookup_segment_by_key("PUMP_OPTIONS", PUMP_OPTIONS_FIELDS, SFO_TO_COMBO_FIELD) or body.segment_codes.get("PUMP_OPTIONS", "????")

        # Seal Mfg code (S/F/J/C) — still from VocabularyMap
        seal_mfg_val = body.selections.get("SEAL_MFG", "")
        if seal_mfg_val:
            mfg_row = cursor.execute(
                "SELECT SFOValue FROM cfg.VocabularyMap WHERE FieldCode='SEAL_MFG' AND LOWER(ComboValue) LIKE ?",
                f"%{seal_mfg_val.lower().strip()}%"
            ).fetchone()
            seal_mfg = mfg_row[0] if mfg_row else "S"
        else:
            seal_mfg = body.segment_codes.get("SEAL_MFG", "S")

        # Seal Assembly hex — multi-field match against re-indexed SelectionsJson
        # Combo fields: SEAL_OPTION, SEAL_TYPE, SEAL_MATERIALS, SEAL_ELASTOMERS, SEAL_GUARD
        seal_option_val = body.selections.get("SEAL_OPTION", "")
        seal_type_val = body.selections.get("SEAL_TYPE", "")
        seal_materials_val = body.selections.get("SEAL_MATERIALS", "")
        seal_elastomers_val = body.selections.get("SEAL_ELASTOMERS", "")
        seal_guard_val = body.selections.get("SEAL_GUARD", "")
        seal_assy = "??"
        
        # Check if this series even HAS seal configuration fields
        # If not, the seal segment should be a standard default (noseal)
        has_seal_fields = cursor.execute(
            "SELECT COUNT(*) FROM cfg.SeriesFieldOption "
            "WHERE MetadataPublicationId=? AND SeriesCode=? AND FieldCode IN ('SEAL_OPTION','SEAL_TYPE')",
            pub_id, body.series
        ).fetchone()[0] > 0
        
        if not has_seal_fields and not is_vertical:
            # Series has no seal configuration — use noseal default code
            # Look up the "noseal nosealgland" + "not supplied by fybroc" combo
            try:
                row = cursor.execute(
                    "SELECT TOP 1 SegmentValue FROM cfg.vw_SegmentCombinationLookup "
                    "WHERE SegmentCode='SEAL_ASSEMBLY' "
                    "AND LOWER(SelectionsJson) LIKE '%noseal nosealgland%' "
                    "AND LOWER(SelectionsJson) LIKE '%not supplied by fybroc%'"
                ).fetchone()
                seal_assy = row[0] if row else "0X"  # 0X = noseal nosealgland default
            except:
                seal_assy = "0X"
            seal_mfg = "S"  # Standard offering for no-seal
        elif not has_seal_fields and is_vertical:
            seal_assy = "N/A"  # Will be omitted from PN anyway
        else:
            # Build search keywords from all seal fields
            seal_keywords = []
            
            if seal_option_val:
                seal_opt_search = seal_option_val.lower()
                # Normalize synonym
                if "supplied by fybroc" in seal_opt_search:
                    seal_opt_search = "installed by fybroc"
                seal_keywords.append(seal_opt_search)
            
            if seal_type_val:
                seal_keywords.append(seal_type_val.lower())
            
            if seal_materials_val:
                seal_keywords.append(seal_materials_val.lower())
            
            if seal_elastomers_val:
                seal_keywords.append(seal_elastomers_val.lower())
            
            if seal_guard_val:
                # SEAL_GUARD SFO values: "supplied by fybroc" / "not supplied by fybroc"
                seal_keywords.append(seal_guard_val.lower())

            if seal_keywords:
                conditions = " AND ".join(["LOWER(SelectionsJson) LIKE ?"] * len(seal_keywords))
                params = ["SEAL_ASSEMBLY"] + [f"%{k}%" for k in seal_keywords]
                try:
                    row = cursor.execute(
                        f"SELECT TOP 1 SegmentValue FROM cfg.vw_SegmentCombinationLookup "
                        f"WHERE SegmentCode=? AND {conditions}",
                        *params
                    ).fetchone()
                    if row:
                        seal_assy = row[0]
                except:
                    pass
                
                # Fallback 1: option + type only
                if seal_assy == "??" and seal_type_val and seal_option_val:
                    kw = seal_keywords[:2]  # just option + type
                    conditions = " AND ".join(["LOWER(SelectionsJson) LIKE ?"] * len(kw))
                    params = ["SEAL_ASSEMBLY"] + [f"%{k}%" for k in kw]
                    try:
                        row = cursor.execute(
                            f"SELECT TOP 1 SegmentValue FROM cfg.vw_SegmentCombinationLookup "
                            f"WHERE SegmentCode=? AND {conditions}",
                            *params
                        ).fetchone()
                        if row:
                            seal_assy = row[0]
                    except:
                        pass
                
                # Fallback 2: option alone (for noseal/customer supplied which have type="-")
                if seal_assy == "??" and seal_option_val:
                    try:
                        row = cursor.execute(
                            "SELECT TOP 1 SegmentValue FROM cfg.vw_SegmentCombinationLookup "
                            "WHERE SegmentCode='SEAL_ASSEMBLY' AND LOWER(SelectionsJson) LIKE ?",
                            f"%{seal_keywords[0]}%"
                        ).fetchone()
                        if row:
                            seal_assy = row[0]
                    except:
                        pass

        # OPTIONS — direct match
        opt_keywords = [v.lower() for k in ["COUPLING_OPTION", "BASEPLATE_OPTION"]
                       if (v := body.selections.get(k, "")) and len(v) > 2]
        if opt_keywords:
            conditions = " AND ".join(["LOWER(SelectionsJson) LIKE ?"] * len(opt_keywords))
            params = ["OPTIONS"] + [f"%{k}%" for k in opt_keywords]
            try:
                row = cursor.execute(f"SELECT TOP 1 SegmentValue FROM cfg.vw_SegmentCombinationLookup WHERE SegmentCode=? AND {conditions}", *params).fetchone()
                options_code = row[0] if row else "00"
            except:
                options_code = "00"
        else:
            # No coupling/baseplate fields selected — check if series even has them
            has_options_fields = cursor.execute(
                "SELECT COUNT(*) FROM cfg.SeriesFieldOption "
                "WHERE MetadataPublicationId=? AND SeriesCode=? AND FieldCode IN ('COUPLING_OPTION','BASEPLATE_OPTION')",
                pub_id, body.series
            ).fetchone()[0] > 0
            options_code = body.segment_codes.get("OPTIONS", "00") if not has_options_fields else "??"

        # MOTOR_ASSEMBLY — multi-field lookup (same pattern as PUMP_OPTIONS)
        # The combo table has 11 fields: MOTOR_OPTION, MOTOR_CLASS, MOTOR_ORIENTATION,
        # MOTOR_HORSEPOWER, MOTOR_RPM, MOTOR_VOLTAGE, MOTOR_HERTZ, MOTOR_FRAME,
        # MOTOR_ENCLOSURE, MOTOR_EFFICIENCY, MOTOR_MANUFACTURER
        # SFO field → combo JSON field mapping:
        MOTOR_SFO_TO_COMBO = {
            "MOTOR_OPTION": "MOTOR_OPTION",
            "MOTOR_HP": "MOTOR_HORSEPOWER",
            "MOTOR_RPM": "MOTOR_RPM",
            "MOTOR_VOLTAGE": "MOTOR_VOLTAGE",
            "MOTOR_HERTZ": "MOTOR_HERTZ",
            "FRAME_SIZE": "MOTOR_FRAME",
            "MOTOR_ENCLOSURE": "MOTOR_ENCLOSURE",
            "MOTOR_EFFICIENCY": "MOTOR_EFFICIENCY",
            "MOTOR_MFG": "MOTOR_MANUFACTURER",
        }

        motor_keywords = []
        motor_opt_val = body.selections.get("MOTOR_OPTION", "")
        if motor_opt_val:
            # Handle synonym: "supplied by fybroc" = "installed by fybroc" for motor
            motor_search = motor_opt_val.lower()
            if "supplied by fybroc" in motor_search:
                motor_search = "installed by fybroc"
            motor_keywords.append(motor_search)

        # Add other motor fields for more precise matching
        for sfo_field, combo_field in MOTOR_SFO_TO_COMBO.items():
            if sfo_field == "MOTOR_OPTION":
                continue  # Already handled above
            val = body.selections.get(sfo_field, "")
            if val and len(val) >= 1:
                # Normalize: SFO "3ph - 60 hz" → combo has "/3/60"; SFO "143t" → combo "143"
                search_val = val.lower().strip()
                # Frame size: strip 't' suffix (SFO="143t", combo="143")
                if sfo_field == "FRAME_SIZE":
                    search_val = search_val.rstrip("t").strip()
                # Hertz: SFO="3ph - 60 hz" → combo="/3/60"; SFO="3ph - 50 hz" → combo="/3/50"
                elif sfo_field == "MOTOR_HERTZ":
                    if "60" in search_val:
                        search_val = "3/60"
                    elif "50" in search_val:
                        search_val = "3/50"
                # HP: SFO="1.5" → combo="1.5 hp"; SFO="7.5" → combo="7.5 hp"
                # Use quote boundary: combo JSON has "MOTOR_HORSEPOWER": "5 hp"
                # So search for '"5 hp"' to avoid matching "1.5 hp" or "25 hp"
                elif sfo_field == "MOTOR_HP":
                    search_val = f'": "{search_val} hp"'  # matches the JSON value exactly
                # MFG: SFO="standard offering" → combo="fybroc choice"
                elif sfo_field == "MOTOR_MFG":
                    if "standard" in search_val:
                        search_val = "fybroc choice"
                motor_keywords.append(search_val)

        if motor_keywords:
            # Progressive matching: try all keywords first, then progressively reduce
            # Priority order: motor_option, hp, rpm, voltage, hertz, frame, enclosure, efficiency, mfg
            motor_assy = "???"
            
            # Try full match first
            conditions = " AND ".join(["LOWER(SelectionsJson) LIKE ?"] * len(motor_keywords))
            params = ["MOTOR_ASSEMBLY"] + [f"%{k}%" for k in motor_keywords]
            try:
                row = cursor.execute(
                    f"SELECT TOP 1 SegmentValue FROM cfg.vw_SegmentCombinationLookup "
                    f"WHERE SegmentCode=? AND {conditions}",
                    *params
                ).fetchone()
                if row:
                    motor_assy = row[0]
            except:
                pass
            
            # Progressive fallback: remove keywords from the end (least important)
            if motor_assy == "???":
                for n in range(len(motor_keywords) - 1, 0, -1):
                    use_kw = motor_keywords[:n]
                    conditions = " AND ".join(["LOWER(SelectionsJson) LIKE ?"] * len(use_kw))
                    params = ["MOTOR_ASSEMBLY"] + [f"%{k}%" for k in use_kw]
                    try:
                        row = cursor.execute(
                            f"SELECT TOP 1 SegmentValue FROM cfg.vw_SegmentCombinationLookup "
                            f"WHERE SegmentCode=? AND {conditions}",
                            *params
                        ).fetchone()
                        if row:
                            motor_assy = row[0]
                            break
                    except:
                        continue
        else:
            # No motor keywords formed — check if series even has motor configuration
            has_motor_fields = cursor.execute(
                "SELECT COUNT(*) FROM cfg.SeriesFieldOption "
                "WHERE MetadataPublicationId=? AND SeriesCode=? AND FieldCode='MOTOR_OPTION'",
                pub_id, body.series
            ).fetchone()[0] > 0
            if has_motor_fields:
                motor_assy = body.segment_codes.get("MOTOR_ASSY", "???")
            else:
                # No motor fields for this series — default to "no motor" (code 001)
                motor_assy = "001"
        
        motor_mods = body.segment_codes.get("MOTOR_MODS", "XXX")
        
        # Motor Modifications — build 3-char code from individual mod selections
        mod1 = body.selections.get("MOTOR_MOD_1", "")
        mod2 = body.selections.get("MOTOR_MOD_2", "")
        mod3 = body.selections.get("MOTOR_MOD_3", "")
        if mod1 or mod2 or mod3:
            def get_mod_code(mod_val):
                if not mod_val or "no modification" in mod_val.lower():
                    return "X"
                row = cursor.execute(
                    "SELECT SFOValue FROM cfg.VocabularyMap WHERE FieldCode='MOTOR_MOD' AND LOWER(ComboValue)=?",
                    mod_val.lower().strip()
                ).fetchone()
                return row[0] if row else "X"
            motor_mods = get_mod_code(mod1) + get_mod_code(mod2) + get_mod_code(mod3)

        # Testing — lookup the 2-char base-36 code from the V6 Testing table
        # (cfg.vw_SegmentCombinationLookup SegmentCode='TESTING', 60 rows). This
        # code is the testing segment of the part number.
        #
        # The stored SelectionsJson uses the workbook's PREFIXED test tokens and
        # 'none' for "no test", e.g.:
        #   {"PERFORMANCE_TESTING":"1d-wit perf test","HYDROTEST":"none",
        #    "VIBRATION":"none","SOUND_LEVEL":"4b-sound level test"}
        # The user's selections come from cfg.SeriesFieldOption in a DIFFERENT
        # vocabulary (no numeric prefix; "not included" instead of "none";
        # "certificate"/"testing" suffixes). Prior code matched with fuzzy LIKE
        # and skipped "not included", so almost every combination failed and the
        # code defaulted to "00" - which is why testing never appeared in the
        # part number. We normalize each selection to the stored token and match
        # all four fields EXACTLY.
        testing = "00"

        def _norm_test(field_code: str) -> str:
            raw = str(body.selections.get(field_code, "")).strip().lower()
            # No selection / explicit not-included -> the stored "none" token.
            if raw in ("", "none", "not included", "not supplied by fybroc"):
                return "none"
            # Vibration and Sound Level have a single non-none token regardless
            # of witnessed/non-witnessed in the V6 Testing table.
            if field_code == "VIBRATION_TESTING":
                return "5b-vibration test"
            if field_code == "SOUND_LEVEL_TESTING":
                return "4b-sound level test"
            # Performance / Hydrotest: map the SFO wording to the prefixed token.
            core = raw.replace(" certificate", "").replace(" testing", " test").strip()
            perf_map = {
                "non-wit perf test": "1c-non-wit perf test",
                "wit perf test": "1d-wit perf test",
                "non-wit perf test npshr": "1e-non-wit perf test npshr",
                "wit perf test npshr": "1f-wit perf test npshr",
            }
            hydro_map = {
                "non-wit hydro test": "2a-non-wit hydro test",
                "wit hydro test": "2b-wit hydro test",
            }
            if field_code == "PERFORMANCE_TESTING":
                return perf_map.get(core, "none")
            if field_code == "HYDROTEST_CERTIFICATE":
                return hydro_map.get(core, "none")
            return "none"

        perf_t = _norm_test("PERFORMANCE_TESTING")
        hydro_t = _norm_test("HYDROTEST_CERTIFICATE")
        vib_t = _norm_test("VIBRATION_TESTING")
        sound_t = _norm_test("SOUND_LEVEL_TESTING")
        # Exact per-field match against the stored JSON tokens (JSON keys are
        # PERFORMANCE_TESTING / HYDROTEST / VIBRATION / SOUND_LEVEL).
        try:
            row = cursor.execute(
                "SELECT TOP 1 SegmentValue FROM cfg.vw_SegmentCombinationLookup "
                "WHERE SegmentCode='TESTING' "
                "  AND LOWER(SelectionsJson) LIKE ? "
                "  AND LOWER(SelectionsJson) LIKE ? "
                "  AND LOWER(SelectionsJson) LIKE ? "
                "  AND LOWER(SelectionsJson) LIKE ?",
                f'%"performance_testing": "{perf_t}"%',
                f'%"hydrotest": "{hydro_t}"%',
                f'%"vibration": "{vib_t}"%',
                f'%"sound_level": "{sound_t}"%',
            ).fetchone()
            if row:
                testing = row[0]
        except Exception:
            pass

        # Frame size from selection
        import re
        frame_val = body.selections.get("FRAME_SIZE", "")
        if frame_val:
            digits = re.sub(r'[^0-9]', '', frame_val)
            frame_size = digits[:2] if len(digits) >= 2 else "??"
        else:
            frame_size = body.segment_codes.get("FRAME_SIZE", "??")

        # Build Part Number (vertical series omit seal segment)
        if is_vertical:
            pn = f"{brand}{series_code}{size_code}{material_code}{trim_code}-{pump_opts}-{options_code}-{frame_size}{motor_assy}-{motor_mods}-{testing}"
        else:
            pn = f"{brand}{series_code}{size_code}{material_code}{trim_code}-{pump_opts}-{seal_mfg}{seal_assy}-{options_code}-{frame_size}{motor_assy}-{motor_mods}-{testing}"

        # Debug info for segment resolution
        # For vertical series, seal_assy "??" is expected (no seal assembly segment)
        failed = [k for k, v in {
            "seal_assy": seal_assy, "motor_assy": motor_assy,
            "pump_options": pump_opts, "options": options_code,
        }.items() if "?" in str(v)]
        
        # Remove seal_assy from failed list for vertical series (expected behavior)
        if is_vertical and "seal_assy" in failed:
            failed.remove("seal_assy")
        
        segment_debug = {
            "brand": brand,
            "series_code": series_code,
            "size_code": size_code,
            "material_code": material_code,
            "trim_code": trim_code,
            "pump_options": pump_opts,
            "seal_mfg": seal_mfg,
            "seal_assy": seal_assy if not is_vertical else "N/A (vertical)",
            "options": options_code,
            "frame_size": frame_size,
            "motor_assy": motor_assy,
            "motor_mods": motor_mods,
            "testing": testing,
            "is_vertical": is_vertical,
            "failed_segments": failed,
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

        # Normalize material for matching against price.PriceRule SourceOptionValue
        # SFO values: "vr-1", "vr-1a", "ey-2", "vr-1 bpo/dma", "vr-1a bpo/dma", "vr-1v"
        # Pricing values: "VR-1 (Standard)", "EY-2", "VR-1 BPO/DMA", "VR-1V"
        # Build multiple LIKE patterns to try
        mat_patterns = []
        if material_display:
            # Direct pattern (works for ey-2, vr-1 bpo/dma, vr-1v)
            direct = material_display.replace(" ", "%")
            mat_patterns.append(f"%{direct}%")
            
            # VR-1 / VR-1A → "VR-1 (Standard)" mapping
            # "vr-1a" and "vr-1" are both standard VR-1 material
            if material_display in ("vr-1", "vr-1a"):
                mat_patterns.append("%vr-1%standard%")
                mat_patterns.append("%vr-1 (%")
            elif "bpo/dma" in material_display:
                mat_patterns.append("%bpo/dma%")
            elif material_display == "vr-1v":
                mat_patterns.append("%vr-1v%")

        # Base pump price - try each material pattern until one matches
        base_row = None
        for mat_pattern in mat_patterns:
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
                break

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

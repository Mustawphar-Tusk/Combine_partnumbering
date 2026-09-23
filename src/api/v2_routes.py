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
NUMERIC_OPTION_FIELDS = {"MOTOR_HP", "MOTOR_RPM", "MOTOR_HERTZ", "MOTOR_VOLTAGE",
                         "IMPELLER_TRIM",
                         # Vertical-series numeric fields (5500/5530/...): these
                         # are whole-number sizes stored as strings, so SQL string
                         # order mixes 1,10,11,...,2,3. Present ascending numeric.
                         "SETTING", "LENGTH", "TAILPIPE_LENGTH"}

# DIMENSIONAL fields whose option values are compound sizes like "10x12x16"
# (suction x discharge x impeller). Plain string order mis-sorts these
# ("10x12x16" before "2x3x6" because '1' < '2'); they must sort by the tuple of
# their numeric parts so the UI shows an ascending, logical progression.
DIMENSIONAL_OPTION_FIELDS = {"ALT_SIZE"}

# ---------------------------------------------------------------------------
# Dean PUMP_CONFIGURATION applicability gating (authoritative from the Dean Data
# Sheet Rev 2 macro `Sheet1.Worksheet_Change` at Data Sheet!D8). Selecting the
# Pump Configuration bundle determines whether the Baseplate, Coupling, and Motor
# component groups are part of the pump at all. When a group is excluded, its
# fields are NOT applicable (dropped from the field set, like WETTED_HARDWARE_
# SELECTION) and therefore not priced.
#
# This is Dean-only: PUMP_CONFIGURATION with these bundle values exists only for
# Dean. Fybroc has no PUMP_CONFIGURATION field, so the gate never triggers for
# Fybroc and its applicability is unchanged.
DEAN_COMPONENT_GROUP_FIELDS = {
    "BASEPLATE": {"BASEPLATE_TYPE", "DRIP_PAN", "ALIGNMENT_LUGS", "LIFTING_LUGS",
                  "LEVELLING_SCREWS", "GROUNDING_LUG", "GROUT_HOLE",
                  "ISOLATION_PADS", "STILTS"},
    "COUPLING": {"COUPLING_TYPE", "COUPLING_GUARD"},
    "MOTOR": {"FRAME_SIZE"},
}

# Pump Configuration bundle -> set of component groups INCLUDED. Any group not in
# the set is excluded (its fields drop out). Matches the 8 bundles in the Dean
# SeriesFieldOption PUMP_CONFIGURATION domain and the macro cascade.
DEAN_PUMP_CONFIG_INCLUDES = {
    "pump only": set(),
    "pump and baseplate": {"BASEPLATE"},
    "pump, baseplate, and coupling": {"BASEPLATE", "COUPLING"},
    "pump and motor": {"MOTOR"},
    "pump, baseplate, and motor": {"BASEPLATE", "MOTOR"},
    "pump, baseplate, coupling and motor": {"BASEPLATE", "COUPLING", "MOTOR"},
    "pump and coupling": {"COUPLING"},
    "pump, coupling and motor": {"COUPLING", "MOTOR"},
}


def _dean_pump_config_excluded_fields(selections: dict) -> set[str]:
    """Fields that are NOT applicable given the chosen PUMP_CONFIGURATION bundle.

    Returns the union of component-group fields for every group the bundle
    excludes (Baseplate/Coupling/Motor). Empty set when PUMP_CONFIGURATION is
    unset or not a recognized Dean bundle (so non-Dean configs are unaffected).
    """
    pc = None
    for k, v in selections.items():
        if k.upper() == "PUMP_CONFIGURATION" and v is not None and str(v).strip():
            pc = str(v).strip().lower()
            break
    if pc is None or pc not in DEAN_PUMP_CONFIG_INCLUDES:
        return set()
    included = DEAN_PUMP_CONFIG_INCLUDES[pc]
    excluded = set()
    for group, fields in DEAN_COMPONENT_GROUP_FIELDS.items():
        if group not in included:
            excluded |= fields
    return excluded


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


def _selected_size(selections: dict) -> str | None:
    """The pump size from the current selections, if chosen (ALT_SIZE or SIZE).

    Returns None when no size is selected. Used to scope size-aware option
    projection (Dean publishes options PER (series, size); Fybroc's rows are
    series-level with SizeCode NULL).
    """
    for k, v in selections.items():
        if k.upper() in ("ALT_SIZE", "SIZE") and v is not None and str(v).strip():
            return str(v).strip()
    return None


def _size_option_clause(size: str | None) -> tuple[str, list]:
    """SQL fragment + params to scope a cfg.SeriesFieldOption read by size.

    Semantics (backward-compatible / Fybroc-safe):
      * size is None (no size chosen yet): no size filter - return the series
        union across all sizes. Fybroc rows (SizeCode NULL) are included as-is.
      * size is set: match series-level rows (SizeCode IS NULL, e.g. Fybroc and
        Dean's ungated BARRIER_PLAN) OR rows for exactly that size. So Fybroc
        (all SizeCode NULL) is unaffected, while Dean narrows to the model size.
    """
    if not size:
        return "", []
    return " AND (SizeCode IS NULL OR SizeCode = ?)", [size]


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
# Segment-combination lookup cache
# ---------------------------------------------------------------------------
# The PN-assembly segment lookups query cfg.vw_SegmentCombinationLookup with
# `LOWER(SelectionsJson) LIKE '%kw%'` (leading wildcard = full partition scan),
# and do progressive-fallback retries - so a single /resolve fires ~15 scans,
# and the PUMP_OPTIONS partition alone has 276K rows. On the vertical (5500)
# path this dominated resolve at ~4.3s.
#
# The combination data is STATIC per loaded import batch, so we cache each
# SegmentCode's rows in memory once per process and do the substring matching
# in Python. This preserves the exact prior semantics (all keywords must be
# substrings of lower(SelectionsJson), AND-combined, first match in the view's
# natural scan order = clustered SegmentCombinationImportId order), while
# turning ~15 DB scans per request into one-time in-memory work.
_SEGMENT_ROWS_CACHE: dict = {}   # SegmentCode -> [(selections_json_lower, segment_value), ...]
_SEGMENT_CACHE_TTL_SECONDS = 300.0
_SEGMENT_CACHE_EXPIRES: dict = {}


def _segment_rows(cursor, segment_code):
    """Return cached [(selections_json_lower, segment_value)] for a SegmentCode,
    in the view's natural (clustered id) order. Loaded once per process (short
    TTL), matching cfg.vw_SegmentCombinationLookup's active-batch filter."""
    now = time.monotonic()
    exp = _SEGMENT_CACHE_EXPIRES.get(segment_code, 0.0)
    if segment_code in _SEGMENT_ROWS_CACHE and now < exp:
        return _SEGMENT_ROWS_CACHE[segment_code]
    # Read straight from the same staging source the view uses, INCLUDING the
    # clustered key, and order by it - so the cached "first match" is exactly the
    # row the old `SELECT TOP 1 ... (no ORDER BY)` returned (scan = clustered
    # order). Ordering by SegmentValue would NOT be equivalent: OPTIONS and
    # SEAL_ASSEMBLY have duplicate SegmentValues whose scan order differs from
    # value order, so the winning row could change and break PN parity.
    rows = cursor.execute(
        "SELECT sci.SelectionsJson, sci.SegmentValue "
        "FROM stg.SegmentCombinationImport sci "
        "WHERE sci.SegmentCode = ? "
        "  AND sci.ImportBatchId IN ("
        "      SELECT ImportBatchId FROM stg.SegmentCombinationImportBatch "
        "      WHERE FamilyCode = 'FYBROC' AND Status = 'Loaded') "
        "ORDER BY sci.SegmentCombinationImportId",
        segment_code,
    ).fetchall()
    cached = [((r[0] or "").lower(), r[1]) for r in rows]
    _SEGMENT_ROWS_CACHE[segment_code] = cached
    _SEGMENT_CACHE_EXPIRES[segment_code] = now + _SEGMENT_CACHE_TTL_SECONDS
    return cached


def _seg_first_match(cursor, segment_code, patterns):
    """First SegmentValue whose lower(SelectionsJson) contains EVERY pattern in
    `patterns` (each pattern is a plain substring, already lower-cased, no % ).
    Returns None if no row matches. Mirrors the old
    `WHERE SegmentCode=? AND LOWER(SelectionsJson) LIKE '%p1%' AND ...` + TOP 1."""
    subs = [p for p in patterns if p]
    for js, val in _segment_rows(cursor, segment_code):
        if all(s in js for s in subs):
            return val
    return None


def _load_constraint_context(cursor, pub_id, family_id, series):
    """Read all the CONSTANT constraint data for a (pub, family, series) ONCE, so
    that repeated _apply_constraints calls within a single request (e.g. the
    free-edit endpoint filtering every field) do not re-query the same tables.

    Returns a dict consumed by _apply_constraints via its `ctx` argument. All the
    contained data depends only on (pub, family, series), never on the current
    selections, so it is safe to reuse across every field in one request.
    """
    # Both tables are family-scoped (PumpFamilyId): a family's constraint rules
    # and label->code map are read for THAT family only, so Dean and Fybroc
    # coexist in the same tables without cross-contaminating each other's
    # enforcement (esp. on shared labels like Seal Type / Seal Option / Shaft
    # Material). Fybroc rows are tagged family 2; Dean family 1.
    label_to_sfo = {
        r[0]: r[1] for r in cursor.execute(
            "SELECT ConstraintFieldName, SFOFieldCode FROM cfg.ConstraintFieldMap "
            "WHERE PumpFamilyId = ?", family_id
        ).fetchall()
    }
    feasible_rows = cursor.execute(
        "SELECT TableName, Option1Field, Option1Value, Option2Field, Option2Value, "
        "       Option3Field, Option3Value, Option4Field, Option4Value, "
        "       Allowed, SeriesApplicability "
        "FROM cfg.FeasibleConstraint WHERE PumpFamilyId = ?", family_id
    ).fetchall()

    scope_row = cursor.execute(
        "SELECT DISTINCT SeriesScope FROM cfg.MotorConstraint "
        "WHERE MetadataPublicationId=? AND PumpFamilyId=? "
        "AND (SeriesScope = ? OR SeriesScope LIKE ? OR SeriesScope LIKE ? "
        "     OR SeriesScope LIKE ?)",
        pub_id, family_id, series,
        f"{series} %", f"% {series}", f"% {series} %",
    ).fetchone()
    motor_scope = scope_row[0] if scope_row else None

    # All motor-constraint rows for this scope, indexed by
    # (Dimension1Field, Dimension2Field) -> {dim1_value_lower -> {dim2_value_lower}}
    # and the reverse (dim2 -> {dim1}) so both directions are O(1) lookups.
    mc_fwd: dict = {}
    mc_rev: dict = {}
    if motor_scope:
        for d1f, d1v, d2f, d2v in cursor.execute(
            "SELECT Dimension1Field, Dimension1Value, Dimension2Field, Dimension2Value "
            "FROM cfg.MotorConstraint "
            "WHERE MetadataPublicationId=? AND PumpFamilyId=? AND SeriesScope=?",
            pub_id, family_id, motor_scope,
        ).fetchall():
            if d1v is None or d2v is None:
                continue
            k = (d1f, d2f)
            mc_fwd.setdefault(k, {}).setdefault(str(d1v).strip().lower(), set()).add(
                str(d2v).strip().lower())
            mc_rev.setdefault(k, {}).setdefault(str(d2v).strip().lower(), set()).add(
                str(d1v).strip().lower())

    # MotorHpRpm combine pairs: MotorHp value (lower) -> {allowed RPM values (lower)}
    hp_to_rpm: dict = {}
    for hp_v, rpm_v in cursor.execute(
        "SELECT cv_hp.ValueValue, cv_rpm.ValueValue "
        "FROM cfg.CombineVariable cv_hp "
        "JOIN cfg.CombineVariable cv_rpm "
        "  ON cv_rpm.MetadataPublicationId = cv_hp.MetadataPublicationId "
        " AND cv_rpm.PumpFamilyId = cv_hp.PumpFamilyId "
        " AND cv_rpm.TableName = cv_hp.TableName "
        " AND cv_rpm.KeyValue = cv_hp.KeyValue "
        "WHERE cv_hp.MetadataPublicationId = ? AND cv_hp.PumpFamilyId = ? "
        "  AND cv_hp.TableName = 'MotorHpRpm_to_HpAndRpm' "
        "  AND cv_hp.ValueField = 'MotorHp' AND cv_rpm.ValueField = 'MotorRPM'",
        pub_id, family_id,
    ).fetchall():
        if hp_v is None or rpm_v is None:
            continue
        hp_to_rpm.setdefault(str(hp_v).strip().lower(), set()).add(
            str(rpm_v).strip().lower())

    return {
        "series": series,
        "label_to_sfo": label_to_sfo,
        "feasible_rows": feasible_rows,
        "motor_scope": motor_scope,
        "mc_fwd": mc_fwd,
        "mc_rev": mc_rev,
        "hp_to_rpm": hp_to_rpm,
    }


def _apply_constraints(cursor, pub_id, family_id, series, selections, allowable,
                       ctx=None):
    """Apply the authoritative constraints (feasible + motor + combine HP->RPM)
    to `allowable` in place, given the current `selections` as context.

    This is the SINGLE authoritative constraint filter, shared by the linear-walk
    /evaluate endpoint and the free-edit /configurations/resolve-state endpoint.
    `selections` supplies the context (any field can be context for any other -
    the feasible-constraint rows are omni-directional per leg); `allowable` is the
    per-field option lists to filter (only fields present in `allowable` are
    filtered, so a caller wanting to constrain an already-chosen field must
    include that field in `allowable`).

    `ctx`, when provided, is a pre-loaded constraint context from
    _load_constraint_context (constant per pub/family/series). Passing it lets a
    caller that filters many fields in one request avoid re-querying the constant
    constraint tables per field. When omitted, the context is loaded here, so the
    behavior is identical whether or not a context is supplied.
    """
    if ctx is None:
        ctx = _load_constraint_context(cursor, pub_id, family_id, series)

    label_to_sfo = ctx["label_to_sfo"]
    all_rows = ctx["feasible_rows"]
    motor_scope = ctx["motor_scope"]
    mc_fwd = ctx["mc_fwd"]
    mc_rev = ctx["mc_rev"]
    hp_to_rpm = ctx["hp_to_rpm"]

    import collections as _collections

    def _series_in_scope(scope: str) -> bool:
        s = (scope or "ALL_SERIES").strip().upper()
        if s == "ALL_SERIES":
            return True
        return series.upper() in s  # e.g. "5500_ONLY"

    _sel_norm = {k.upper(): str(v).strip().lower() for k, v in selections.items()}

    allowed_by = _collections.defaultdict(set)
    notallowed_by = _collections.defaultdict(set)
    # Per (table, target_field): the set of ALL target values the table mentions
    # anywhere (across every in-scope row), regardless of context match. This is
    # the target domain the table GOVERNS. An allow-list only restricts values
    # inside this governed domain - values a table never mentions are left
    # untouched. This distinguishes a full-domain allow-list (e.g. Alt Size x
    # Impeller Trim enumerates every trim per size, so unlisted trims are
    # excluded) from a DIRECTIONAL rule (e.g. Setting x Shaft Material lists only
    # wrapped-shaft materials to say "wrapped shafts only come in settings 1-4";
    # it must NOT wipe non-wrapped shaft materials it never names).
    governed_targets = _collections.defaultdict(set)

    for (tname, o1f, o1v, o2f, o2v, o3f, o3v, o4f, o4v, allowed_flag, scope) in all_rows:
        if not _series_in_scope(scope):
            continue
        legs = []
        ok = True
        for label, value in ((o1f, o1v), (o2f, o2v), (o3f, o3v), (o4f, o4v)):
            if not label:
                continue
            sfo = label_to_sfo.get(str(label).strip())
            if not sfo:
                ok = False
                break
            legs.append((sfo.upper(), str(value).strip().lower()))
        if not ok or len(legs) < 2:
            continue
        is_not_allowed = str(allowed_flag).strip().lower() == "not allowed"
        for ti in range(len(legs)):
            target_field, target_value = legs[ti]
            context = [legs[i] for i in range(len(legs)) if i != ti]
            # Every ALLOW row contributes its target value to the governed domain
            # for (table, target_field), whether or not the context matches now.
            if not is_not_allowed:
                governed_targets[(tname, target_field)].add(target_value)
            if all(_sel_norm.get(cf) == cv for cf, cv in context):
                key = (tname, target_field)
                if is_not_allowed:
                    notallowed_by[key].add(target_value)
                else:
                    allowed_by[key].add(target_value)

    _targets = set(allowed_by) | set(notallowed_by)
    for (tname, target_field) in _targets:
        if target_field not in allowable:
            continue
        allow_set = allowed_by.get((tname, target_field), set())
        deny_set = notallowed_by.get((tname, target_field), set())
        if allow_set:
            # Restrict ONLY within the domain this table governs; a target value
            # the table never mentions is not constrained by this table.
            governed = governed_targets.get((tname, target_field), set())
            allowable[target_field] = [
                v for v in allowable[target_field]
                if (str(v).strip().lower() not in governed
                    or str(v).strip().lower() in allow_set)
                and str(v).strip().lower() not in deny_set
            ]
        elif deny_set:
            allowable[target_field] = [
                v for v in allowable[target_field]
                if str(v).strip().lower() not in deny_set
            ]

    # MOTOR CONSTRAINT ENFORCEMENT (cfg.MotorConstraint - ALLOW-LISTs).
    # Uses the pre-indexed motor map (ctx) instead of per-call SQL.
    def _mc_allowed(dim1_field, dim1_value, dim2_field):
        if not motor_scope or dim1_value is None:
            return set()
        return set(mc_fwd.get((dim1_field, dim2_field), {})
                   .get(str(dim1_value).strip().lower(), set()))

    size_value = selections.get("ALT_SIZE")
    hp_sel = selections.get("MOTOR_HP")
    rpm_sel = selections.get("MOTOR_RPM")

    if size_value and "FRAME_SIZE" in allowable:
        frames = _mc_allowed("Alt_Size", size_value, "F_Frame_Size")
        if frames:
            allowable["FRAME_SIZE"] = [
                v for v in allowable["FRAME_SIZE"] if v.strip().lower() in frames
            ]

    if size_value:
        hprpm_for_size = _mc_allowed("Alt_Size", size_value, "F_MotorHpRpm")
        if hprpm_for_size:
            pairs = []
            for c in hprpm_for_size:
                if "-" in c:
                    hp_p, rpm_p = c.split("-", 1)
                    pairs.append((hp_p.strip(), rpm_p.strip()))
            allowed_hp = {hp for hp, _ in pairs}
            if allowed_hp and "MOTOR_HP" in allowable:
                allowable["MOTOR_HP"] = [
                    v for v in allowable["MOTOR_HP"]
                    if str(v).strip().lower() in allowed_hp
                ]
            if hp_sel is not None and "MOTOR_RPM" in allowable:
                hp_l = str(hp_sel).strip().lower()
                allowed_rpm = {rpm for hp, rpm in pairs if hp == hp_l}
                if allowed_rpm:
                    allowable["MOTOR_RPM"] = [
                        v for v in allowable["MOTOR_RPM"]
                        if str(v).strip().lower() in allowed_rpm
                    ]

    if hp_sel is not None and rpm_sel is not None and "FRAME_SIZE" in allowable:
        composite = f"{str(hp_sel).strip()}-{str(rpm_sel).strip()}".lower()
        # F_Frame_Size(dim1) x F_MotorHpRpm(dim2): frames whose allowed hprpm set
        # includes this composite -> reverse map dim2(composite) -> {dim1 frames}.
        frames_for_hprpm = set(
            mc_rev.get(("F_Frame_Size", "F_MotorHpRpm"), {}).get(composite, set())
        )
        if frames_for_hprpm:
            allowable["FRAME_SIZE"] = [
                v for v in allowable["FRAME_SIZE"]
                if v.strip().lower() in frames_for_hprpm
            ]

    # MOTOR Hp -> RPM (Combine Variables MotorHpRpm table).
    if "MOTOR_HP" in selections and "MOTOR_RPM" in allowable:
        hp_value = str(selections["MOTOR_HP"]).strip().lower()
        allowed_rpm_set = set(hp_to_rpm.get(hp_value, set()))
        if allowed_rpm_set:
            allowable["MOTOR_RPM"] = [
                v for v in allowable["MOTOR_RPM"]
                if str(v).strip().lower() in allowed_rpm_set
            ]

    return allowable


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


class FreeConfigRequest(BaseModel):
    """Request for the free-edit /configurations/resolve-state endpoint.

    - series: the pump series (required).
    - selections: current field selections. When empty, the endpoint seeds the
      STANDARD (STD) value for every configurable field for the series.
    - changed_field: the field the user just changed (optional). Informational -
      the re-resolution is invalidation-based and does NOT depend on it, but it
      lets the endpoint prefer keeping the just-changed field and re-resolve
      everything else around it.
    """
    series: str
    selections: dict[str, str] = Field(default_factory=dict)
    changed_field: str | None = None


class FreeConfigResponse(BaseModel):
    """Response for the free-edit /configurations/resolve-state endpoint.

    Unlike EvaluateResponse (linear-walk, one current field), this exposes a
    COMPLETE configuration: every configurable field has a value (STD-seeded)
    and its own constraint-correct allowable option list computed against every
    OTHER selection (omni-directional). Upstream corrections are non-destructive:
    still-valid selections are kept; only invalidated fields are re-resolved
    (auto-reset to STD when STD is valid, else dropped) and reported.
    """
    family: str
    series: str
    valid: bool
    # Final selection value for every configurable field (STD-seeded / kept /
    # reset / minus any dropped field).
    selections: dict[str, str] = Field(default_factory=dict)
    # Per-field constraint-correct allowable options, computed for EVERY field
    # given all the OTHER current selections (omni-directional, not top-down).
    allowable_options: dict[str, list[str]] = Field(default_factory=dict)
    # Field-code -> STANDARD default option value for this series (all fields).
    standard_defaults: dict[str, str] = Field(default_factory=dict)
    # Fields whose incoming value was invalidated by another selection and was
    # AUTO-RESET to the STD value (field_code -> new STD value). Only used for
    # fields dropped by conditional-applicability (see below); user-made
    # selections are NEVER silently reset - they are reported in `conflicts`.
    reset_fields: dict[str, str] = Field(default_factory=dict)
    # Fields removed because they no longer APPLY to the configuration (e.g.
    # WETTED_HARDWARE_SELECTION when the wetted-hardware mode is not custom).
    # This is applicability, not incompatibility - distinct from `conflicts`.
    dropped_fields: list[str] = Field(default_factory=list)
    # Non-destructive conflict report. When a selection the user made is not
    # compatible with the other current selections, its value is KEPT (never
    # silently changed) and a conflict entry is emitted so the UI can flag the
    # field and recommend valid alternatives. Each entry:
    #   { "field": <field_code>,
    #     "value": <the kept, incompatible value>,
    #     "conflicts_with": [<other field codes that make it invalid>],
    #     "recommended": [<up to N compatible option values for this field
    #                      given the OTHER selections>] }
    conflicts: list[dict] = Field(default_factory=list)
    # Fields applicable in authoritative hierarchy order (for stable UI layout).
    ordered_fields: list[str] = Field(default_factory=list)
    # Identifier (PN segment) code for each final selection.
    resolved_codes: dict[str, str | None] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


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

        # Get ALL options for this series, scoped to the selected size when one is
        # chosen (Dean options are per (series, size); Fybroc rows are SizeCode
        # NULL and therefore unaffected by the size clause).
        _size = _selected_size(body.selections)
        _size_sql, _size_params = _size_option_clause(_size)
        rows = cursor.execute(
            "SELECT FieldCode, OptionValue, IsStandard FROM cfg.SeriesFieldOption "
            "WHERE MetadataPublicationId = ? AND SeriesCode = ?" + _size_sql +
            " ORDER BY FieldCode, OptionValue",
            pub_id, body.series, *_size_params,
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
        _seen_opt: set[tuple[str, str]] = set()
        for field_code, option_value, is_standard in rows:
            # De-duplicate values: when no size is selected the query unions every
            # size's rows for the series, so the same option value can repeat.
            if (field_code, option_value) not in _seen_opt:
                _seen_opt.add((field_code, option_value))
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
        # Dean PUMP_CONFIGURATION gating (macro-authoritative): drop the
        # Baseplate/Coupling/Motor fields the chosen bundle excludes, so they are
        # neither shown nor priced. Dean-only (no-op when PUMP_CONFIGURATION unset
        # or non-Dean), so Fybroc applicability is unchanged.
        _pc_excluded = _dean_pump_config_excluded_fields(body.selections)
        if _pc_excluded:
            ordered_fields = [fc for fc in ordered_fields
                              if fc.upper() not in _pc_excluded]
            for _fc in _pc_excluded:
                all_options.pop(_fc, None)
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

        # The tables come in three shapes and this logic handles all three,
        # data-driven, per table + per selected context:
        #   NOT-ALLOWED (e.g. Alt Size x Coupling Guard): remove the listed
        #       target values.
        #   ALLOW-LIST  (e.g. Alt Size x Impeller Trim): only the listed target
        #       values are valid for that context -> keep ONLY those.
        #   MIXED       (e.g. Wetted Hardware x Selection): keep the Allowed set
        #       and drop the Not-Allowed set.
        # For a given constraint table, a given target field, and a given fully-
        # selected+matched context, we collect that context's Allowed and
        # Not-Allowed target values. If there is at least one Allowed row, the
        # target is restricted to (Allowed - NotAllowed); otherwise the
        # Not-Allowed values are removed. When the current context has NO rows in
        # a table, that table does not constrain the target (no filtering), so
        # unrelated sizes are never blanked.

        # FEASIBLE + MOTOR + COMBINE constraint enforcement (single authoritative
        # implementation, shared with /configurations/resolve-state). Filters the
        # unselected fields' options in `allowable` given the effective (pruned)
        # selections. See _apply_constraints for the full data-driven semantics
        # (feasible allow/deny per table, motor allow-lists, HP->RPM pairs).
        _apply_constraints(
            cursor, pub_id, family_id, body.series, effective_selections, allowable
        )

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
    "/families/{family}/configurations/resolve-state",
    response_model=FreeConfigResponse,
)
async def resolve_configuration_state(
    family: str, body: FreeConfigRequest, request: Request
):
    """
    FREE-EDIT configuration state (omni-directional, non-destructive).

    Unlike /configurations/evaluate (a strict top-down linear walk with a single
    "current" field and blanket prefix pruning), this endpoint powers a UI where
    EVERY configurable field is an editable dropdown at all times:

      (a) STD auto-populate: when `selections` is empty, every configurable field
          for the series is seeded with its STANDARD (STD) value, producing a
          complete, valid starting configuration.

      (b) Omni-directional allowable options: for EACH field, the allowable
          option list is computed against every OTHER current selection (not just
          upstream ones). This means a downstream selection can legitimately
          narrow an upstream field's options, and an upstream field can still be
          corrected after downstream picks - as long as the correction agrees
          with the authoritative constraints given everything else selected.

      (c) Non-destructive re-resolution: still-valid selections are ALWAYS kept.
          Only fields whose value is invalidated by the current combination are
          re-resolved - auto-reset to the STD value when STD is valid, otherwise
          dropped. Both are reported (reset_fields / dropped_fields). The loop
          iterates to a fixpoint because one reset can change what is valid for
          another field.

    The authoritative constraint filter (_apply_constraints: feasible + motor +
    combine HP->RPM) is the SAME one /evaluate uses, so this endpoint can never
    admit a combination the linear walk would reject.

    NOT cached (input-dependent). The existing /evaluate endpoint is unchanged.
    """
    conn_str = _get_conn_str(request)
    conn = pyodbc.connect(conn_str, autocommit=True)
    try:
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

        # Size-scoped option projection (Dean per (series, size); Fybroc SizeCode
        # NULL -> unaffected). Before a size is chosen, the series union is shown.
        _size = _selected_size(body.selections)
        _size_sql, _size_params = _size_option_clause(_size)
        rows = cursor.execute(
            "SELECT FieldCode, OptionValue, IsStandard FROM cfg.SeriesFieldOption "
            "WHERE MetadataPublicationId = ? AND SeriesCode = ?" + _size_sql +
            " ORDER BY FieldCode, OptionValue",
            pub_id, body.series, *_size_params,
        ).fetchall()

        if not rows:
            return FreeConfigResponse(
                family=family_upper,
                series=body.series,
                valid=False,
                errors=[
                    f"No configuration options found for {family_upper} series "
                    f"{body.series}. Metadata may not be loaded for this family."
                ],
            )

        # Base option catalog + STD defaults for the series.
        all_options: dict[str, list[str]] = {}
        standard_defaults: dict[str, str] = {}
        _seen_opt: set[tuple[str, str]] = set()
        for field_code, option_value, is_standard in rows:
            # De-duplicate: the no-size series union can repeat a value across
            # sizes. Keep one entry per (field, value).
            if (field_code, option_value) not in _seen_opt:
                _seen_opt.add((field_code, option_value))
                all_options.setdefault(field_code, []).append(option_value)
            if is_standard:
                standard_defaults[field_code] = option_value
        for field_code in all_options:
            all_options[field_code] = _sort_field_options(
                field_code, all_options[field_code]
            )

        # Normalize incoming selections onto known field codes (upper-cased keys,
        # keep only fields that exist for this series). SERIES pseudo-field is
        # not a configurable option field, so it is ignored here.
        incoming = {
            k.upper(): v
            for k, v in body.selections.items()
            if k.upper() in all_options
        }

        # (a) STD seed when nothing selected: start every field at its STD.
        if not incoming:
            selections = {
                fc: standard_defaults[fc]
                for fc in all_options
                if fc in standard_defaults
            }
        else:
            selections = dict(incoming)

        # DERIVE the SETTING/LENGTH mode from what the user just changed.
        # SETTING/LENGTH is a mode pseudo-field: "standard setting" gates the
        # SETTING field (ConstraintTable23), "custom length" gates the LENGTH
        # field (ConstraintTable22) - the two are mutually exclusive. Rather than
        # make the user flip the mode by hand (which otherwise surfaces as a
        # confusing conflict), we set it automatically: choosing a LENGTH implies
        # custom-length mode; choosing a SETTING implies standard-setting mode.
        # The now-inapplicable sibling is then dropped by _applicable_fields.
        _changed_fc = body.changed_field.upper() if body.changed_field else None
        if "SETTING/LENGTH" in all_options:
            def _has(fc):
                v = selections.get(fc)
                return v is not None and str(v).strip() != ""
            if _changed_fc == "LENGTH" and _has("LENGTH"):
                selections["SETTING/LENGTH"] = "custom length"
                selections.pop("SETTING", None)
            elif _changed_fc == "SETTING" and _has("SETTING"):
                selections["SETTING/LENGTH"] = "standard setting"
                selections.pop("LENGTH", None)
            elif _changed_fc == "SETTING/LENGTH":
                # User set the mode directly: clear the sibling that no longer applies.
                mode = str(selections.get("SETTING/LENGTH", "")).strip().lower()
                if mode == "custom length":
                    selections.pop("SETTING", None)
                elif mode == "standard setting":
                    selections.pop("LENGTH", None)

        def _applicable_fields(sel: dict[str, str]) -> list[str]:
            """Fields applicable in hierarchy order, honoring conditional
            applicability:
              - WETTED_HARDWARE_SELECTION applies ONLY when WETTED_HARDWARE ==
                'select material'.
              - SETTING/LENGTH mode gates the LENGTH vs SETTING pair: in
                'custom length' mode only LENGTH applies; in 'standard setting'
                mode only SETTING applies (the other is not shown)."""
            fields = _order_fields(all_options.keys())
            wh = sel.get("WETTED_HARDWARE")
            if wh is not None and str(wh).strip().lower() != "select material":
                fields = [fc for fc in fields if fc != "WETTED_HARDWARE_SELECTION"]
            mode = str(sel.get("SETTING/LENGTH", "")).strip().lower()
            if mode == "custom length":
                fields = [fc for fc in fields if fc != "SETTING"]
            elif mode == "standard setting":
                fields = [fc for fc in fields if fc != "LENGTH"]
            # Dean PUMP_CONFIGURATION gating (macro-authoritative): drop the
            # Baseplate/Coupling/Motor fields the chosen bundle excludes.
            excluded = _dean_pump_config_excluded_fields(sel)
            if excluded:
                fields = [fc for fc in fields if fc.upper() not in excluded]
            return fields

        # Load the constant constraint data ONCE for this request, then reuse it
        # for every per-field filter below (avoids re-querying the constraint
        # tables per field, which is what made this endpoint slow).
        constraint_ctx = _load_constraint_context(
            cursor, pub_id, family_id, body.series
        )

        def _allowable_for(target: str, sel: dict[str, str]) -> list[str]:
            """Constraint-correct options for `target` given every OTHER
            selection as context (omni-directional)."""
            context = {k: v for k, v in sel.items() if k != target}
            box = {target: list(all_options.get(target, []))}
            _apply_constraints(
                cursor, pub_id, family_id, body.series, context, box,
                ctx=constraint_ctx,
            )
            return box.get(target, [])

        def _norm(v):
            return str(v).strip().lower()

        def _conflicting_context_fields(target: str, sel: dict[str, str]) -> list[str]:
            """Which OTHER selected fields actually participate in making
            `target`'s current value incompatible. We test each other selected
            field in isolation: if removing it from the context makes target's
            value valid again, that field is (part of) the conflict. This gives
            the user a precise "conflicts with X, Y" explanation."""
            cur = sel.get(target)
            if cur is None:
                return []
            culprits = []
            others = [k for k in sel if k != target]
            for k in others:
                reduced = {kk: vv for kk, vv in sel.items() if kk != k and kk != target}
                allowed_without = _allowable_for(target, {**reduced, target: cur})
                if any(_norm(cur) == _norm(a) for a in allowed_without):
                    # Dropping k restores validity -> k participates in the conflict.
                    culprits.append(k)
            return culprits

        reset_fields: dict[str, str] = {}
        dropped_fields: set[str] = set()

        # (c) NON-DESTRUCTIVE re-resolution. The user's explicit selections are
        # NEVER silently changed. We only:
        #   1. Drop fields that no longer APPLY (conditional applicability, e.g.
        #      WETTED_HARDWARE_SELECTION when the wetted-hardware mode is not
        #      custom) - this is applicability, not incompatibility.
        #   2. Detect INCOMPATIBLE selections (a value not allowed given the other
        #      current selections), KEEP the value, and report a conflict with the
        #      fields it clashes with plus recommended compatible options. The UI
        #      surfaces this so the user can correct it deliberately - instead of
        #      the config silently resetting their upstream choices.
        applicable = set(_applicable_fields(selections))
        for fc in list(selections):
            if fc not in applicable:
                del selections[fc]
                dropped_fields.add(fc)

        conflicts: list[dict] = []
        for fc in list(selections):
            allowed = _allowable_for(fc, selections)
            cur_val = selections[fc]
            if any(_norm(cur_val) == _norm(a) for a in allowed):
                continue  # compatible - keep as-is
            # Incompatible: keep the value, report the conflict + recommendations.
            culprits = _conflicting_context_fields(fc, selections)
            conflicts.append({
                "field": fc,
                "value": cur_val,
                "conflicts_with": culprits,
                "recommended": allowed[:12],
            })

        # Applicable field order for the (unchanged) selections.
        ordered_fields = _applicable_fields(selections)

        # Per-field allowable options for ALL applicable fields (omni-directional).
        # For a field in conflict we still surface its current (kept) value as a
        # selectable option so the UI shows it as chosen, alongside the compatible
        # recommendations - the value is flagged via `conflicts`, not hidden.
        conflict_fields = {c["field"] for c in conflicts}
        allowable_options = {}
        for fc in ordered_fields:
            allowed = _allowable_for(fc, selections)
            if fc in conflict_fields and fc in selections:
                cur = selections[fc]
                if not any(_norm(cur) == _norm(a) for a in allowed):
                    allowed = [cur] + allowed
            allowable_options[fc] = allowed

        # STD defaults limited to applicable fields (so the UI can offer a reset).
        std_out = {
            fc: standard_defaults[fc]
            for fc in ordered_fields
            if fc in standard_defaults
        }

        # Resolve identifier (PN segment) codes for the final selections.
        resolved = {}
        for field, value in selections.items():
            code_row = cursor.execute(
                "SELECT cfg.fn_LookupIdentifierCode(?, ?, ?, ?)",
                pub_id, family_id, field.upper(), value,
            ).fetchone()
            resolved[field] = code_row[0] if code_row and code_row[0] else None

        return FreeConfigResponse(
            family=family_upper,
            series=body.series,
            # The response is always a usable state to render; conflicts are
            # reported in `conflicts` (not via valid=False, which the UI treats
            # as a hard error). The config simply isn't resolvable to a PN until
            # the user clears the conflicts.
            valid=True,
            selections=selections,
            allowable_options=allowable_options,
            standard_defaults=std_out,
            reset_fields=reset_fields,
            dropped_fields=sorted(dropped_fields),
            conflicts=conflicts,
            ordered_fields=ordered_fields,
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

    conn = pyodbc.connect(conn_str, autocommit=True)
    try:
        pub_id, _ = _get_active_publication(conn_str, conn)
        cursor = conn.cursor()
        violations = []

        # Check each selection is valid for the series, scoped to the selected
        # size when one is chosen (Dean options are per (series, size); Fybroc
        # rows are SizeCode NULL so the clause never excludes them).
        _size = _selected_size(body.selections)
        _size_sql, _size_params = _size_option_clause(_size)
        for field, value in body.selections.items():
            exists = cursor.execute(
                "SELECT COUNT(*) FROM cfg.SeriesFieldOption "
                "WHERE MetadataPublicationId = ? AND SeriesCode = ? "
                "AND FieldCode = ? AND OptionValue = ?" + _size_sql,
                pub_id, body.series, field, value, *_size_params,
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

    # Build the CANONICAL configuration JSON for SQL procedures.
    #
    # This JSON is the single source of the configuration signature (hashed here
    # AND in SQL, which must match), and the signature is what drives reuse and
    # the SKU. It MUST be a deterministic function of the configuration CONTENT
    # only: the same pump configuration has to produce the same bytes (and thus
    # the same signature / SKU / reused Part Number) no matter what order the
    # client happened to assemble the selections in.
    #
    # sort_keys=True + fixed separators canonicalize the JSON so identical
    # selections always hash identically. (Before this, key order leaked into
    # the signature: the same config sent with a different key order produced a
    # different signature, missed reuse, and then collided with the existing
    # row's UNIQUE(PartNumber) - surfacing as a spurious HTTP 503. See F160.)
    config_json = json.dumps(
        {
            **body.selections,
            **{f"{k}_CODE": v for k, v in body.segment_codes.items()},
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    # Generate signature (Python parity oracle; SQL recomputes over the SAME
    # canonical bytes via HASHBYTES so the two signatures always agree).
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

        # ------------------------------------------------------------------
        # D130 - DEAN identifier resolve (family-gated, additive). The Dean PN
        # has a different segment structure from Fybroc. Resolve the Dean segment
        # codes (dean_identifier), hand them to the SAME SQL assembler with
        # @FamilyCode='DEAN' (authoritative), keep the parity oracle. The Fybroc
        # block below is unchanged, guarded by the family.
        # ------------------------------------------------------------------
        if family_upper == "DEAN":
            from . import dean_identifier as _dean_id
            _dean_series = body.selections.get("SERIES", body.series)
            _dean_size = (body.selections.get("ALT_SIZE")
                          or body.selections.get("SIZE") or "")
            dean_payload, dean_debug = _dean_id.resolve_segments(
                cursor, _dean_series, _dean_size, body.selections)
            py_pn = dean_debug["py_pn"]
            segment_debug = dean_debug
            is_vertical = False
            segments_payload = json.dumps(dean_payload)
            sql_row = cursor.execute(
                "EXEC cfg.usp_AssembleConfiguredProduct "
                "@FamilyCode=?, @SeriesCode=?, @IsVertical=0, "
                "@SegmentsJson=?, @CanonicalJson=?, @RequestedBy=?, @Persist=1;",
                family_upper, body.series, segments_payload, config_json,
                body.requested_by,
            ).fetchone()
            pn = sql_row[0]
            sku = sql_row[1]
            signature = sql_row[2]
            parity_ok = (py_pn == pn)
            if not parity_ok:
                import logging
                logging.getLogger("uvicorn.error").warning(
                    "D130 PN parity divergence: python=%r sql=%r (series=%s)",
                    py_pn, pn, body.series)
            sku_token_expected = (
                hashlib.sha256(pn.encode()).hexdigest().upper()[:8] if pn else "")
            sku_pn_ok = bool(sku) and (sku_token_expected in sku)
            if not sku_pn_ok:
                import logging
                logging.getLogger("uvicorn.error").warning(
                    "D130 SKU<->PN divergence: pn=%r token=%r sku=%r (series=%s)",
                    pn, sku_token_expected, sku, body.series)

        # Build Part Number from resolved attribute codes
        if family_upper != "DEAN":
            brand = "F" if family_upper == "FYBROC" else "D"

            # Look up each identifier code.
            #
            # The identifier table (cfg.AttributeValue) stores STANDARD/DEFAULT
            # option values with a trailing '*' marker (e.g. the standard material
            # "VR-1" is stored as "VR-1*"). Selections coming off the configuration
            # walk carry the plain value ("vr-1"), so an exact lookup misses the
            # standard row and the segment resolves to '?'. We therefore try the
            # value as-is and, if that misses, the '*'-suffixed (standard) form. This
            # keeps the Python parity oracle faithful to how identity treats
            # standard defaults; it does not change any authoritative value.
            def lookup(field, value):
                if not value:
                    return None
                for candidate in (value, f"{value}*"):
                    row = cursor.execute(
                        "SELECT cfg.fn_LookupIdentifierCode(?, ?, ?, ?)",
                        pub_id, family_id, field, candidate
                    ).fetchone()
                    if row and row[0]:
                        return row[0]
                return None

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
            
                # Direct match — SelectionsJson is now in SFO vocabulary. Match in
                # Python against the cached segment rows (same semantics as the old
                # `LIKE '%kw%'` AND-combined TOP 1, capped at 4 keywords).
                try:
                    return _seg_first_match(cursor, segment_code,
                                            [kw for kw in keywords[:4]])
                except Exception:
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
                    # Progressive matching for vertical pump options (in-memory).
                    pump_opts = None
                    for n in range(len(vert_keywords), 0, -1):
                        try:
                            match = _seg_first_match(
                                cursor, "PUMP_OPTIONS_VERTICAL", vert_keywords[:n])
                        except Exception:
                            match = None
                        if match is not None:
                            pump_opts = match
                            break
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
                    match = _seg_first_match(cursor, "SEAL_ASSEMBLY",
                                             ["noseal nosealgland", "not supplied by fybroc"])
                    seal_assy = match if match is not None else "0X"  # 0X = noseal default
                except Exception:
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
                    try:
                        match = _seg_first_match(cursor, "SEAL_ASSEMBLY", seal_keywords)
                        if match is not None:
                            seal_assy = match
                    except Exception:
                        pass
                
                    # Fallback 1: option + type only
                    if seal_assy == "??" and seal_type_val and seal_option_val:
                        try:
                            match = _seg_first_match(cursor, "SEAL_ASSEMBLY", seal_keywords[:2])
                            if match is not None:
                                seal_assy = match
                        except Exception:
                            pass
                
                    # Fallback 2: option alone (for noseal/customer supplied which have type="-")
                    if seal_assy == "??" and seal_option_val:
                        try:
                            match = _seg_first_match(cursor, "SEAL_ASSEMBLY", [seal_keywords[0]])
                            if match is not None:
                                seal_assy = match
                        except Exception:
                            pass

            # OPTIONS — direct match
            opt_keywords = [v.lower() for k in ["COUPLING_OPTION", "BASEPLATE_OPTION"]
                           if (v := body.selections.get(k, "")) and len(v) > 2]
            if opt_keywords:
                try:
                    match = _seg_first_match(cursor, "OPTIONS", opt_keywords)
                    options_code = match if match is not None else "00"
                except Exception:
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
            
                # Try full match first (in-memory against cached rows).
                try:
                    match = _seg_first_match(cursor, "MOTOR_ASSEMBLY", motor_keywords)
                    if match is not None:
                        motor_assy = match
                except Exception:
                    pass
            
                # Progressive fallback: remove keywords from the end (least important)
                if motor_assy == "???":
                    for n in range(len(motor_keywords) - 1, 0, -1):
                        try:
                            match = _seg_first_match(
                                cursor, "MOTOR_ASSEMBLY", motor_keywords[:n])
                        except Exception:
                            match = None
                        if match is not None:
                            motor_assy = match
                            break
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
                match = _seg_first_match(cursor, "TESTING", [
                    f'"performance_testing": "{perf_t}"',
                    f'"hydrotest": "{hydro_t}"',
                    f'"vibration": "{vib_t}"',
                    f'"sound_level": "{sound_t}"',
                ])
                if match is not None:
                    testing = match
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

            # SQL-AUTHORITATIVE IDENTITY (F150, Option B).
            # SQL now owns the authoritative assembly, signature, SKU, reuse, and
            # persistence. The Python-assembled `pn` above is retained only as a
            # PARITY ORACLE: we resolve the composite segments in Python (which
            # respects all constraint corrections), hand the resolved segment codes
            # to cfg.usp_AssembleConfiguredProduct, and use SQL's returned values as
            # authoritative. If Python's PN diverges from SQL's, we log it (a signal
            # the two assemblers disagree) but SQL wins.
            segments_payload = json.dumps({
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
            })
            py_pn = pn  # Python parity-oracle assembly (computed above)

            sql_row = cursor.execute(
                "EXEC cfg.usp_AssembleConfiguredProduct "
                "@FamilyCode=?, @SeriesCode=?, @IsVertical=?, "
                "@SegmentsJson=?, @CanonicalJson=?, @RequestedBy=?, @Persist=1;",
                family_upper, body.series, 1 if is_vertical else 0,
                segments_payload, config_json, body.requested_by,
            ).fetchone()

            # SQL is authoritative for PN, SKU, signature, and reuse.
            pn = sql_row[0]
            sku = sql_row[1]
            signature = sql_row[2]

            # Parity check: Python assembly vs SQL assembly must agree on the PN.
            parity_ok = (py_pn == pn)
            if not parity_ok:
                import logging
                logging.getLogger("uvicorn.error").warning(
                    "F150 PN parity divergence: python=%r sql=%r (series=%s)",
                    py_pn, pn, body.series,
                )

            # SKU<->PN 1:1 invariant (independent of the Python PN oracle): the SKU
            # must carry the PN-derived token = first 8 hex of SHA-256(PartNumber).
            # SQL derives the SKU from the PN; we recompute and expose the check so a
            # divergence is visible even though SQL is authoritative for the SKU.
            sku_token_expected = hashlib.sha256(pn.encode()).hexdigest().upper()[:8] if pn else ""
            sku_pn_ok = bool(sku) and (sku_token_expected in sku)
            if not sku_pn_ok:
                import logging
                logging.getLogger("uvicorn.error").warning(
                    "SKU<->PN divergence: pn=%r expected_token=%r sku=%r (series=%s)",
                    pn, sku_token_expected, sku, body.series,
                )

        # Pricing lookup
        pricing = []
        # component_pricing is a COMPLETE per-component breakdown for tracking:
        # every component this configuration actually selects appears here, with
        # either its price (status 'found') or "C/F" (Contact Factory) when no
        # current price rule matched. Unlike `pricing` (which only lists priced
        # components and drives total_price / the quote engine), this list is
        # additive and exists so the UI can show, per config, exactly which
        # components are priced vs still C/F. Order follows configuration flow.
        component_pricing: list[dict] = []

        def _add_component(label, selection_value, amount=None, detail=None):
            """Record a component in the tracking breakdown. amount=None => C/F.
            selection_value is what the user chose for this component (shown so a
            reviewer can see which selection drives the price / C/F)."""
            component_pricing.append({
                "component": label,
                "selection": (str(selection_value)
                              if selection_value not in (None, "") else None),
                "amount": (float(amount) if amount is not None else None),
                "status": ("found" if amount is not None else "C/F"),
                "detail": detail,
            })

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
            _add_component("Base Pump", size_val, float(base_row[0]), base_row[1])
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
                _add_component("Base Pump (std material)", size_val, float(base_row2[0]), base_row2[1])
            else:
                _add_component("Base Pump", size_val, None)

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
                _add_component("Seal", seal_type, float(seal_row[0]), seal_row[1])
            else:
                _add_component("Seal", seal_type, None)

        # ====================================================================
        # DEAN pricing resolve path (D120). Dean's Matrix pricebook uses its own
        # component-code vocabulary (OPTION_ADDER / COUPLING / BASEPLATE /
        # SHAFT_CONFIG), NOT the Fybroc ADDER_COMPONENTS/MULTI_COMPONENTS field
        # codes below. So for DEAN we price via a dedicated branch and SKIP the
        # Fybroc blocks (they would only add spurious C/F entries). The Fybroc
        # path is byte-for-byte unchanged (this branch is family-gated).
        #
        # Composition (macro/formula-authoritative, docs/evidence/D100/
        # DEAN_DATASHEET_VBA_LOGIC.md): total = base list + Σ|option adder| (only
        # for selected options) + coupling + baseplate + shaft config, gated by
        # Pump Configuration presence. Adder sign ignored (abs). List price only;
        # discount is a per-line sales input (default 0).
        # ====================================================================
        if family_upper == "DEAN":
            _dean_excluded = _dean_pump_config_excluded_fields(body.selections)

            def _dean_price_by_conditions(component_code, require_field=None,
                                          require_value=None):
                """Price a Dean component whose PriceRule's conditions ALL match the
                current selections. A rule matches iff EVERY one of its
                PriceConditions is satisfied by a selection (SIZE + PUMP_MATERIAL +
                driving field(s)).

                For OPTION_ADDER we additionally REQUIRE the rule to carry a
                condition on the specific field being priced (require_field=value),
                so pricing CASING_MATERIAL only ever returns a CASING_MATERIAL adder
                rule - not just any rule whose conditions happen to be satisfied by
                the full selection set. Returns (amount, detail) or None."""
                sel_pairs = []
                for fc, v in body.selections.items():
                    if v is None or str(v).strip() == "":
                        continue
                    sel_pairs.append({"f": fc.upper(),
                                      "v": str(v).strip().lower().replace("_", " ")})
                if size_val:
                    sel_pairs.append({"f": "SIZE",
                                      "v": str(size_val).strip().lower().replace("_", " ")})
                sel_json = json.dumps(sel_pairs)
                sql = ["""
                    SELECT TOP 1 pr.Amount, pr.SourceOptionValue
                    FROM price.PriceRule pr
                    JOIN price.PriceBookVersion pbv ON pbv.PriceBookVersionId = pr.PriceBookVersionId AND pbv.IsCurrent = 1
                    WHERE pr.ComponentCode = ? AND pr.IsActive = 1 AND pr.PricingStatus = 'found'
                      AND (pr.SeriesCode = ? OR pr.SeriesCode LIKE ?)
                      AND NOT EXISTS (
                          SELECT 1 FROM price.PriceCondition pc
                          WHERE pc.PriceRuleId = pr.PriceRuleId
                            AND NOT EXISTS (
                                SELECT 1 FROM OPENJSON(?) WITH (f varchar(100) '$.f', v nvarchar(400) '$.v') s
                                WHERE s.f = UPPER(pc.FieldCode)
                                  AND s.v = LOWER(REPLACE(LTRIM(RTRIM(pc.ComparisonValue)), '_', ' '))
                            )
                      )"""]
                params = [component_code, body.series, f"{body.series}%", sel_json]
                if require_field is not None:
                    # The rule MUST have a condition on exactly this field+value,
                    # so the adder returned is the one for the field being priced.
                    sql.append("""
                      AND EXISTS (
                          SELECT 1 FROM price.PriceCondition pc2
                          WHERE pc2.PriceRuleId = pr.PriceRuleId
                            AND UPPER(pc2.FieldCode) = ?
                            AND LOWER(REPLACE(LTRIM(RTRIM(pc2.ComparisonValue)), '_', ' ')) = ?
                      )""")
                    params += [require_field.upper(),
                               str(require_value).strip().lower().replace("_", " ")]
                sql.append(" ORDER BY pr.Priority")
                row = cursor.execute("".join(sql), *params).fetchone()
                if row and row[0] is not None:
                    return float(row[0]), row[1]
                return None

            # (1) OPTION_ADDER: one rule per (SIZE, PUMP_MATERIAL, <field>=<value>).
            # For each selected option field that is applicable (not gated out),
            # look up its adder and add |amount|.
            for fc, val in body.selections.items():
                fcu = fc.upper()
                if fcu in ("SERIES", "ALT_SIZE", "SIZE", "PUMP_MATERIAL",
                           "PUMP_CONFIGURATION"):
                    continue
                if fcu in _dean_excluded:
                    continue
                if val is None or str(val).strip() == "":
                    continue
                priced = _dean_price_by_conditions(
                    "OPTION_ADDER", require_field=fcu, require_value=val)
                if priced is not None:
                    amt = abs(priced[0])
                    pricing.append({"component": f"Adder: {fcu}", "amount": amt,
                                    "detail": priced[1]})
                    _add_component(f"Adder: {fcu}", val, amt, priced[1])

            # (2) COUPLING / BASEPLATE / SHAFT_CONFIG - gated by Pump Config.
            _dean_components = [
                ("COUPLING", "Coupling", "COUPLING"),
                ("BASEPLATE", "Baseplate", "BASEPLATE"),
                ("SHAFT_CONFIG", "Shaft Configuration", "SHAFT"),
            ]
            for comp_code, label, group in _dean_components:
                # If the whole component group is gated out by Pump Configuration,
                # it is not part of the pump -> no charge, not even C/F.
                grp_fields = DEAN_COMPONENT_GROUP_FIELDS.get(group, set())
                if grp_fields and grp_fields <= _dean_excluded:
                    continue
                priced = _dean_price_by_conditions(comp_code)
                if priced is not None:
                    amt = abs(priced[0])
                    pricing.append({"component": label, "amount": amt, "detail": priced[1]})
                    _add_component(label, None, amt, priced[1])
                else:
                    _add_component(label, None, None)

            # Motor + Seal are not priced by the Matrix -> honest C/F.
            _add_component("Motor", body.selections.get("FRAME_SIZE"), None)

            total = sum(p["amount"] for p in pricing)
            # Skip the Fybroc-specific adder/multi blocks below for Dean.
            _dean_priced = True
        else:
            _dean_priced = False

        # ---- Rev0.4 Phase B: additional priced components (1500 & 5500) ----
        # Each of these adder/component tables is keyed by series + size + one
        # driving selection value; the published PriceRule denormalizes that
        # driving value into SourceOptionValue. We look up the current price by
        # ComponentCode + series + size + the selection value. A miss simply
        # means the component isn't priced for this config (Contact Factory /
        # not-yet-determined) and is skipped - the runtime default. Only series
        # 1500 & 5500 have these priced (option 2b); other series no-op here.
        #
        # component_code -> (display label, selection field the price is keyed on)
        ADDER_COMPONENTS = [
            ("SLEEVE", "Sleeve", "IMPELLER_SLEEVE"),
            ("SHAFT_MATERIAL", "Shaft Material", "SHAFT_MATERIAL"),
            ("GLAND_HARDWARE", "Gland Hardware", "GLAND_HARDWARE"),
            ("POWER_FRAME_HARDWARE", "Power Frame Hardware", "POWER_FRAME_HARDWARE"),
            ("BEARING_OPTION", "Bearing Option", "BEARING_OPTION"),
            ("CASING_HARDWARE", "Casing Hardware", "CASING_HARDWARE"),
            ("COUPLING_GUARD", "Coupling Guard", "COUPLING_GUARD"),
            ("BASEPLATE_HARDWARE", "Baseplate Hardware", "FRAME_HARDWARE"),
            ("FLANGE_TYPE", "Flange Type", "FLANGE_TYPE"),
            ("CYCLONE_SEPARATOR", "Cyclone Separator", "CYCLONE_SEPERATOR"),
            ("CASING_DRAINS", "Casing Drains", "CASING_DRAINS"),
            ("SUCTION_DISCHARGE_TAPS", "Suction/Discharge Taps", "SUCTION_DISCHARGE_TAPS"),
            ("SEAL_GUARD", "Seal Guard", "SEAL_GUARD"),
            ("PERFORMANCE_TESTING", "Performance Testing", "PERFORMANCE_TESTING"),
            ("VIBRATION_TESTING", "Vibration Testing", "VIBRATION_TESTING"),
            ("SOUND_LEVEL_TESTING", "Sound Level Testing", "SOUND_LEVEL_TESTING"),
            ("PUMP_ELASTOMERS", "Pump Elastomers", "PUMP_ELASTOMERS"),
            ("HYDROTEST_CERTIFICATE", "Hydrotest Certificate", "HYDROTEST_CERTIFICATE"),
            ("IMPELLER_BALANCE", "Impeller Balance", "IMPELLER_BALANCE"),
        ]

        def _price_component(component_code: str, selection_value: str):
            """Return (amount, detail) for a component priced by series+size+value,
            or None. Matches on the denormalized SourceOptionValue (case-insensitive,
            underscores/spaces normalized)."""
            if not selection_value:
                return None
            v = selection_value.strip().lower()
            # try exact-ish then space/underscore-insensitive LIKE
            patterns = [v, v.replace(" ", "%"), v.replace("_", "%").replace(" ", "%")]
            for pat in patterns:
                row = cursor.execute("""
                    SELECT TOP 1 pr.Amount, pr.SourceOptionValue
                    FROM price.PriceRule pr
                    JOIN price.PriceBookVersion pbv ON pbv.PriceBookVersionId = pr.PriceBookVersionId AND pbv.IsCurrent = 1
                    WHERE pr.ComponentCode = ? AND pr.IsActive = 1 AND pr.PricingStatus = 'found'
                      AND (pr.SeriesCode = ? OR pr.SeriesCode LIKE ?)
                      AND UPPER(pr.SourceSizeValue) LIKE ?
                      AND LOWER(REPLACE(pr.SourceOptionValue,'_',' ')) LIKE ?
                    ORDER BY pr.Priority
                """, component_code, body.series, f"{body.series}%",
                     f"{size_upper}%", pat.replace("_", " ")).fetchone()
                if row and row[0] is not None:
                    return float(row[0]), row[1]
            return None

        for comp_code, label, sel_field in (ADDER_COMPONENTS if not _dean_priced else []):
            sel_val = body.selections.get(sel_field, "")
            if not sel_val:
                # The config does not select this component -> not applicable,
                # so it is not part of this configuration's breakdown at all.
                continue
            priced = _price_component(comp_code, sel_val)
            if priced is not None:
                pricing.append({"component": label, "amount": priced[0], "detail": priced[1]})
                _add_component(label, sel_val, priced[0], priced[1])
            else:
                _add_component(label, sel_val, None)

        # ---- Rev0.4 Phase B: MULTI-CONDITION components (MOTOR/COUPLING/
        # BASEPLATE/TAILPIPE) ----
        # These price tables are keyed by several selection fields at once, stored
        # as one price.PriceCondition row per field. A rule prices the config only
        # if EVERY one of its conditions is satisfied by the resolved selections.
        # We resolve each condition's value from the selections (with a couple of
        # derived fields), case/space-insensitive. A miss => the component is not
        # priced for this config (Contact Factory / not-yet-determined) and is
        # skipped, which is the runtime default.
        def _norm(v) -> str:
            return str(v or "").strip().lower().replace("_", " ")

        def _derived_selection(field_code: str) -> str | None:
            """Resolve a condition FieldCode to a value from the selections,
            including derived fields the price tables use."""
            sels = body.selections
            fc = field_code.upper()
            if fc == "SIZE":
                return sels.get("ALT_SIZE") or sels.get("SIZE")
            if fc in ("F_MOTORHPRPM",):
                hp = sels.get("MOTOR_HP"); rpm = sels.get("MOTOR_RPM")
                return f"{hp}-{rpm}" if hp and rpm else None
            if fc in ("F_FRAME_SIZE",):
                return sels.get("FRAME_SIZE")
            if fc in ("F_COUPLING_OPTION",):
                return sels.get("COUPLING_OPTION")
            # default: same-named selection field
            return sels.get(fc)

        def _price_multi_condition(component_code: str, label: str, cond_fields: list[str]):
            """Find a current PriceRule for this component+series whose EVERY
            condition matches the resolved selections; return (amount, detail).

            The match is done entirely in SQL (no per-rule IN list, which would
            overflow the 2100-parameter limit for large tables like TAILPIPE).
            We pass the resolved (field, normalized-value) selections as a JSON
            array; a rule matches iff it has NO condition whose normalized value
            is absent from that array. Values are normalized the same way both
            sides (lower, trim, '_'->' ')."""
            # Build the resolved selection values for this component's condition
            # fields (skip any the config doesn't supply -> no match possible).
            sel_pairs = []
            for fc in cond_fields:
                v = _derived_selection(fc)
                if v is None or str(v).strip() == "":
                    # A required condition field has no selection value -> this
                    # component cannot be priced for this config.
                    return None
                sel_pairs.append({"f": fc.upper(), "v": _norm(v)})
            sel_json = json.dumps(sel_pairs)
            size_v = (body.selections.get("ALT_SIZE") or body.selections.get("SIZE") or "").upper()
            row = cursor.execute("""
                SELECT TOP 1 pr.Amount, pr.SourceOptionValue
                FROM price.PriceRule pr
                JOIN price.PriceBookVersion pbv ON pbv.PriceBookVersionId = pr.PriceBookVersionId AND pbv.IsCurrent = 1
                WHERE pr.ComponentCode = ? AND pr.IsActive = 1 AND pr.PricingStatus = 'found'
                  AND (pr.SeriesCode = ? OR pr.SeriesCode LIKE ?)
                  AND (pr.SourceSizeValue IS NULL OR UPPER(pr.SourceSizeValue) = ? OR UPPER(pr.SourceSizeValue) LIKE ?)
                  AND NOT EXISTS (
                      SELECT 1 FROM price.PriceCondition pc
                      WHERE pc.PriceRuleId = pr.PriceRuleId
                        AND NOT EXISTS (
                            SELECT 1 FROM OPENJSON(?) WITH (f varchar(100) '$.f', v nvarchar(400) '$.v') s
                            WHERE s.f = UPPER(pc.FieldCode)
                              AND s.v = LOWER(REPLACE(LTRIM(RTRIM(pc.ComparisonValue)), '_', ' '))
                        )
                  )
                ORDER BY pr.Priority
            """, component_code, body.series, f"{body.series}%",
                 size_v, f"{size_v}%", sel_json).fetchone()
            if row and row[0] is not None:
                return float(row[0]), row[1]
            return None

        # (component, label, [condition field sets to try]). Some components have
        # more than one condition shape (e.g. COUPLING: horizontal vs 5500).
        MULTI_COMPONENTS = [
            ("MOTOR", "Motor", [[
                "MOTOR_ENCLOSURE", "MOTOR_EFFICIENCY", "MOTOR_VOLTAGE", "MOTOR_HERTZ",
                "MOTOR_HP", "MOTOR_RPM", "FRAME_SIZE", "MOTOR_MFG",
                "SHAFT_GROUNDING", "PAINT_UPGRADE",
            ]]),
            ("COUPLING", "Coupling", [
                ["SIZE", "F_MOTORHPRPM", "FRAME_SIZE", "COUPLING_OPTION"],       # horizontal
                ["SIZE", "F_MOTORHPRPM", "F_FRAME_SIZE", "F_COUPLING_OPTION"],   # 5500
            ]),
            ("BASEPLATE", "Baseplate", [["SIZE", "FRAME_SIZE", "BASEPLATE_OPTION"]]),
            ("TAILPIPE", "Tailpipe", [["SIZE", "PUMP_MATERIAL", "WETTED_HARDWARE", "TAILPIPE_LENGTH"]]),
        ]
        for comp_code, label, field_sets in (MULTI_COMPONENTS if not _dean_priced else []):
            priced = None
            for cond_fields in field_sets:
                priced = _price_multi_condition(comp_code, label, cond_fields)
                if priced is not None:
                    pricing.append({"component": label, "amount": priced[0], "detail": priced[1]})
                    break
            # Motor is always part of a pump; the others (Coupling/Baseplate/
            # Tailpipe) apply when the config drives them. Track them so a
            # reviewer sees the priced-vs-C/F status per component.
            if priced is not None:
                _add_component(label, None, priced[0], priced[1])
            else:
                _add_component(label, None, None)

        # For DEAN, `total` was already summed in the Dean branch above; recompute
        # for Fybroc (and harmlessly re-affirm for Dean) from the priced lines.
        total = sum(p["amount"] for p in pricing)

        # ---- U130: BOM generation (grounded, deterministic from configuration) ----
        # The BOM is the physical-build identity: same BOM -> same PN -> same SKU.
        # We generate it in SQL from the resolved segments, merging the priced
        # components (BASE_PUMP, SEAL) we just looked up (real cost + lineage).
        # The BOM signature is computed over STRUCTURAL line identity only
        # (component code + attributes + qty + uom), price EXCLUDED. Python
        # recomputes the same signature as a parity oracle.
        configured_product_id = sql_row[4]
        bom = None
        if family_upper != "DEAN":

            # Priced lines for SQL to merge onto matching structural lines.
            priced_payload = []
            for p in pricing:
                comp = p.get("component", "")
                if comp.startswith("Base Pump"):
                    code = "BASE_PUMP"
                elif comp == "Seal":
                    code = "SEAL"
                else:
                    continue
                priced_payload.append({
                    "component_code": code,
                    "unit_cost": p.get("amount"),
                    "source_reference": str(p.get("detail") or "")[:200],
                })

            # Structural lines (must mirror cfg.usp_GenerateBOM exactly).
            def _line(code, attrs, desc, qty=1, uom="EA"):
                return {"component_code": code, "attributes": attrs,
                        "description": desc, "quantity": qty, "uom": uom}
            bom_lines = [
                _line("PUMP_ASSEMBLY", f"{series_code}{size_code}{material_code}{trim_code}",
                      f"Pump assembly {series_code}{size_code}{material_code}{trim_code}"),
                _line("PUMP_OPTIONS", pump_opts, f"Pump options {pump_opts}"),
            ]
            if not is_vertical:
                bom_lines.append(_line("SEAL_ASSEMBLY", f"{seal_mfg}{seal_assy}",
                                       f"Seal assembly {seal_mfg}{seal_assy}"))
            bom_lines += [
                _line("OPTIONS", options_code, f"Options {options_code}"),
                _line("MOTOR_ASSEMBLY", f"{frame_size}{motor_assy}",
                      f"Motor assembly {frame_size}{motor_assy}"),
                _line("MOTOR_MODS", motor_mods, f"Motor modifications {motor_mods}"),
                _line("TESTING", testing, f"Testing {testing}"),
            ]
            # Canonical BOM signature (parity oracle): sorted lower('code|attrs|qty|uom'),
            # joined by newline, SHA-256 hex upper. Must match cfg.usp_GenerateBOM.
            def _fmt_qty(q):
                return f"{q:.3f}"
            line_keys = sorted(
                f"{l['component_code']}|{l['attributes']}|{_fmt_qty(l['quantity'])}|{l['uom']}".lower()
                for l in bom_lines
            )
            py_bom_signature = hashlib.sha256("\n".join(line_keys).encode()).hexdigest().upper()

            bom = None
            if configured_product_id is not None:
                try:
                    bom_row = cursor.execute(
                        "EXEC cfg.usp_GenerateBOM @ConfiguredProductId=?, @IsVertical=?, "
                        "@SegmentsJson=?, @PricedJson=?, @CreatedBy=?;",
                        configured_product_id, 1 if is_vertical else 0,
                        segments_payload, json.dumps(priced_payload), body.requested_by,
                    ).fetchone()
                    sql_bom_signature = bom_row[1]
                    bom_parity_ok = (py_bom_signature == sql_bom_signature)
                    if not bom_parity_ok:
                        import logging
                        logging.getLogger("uvicorn.error").warning(
                            "BOM signature parity divergence: py=%r sql=%r (pn=%s)",
                            py_bom_signature, sql_bom_signature, pn,
                        )
                    bom = {
                        "bom_header_id": bom_row[0],
                        "bom_signature": sql_bom_signature,
                        "existing_bom": bool(bom_row[2]),
                        "line_count": bom_row[3],
                        "bom_parity_ok": bom_parity_ok,
                        "lines": bom_lines,
                    }
                except Exception as e:
                    import logging
                    logging.getLogger("uvicorn.error").warning("BOM generation failed: %s", e)

        return {
            "family": family_upper,
            "part_number": pn,
            "sku": sku,
            "configuration_signature": signature,
            "existing_configuration": bool(sql_row[3]),
            "configured_product_id": sql_row[4],
            "identity_authority": "sql",
            "parity_ok": parity_ok,
            "sku_pn_ok": sku_pn_ok,
            "bom": bom,
            "pricing": pricing,
            "component_pricing": component_pricing,
            "total_price": total,
            "segment_debug": segment_debug,
        }
    finally:
        conn.close()


# ===========================================================================
# U140 - QUOTE ENGINE
# ---------------------------------------------------------------------------
# A quote is a header + lines. Each line is anchored to a configured product
# (cfg.ConfiguredProduct) and its Active BOM (cfg.BOMHeader), and persists
# everything needed to reproduce the quote (PN, SKU, ConfigurationJson, BOM
# signature, qty, unit/extended price, pricing + publication lineage).
#
# The add-line endpoint reuses resolve_configured_product so the line's
# identity, BOM, and price all come from the one authoritative resolve flow.
# Unit price = the base+seal total we can price today; PricingStatus records
# whether the line is fully priced, partial, or call_for_price (honest about
# the components not yet priced). Rendering is a deterministic structured
# document (Excel formal-quote template is a later milestone).
# ===========================================================================


class CreateQuoteRequest(BaseModel):
    site_code: str
    customer_name: str | None = None
    customer_account: str | None = None
    currency_code: str = "USD"
    created_by: str | None = None
    quote_number: str | None = None


class AddQuoteLineRequest(BaseModel):
    series: str
    selections: dict[str, str]
    segment_codes: dict[str, str] = Field(default_factory=dict)
    quantity: int = 1
    requested_by: str | None = None


def _pricing_status(pricing: list[dict], selections: dict[str, str], is_vertical: bool) -> str:
    """Honest pricing status for a line given the components we can price today.

    We price BASE_PUMP always (pump identity) and SEAL when a mechanical seal is
    configured. 'found' = all expected priceable components resolved; 'partial' =
    some resolved but at least one expected component is missing; 'call_for_price'
    = nothing priced. Full component pricing is a later milestone, so a fully
    resolved base(+seal) is reported as 'found' for what is currently priceable.
    """
    have_base = any(p.get("component", "").startswith("Base Pump") for p in pricing)
    seal_expected = bool(selections.get("SEAL_TYPE")) and not is_vertical
    have_seal = any(p.get("component") == "Seal" for p in pricing)
    if not have_base and not have_seal:
        return "call_for_price"
    if seal_expected and not have_seal:
        return "partial"
    if not have_base:
        return "partial"
    return "found"


@router_v2.post("/families/{family}/quotes")
async def create_quote(family: str, body: CreateQuoteRequest, request: Request):
    """Create a quote header. Returns the quote id + number."""
    conn_str = _get_conn_str(request)
    conn = pyodbc.connect(conn_str, autocommit=True)
    try:
        row = conn.cursor().execute(
            "EXEC quote.usp_CreateQuote @SiteCode=?, @CustomerName=?, "
            "@CustomerAccount=?, @CurrencyCode=?, @CreatedBy=?, @QuoteNumber=?;",
            body.site_code, body.customer_name, body.customer_account,
            body.currency_code, body.created_by, body.quote_number,
        ).fetchone()
        result = {
            "quote_header_id": row[0], "quote_number": row[1], "site_code": row[2],
            "currency_code": row[3], "status": row[4], "created_at": str(row[5]),
        }
    finally:
        conn.close()

    try:
        from src.api.audit import log_audit_event  # optional; best-effort
        from src.api.auth import AuthenticatedUser
        _who = body.created_by or "system"
        log_audit_event(
            connection_string=conn_str,
            user=AuthenticatedUser(user_id=_who, display_name=_who, email="", roles=[]),
            action="create_quote", resource_type="quote",
            resource_id=str(result["quote_header_id"]),
            details={"quote_number": result["quote_number"], "site": body.site_code},
        )
    except Exception:
        pass
    return result


@router_v2.post("/families/{family}/quotes/{quote_header_id}/lines")
async def add_quote_line(family: str, quote_header_id: int,
                         body: AddQuoteLineRequest, request: Request):
    """Add a line to a quote from a configuration.

    Resolves the configuration through the authoritative resolve flow (identity +
    BOM + pricing), then persists a quote line anchored to the configured product
    and its Active BOM, with unit price = the base+seal total and an honest
    pricing status.
    """
    conn_str = _get_conn_str(request)

    # Reuse the one authoritative resolve flow.
    resolve_body = ResolveRequest(
        series=body.series, selections=body.selections,
        segment_codes=body.segment_codes, requested_by=body.requested_by,
    )
    resolved = await resolve_configured_product(family, resolve_body, request)

    configured_product_id = resolved.get("configured_product_id")
    unit_price = float(resolved.get("total_price") or 0.0)
    pricing = resolved.get("pricing", [])
    is_vertical = bool((resolved.get("segment_debug") or {}).get("is_vertical"))
    status = _pricing_status(pricing, body.selections, is_vertical)

    # Pricing + publication lineage persisted with the line for reproducibility.
    pricing_lineage = json.dumps({
        "components": pricing,
        "total_price": unit_price,
        "configuration_signature": resolved.get("configuration_signature"),
        "bom_signature": (resolved.get("bom") or {}).get("bom_signature"),
    }, sort_keys=True, separators=(",", ":"))

    conn = pyodbc.connect(conn_str, autocommit=True)
    try:
        pub_id, pub_version = _get_active_publication(conn_str, conn)
        row = conn.cursor().execute(
            "EXEC quote.usp_AddQuoteLine @QuoteHeaderId=?, @ConfiguredProductId=?, "
            "@SKU=?, @Quantity=?, @UnitPrice=?, @PricingStatus=?, @PricingLineage=?, "
            "@PublicationVersion=?, @PriceBookVersion=?;",
            quote_header_id, configured_product_id, resolved.get("sku"),
            body.quantity, unit_price, status, pricing_lineage,
            str(pub_version), None,
        ).fetchone()
        line = {
            "quote_line_id": row[0], "line_number": row[1], "part_number": row[2],
            "sku": row[3], "bom_header_id": row[4], "bom_signature": row[5],
            "quantity": row[6], "unit_price": float(row[7]),
            "extended_price": float(row[8]), "pricing_status": row[9],
        }
    finally:
        conn.close()

    try:
        from src.api.audit import log_audit_event
        from src.api.auth import AuthenticatedUser
        _who = body.requested_by or "system"
        log_audit_event(
            connection_string=conn_str,
            user=AuthenticatedUser(user_id=_who, display_name=_who, email="", roles=[]),
            action="add_quote_line", resource_type="quote_line",
            resource_id=str(line["quote_line_id"]),
            details={"quote": quote_header_id, "sku": line["sku"], "pn": line["part_number"]},
        )
    except Exception:
        pass
    return line


def _fetch_quote(conn, quote_header_id: int) -> dict:
    """Fetch a quote (header + lines) via quote.usp_GetQuote into a dict."""
    cur = conn.cursor()
    cur.execute("EXEC quote.usp_GetQuote @QuoteHeaderId=?;", quote_header_id)
    hcols = [c[0] for c in cur.description]
    hrow = cur.fetchone()
    if hrow is None:
        return {}
    header = dict(zip(hcols, hrow))
    cur.nextset()
    lcols = [c[0] for c in cur.description]
    lines = [dict(zip(lcols, r)) for r in cur.fetchall()]
    return {"header": header, "lines": lines}


def _quote_to_document(quote: dict) -> dict:
    """Build the deterministic, reproducible quote document (structured + text).

    Same persisted quote -> same document. No Excel/COM. The Excel formal-quote
    template render is a later milestone.
    """
    h = quote["header"]
    currency = h.get("CurrencyCode") or "USD"
    lines_out = []
    total = 0.0
    for ln in quote["lines"]:
        ext = float(ln.get("ExtendedPrice") or 0.0)
        total += ext
        lines_out.append({
            "line_number": ln.get("LineNumber"),
            "part_number": ln.get("PartNumber"),
            "sku": ln.get("SKU"),
            "family": ln.get("FamilyCode"),
            "quantity": ln.get("Quantity"),
            "unit_price": float(ln.get("UnitPrice") or 0.0),
            "extended_price": ext,
            "pricing_status": ln.get("PricingStatus"),
            "bom_signature": ln.get("BOMSignature"),
            "publication_version": ln.get("PublicationVersion"),
        })

    doc = {
        "quote_number": h.get("QuoteNumber"),
        "customer_name": h.get("CustomerName"),
        "customer_account": h.get("CustomerAccount"),
        "site_code": h.get("SiteCode"),
        "currency": currency,
        "status": h.get("Status"),
        "lines": lines_out,
        "total_price": total,
        "line_count": len(lines_out),
    }

    # Deterministic plain-text rendering (stable field order, no timestamps).
    txt = []
    txt.append(f"QUOTE {doc['quote_number']}   Site: {doc['site_code']}   Currency: {currency}")
    if doc["customer_name"]:
        txt.append(f"Customer: {doc['customer_name']}"
                   + (f" ({doc['customer_account']})" if doc["customer_account"] else ""))
    txt.append("-" * 72)
    txt.append(f"{'#':>2}  {'Part Number':<34} {'Qty':>4} {'Unit':>12} {'Ext':>12}  Status")
    for l in lines_out:
        txt.append(f"{l['line_number']:>2}  {l['part_number']:<34} {l['quantity']:>4} "
                   f"{l['unit_price']:>12.2f} {l['extended_price']:>12.2f}  {l['pricing_status']}")
    txt.append("-" * 72)
    txt.append(f"{'TOTAL':>54} {total:>12.2f} {currency}")
    doc["rendered_text"] = "\n".join(txt)
    return doc


@router_v2.get("/families/{family}/quotes/{quote_header_id}")
async def get_quote(family: str, quote_header_id: int, request: Request):
    """Return the persisted quote as a structured, rendered document."""
    conn_str = _get_conn_str(request)
    conn = pyodbc.connect(conn_str, autocommit=True)
    try:
        quote = _fetch_quote(conn, quote_header_id)
    finally:
        conn.close()
    if not quote:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Quote not found")
    return _quote_to_document(quote)

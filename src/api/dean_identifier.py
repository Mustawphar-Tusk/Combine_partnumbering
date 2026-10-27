"""D140 - Dean Part Number resolver (family-scoped identifier authority).

Resolves a Dean configuration (a dict of Dean SFO field_code -> value, plus
series/size) into the engineering-segment codes that make up the Dean Part
Number, then the full PN, mirroring the authoritative workbook
PumpConfiguration_Logic_0.1.xlsm numbering.

Storage this reads (all family-scoped, loaded by
scripts/load_dean_identifier_to_sql.py):
  - A#/D# identity: cfg.PumpModelReference (Series+Size -> BaseIdentifier=D<A#>)
  - segment String->Code maps: stg.SegmentCombinationImport (DEAN batch),
    matched EXACTLY on CombinationKey (the numbering sheet's '*'-joined String).

D140 RE-BASE (2026-08-26) onto PumpConfiguration_Logic_0.1.xlsm:
  * Field ORDER per segment now follows the new workbook's numbering-sheet option
    columns (see scripts/load_dean_identifier_to_sql.py SEGMENTS + PCL_V01
    structure). Wet End / Impeller / Power Frame / Baseplate re-ordered.
  * NO "N/A" collapse: the new workbook keeps literal option values (even under
    NONE); segments collapse only by the natural trailing-'*' trim. The old
    SEGMENT_NONE_COLLAPSE (which injected "N/A") is REMOVED.
  * Flush Plan is now TABLE-BACKED (its own numbering sheet). Resolved by looking
    up the plan's STD numbering row (lowest code for the FLUSH_PLAN), replacing
    the prior Config-Info FA->FH letter map.
  * Motor (2026 re-base onto "Motor Numbering.xlsm"): the motor PN group is the
    4-char Combined Alphanumeric Code resolved from the MOTOR_SPEC combination
    table (10 motor fields -> brand letter + 3-char base). This REPLACES the old
    inert frame-only motor code. FRAME_SIZE values are canonicalized (UPPER +
    VP->HP) so selections match the enumerated motor combinations.

Special (non-table) segments:
  - Impeller Trim  : inch-letter + decimal-letter (Impeller trim sub-table)
  - Seal           : IF seal not "Included" -> "00000" else "TBD__" (EXCLUDED from PN)

Retained-but-UNBUILT segments (no numbering table in v0.1 - documented gaps
DEAN_ENGINEERING_QUESTIONS.md §F; the resolver emits a fixed zero-padded
placeholder so the PN never errors and the slot is preserved):
  - Barrier Plan (F2 header-only) -> "0"
  - Cooling Plan (F1 empty sheet) -> "00"
  - Testing / Documentation / Additional Options (no sheet in v0.1) -> "00"/"0000"/"00"

The Dean PN (seal segment EXCLUDED - see below):
  D<A#>-<WetEnd(4)>-<Trim(2)><ImpOpts(2)>-<PowerEnd(4)>
    -<Flush(2)><Barrier(1)><Cooling(2)>-<Frame(2)><Baseplate(2)>
    -<Motor(4)>
  Motor is now the 4-char Combined Alphanumeric Code from the new Motor
  Numbering workbook (brand letter + 3-char base); it is the WHOLE motor group
  (the old separate 2-char motor-options slot is folded in / empty). Additional
  Options + Testing/Documentation are NOT PN drivers (2026-08-26); the PN ends at
  the motor group.

Seal is intentionally omitted from the PN: the seal code is authored only in the
external "Seal Numbering.accdb" (getSealOptions), which is unavailable, so the
workbook itself only ever emits the placeholder 00000/TBD__ for seal. Seal status
is still resolved into segment_debug (seal_status / seal_code_placeholder). If the
seal Access DB becomes available, seal can be re-added to the PN cleanly.

This module is the option-1 resolver: it computes the segment codes in Python
(the parity oracle) and returns the segments payload for
cfg.usp_AssembleConfiguredProduct (@FamilyCode='DEAN'), which is authoritative.
"""
from __future__ import annotations

import json
from pathlib import Path

# --- special-segment lookup maps (extracted from the workbook) ---------------
_SPECIAL_MAPS_PATH = Path(__file__).resolve().parents[2] / "config" / \
    "identifier_profiles" / "dean_special_maps.json"

try:
    _SPECIAL = json.loads(_SPECIAL_MAPS_PATH.read_text(encoding="utf-8"))
except Exception:
    _SPECIAL = {"trim_inch": {}, "trim_decimal": {}, "flush": {}, "barrier": {}}


# --- per-segment ComboString field order (in the NUMBERING SHEET's own column
#     order, which is what CombinationKey stores) -> Dean SFO field code.
#     None means the field has no direct Dean selection and defaults per the
#     numbering-table N/A collapse (we rely on the stored CombinationKey rows
#     containing the N/A form, so an exact match still succeeds).
#     Order verified against the loaded CombinationKey samples.
# ---------------------------------------------------------------------------
SEGMENT_FIELD_ORDER = {
    # Wet End Numbering (v0.1) option cols D..M (10 fields) - header order:
    # Pump Material, Casing Material, Casing Drain, Casing Taps, Casing Gasket,
    # Flange Configuration, Spot Facing, Casing Wear Ring, Casing Mounting,
    # Seal Chamber Config.
    "WET_END_OPTIONS": [
        "PUMP_MATERIAL",
        "CASING_MATERIAL",
        "CASING_DRAIN",
        "CASING_TAPS",
        "CASING_GASKET",
        "FLANGE_CONFIGURATION",
        "SPOT_FACING",
        "CASING_WEAR_RING",
        "CASING_MOUNTING",
        "SEAL_CHAMBER_CONFIG",
    ],
    # Impeller Numbering (v0.1) option cols D..F (3 fields):
    # Impeller Balance, Impeller Material, Impeller Wear Ring Material.
    "IMPELLER_OPTIONS": [
        "IMPELLER_BALANCE",
        "IMPELLER_MATERIAL",
        "IMPELLER_WEAR_RING_MATERIAL",
    ],
    # Power Frame Numbering (v0.1) option cols D..N (11 fields):
    # Shaft Configuration, Shaft Material, Bearing Lubrication, Bearing Seal,
    # Oiler Options, Sight Glass, Bearing Frame Cooling, Magnetic Drain,
    # Expansion Chamber, Coupling Type, Coupling Guard.
    "POWER_FRAME_OPTIONS": [
        "SHAFT_CONFIGURATION",
        "SHAFT_MATERIAL",
        "BEARING_LUBRICATION",
        "BEARING_SEAL",
        "OILER_OPTIONS",
        "SIGHT_GLASS",
        "BEARING_FRAME_COOLING",
        "MAGNETIC_DRAIN",
        "EXPANSION_CHAMBER",
        "COUPLING_TYPE",
        "COUPLING_GUARD",
    ],
    # Baseplate Numbering (v0.1) option cols D..L (9 fields):
    # Baseplate Type, Drip Pan, Alignment Lugs, Lifting Lugs, Levelling Screws,
    # Grounding Lug, Grout Hole, Isolation Pads, Stilts.
    "BASEPLATE_OPTIONS": [
        "BASEPLATE_TYPE",
        "DRIP_PAN",
        "ALIGNMENT_LUGS",
        "LIFTING_LUGS",
        "LEVELLING_SCREWS",
        "GROUNDING_LUG",
        "GROUT_HOLE",
        "ISOLATION_PADS",
        "STILTS",
    ],
    # Flush Plan Numbering (v0.1) combination cols D..H (5 fields), in column
    # order. All five are configurable (D110 Flush Plan option A); the combination
    # allow-list constrains them to the 185 enumerated flush combinations.
    "FLUSH_PLAN": [
        "FLUSH_PLAN",
        "FLUSH_PLAN_ROUTING",
        "FLUSH_CONNECTIONS",
        "FLUSH_TEMPERATURE_RANGE",
        "FLUSH_COOLING_MEDIA",
    ],
    # Motor Numbering (new "Motor Numbering.xlsm" Pricing sheet). The 10 motor
    # spec fields (combos column order S..AB) combine into the 4-char Combined
    # Alphanumeric Code (brand letter + 3-char base). CombinationKey is the
    # '*'-join of these 10 values, matching scripts/load_dean_motor_numbering.py.
    # 34,084 enumerated combinations are the motor allow-list; the code is the
    # motor PN segment (replaces the old inert frame-only motor). FRAME_SIZE is
    # canonicalized (UPPER + VP->HP) in SeriesFieldOption so the selected value
    # matches the stored key.
    "MOTOR_SPEC": [
        "MOTOR",
        "MOTOR_CONTROL",
        "FRAME_SIZE",
        "RATED_SPEED",
        "RATED_POWER",
        "VOLTAGE",
        "PHASE_FREQUENCY",
        "ENCLOSURE",
        "EFFICIENCY",
        "BRAND",
    ],
}

# Default token for each ComboString POSITION when the mapped Dean field is
# absent/blank. Keyed by (segment_code, position_index). Verified against the
# loaded numbering data (the token that appears for the "nothing selected" row).
# Positions not listed default to "NONE".
SEGMENT_POSITION_DEFAULT = {
    # v0.1 workbook literal "nothing selected" tokens per position (verified
    # against loaded rows). Flag-type fields default "Not Required"; list-type
    # fields default "NONE"; material/config fields default "NONE".
    # WET_END (10): 0 Pump Material, 1 Casing Material, 2 Casing Drain,
    # 3 Casing Taps, 4 Casing Gasket, 5 Flange Configuration, 6 Spot Facing,
    # 7 Casing Wear Ring, 8 Casing Mounting, 9 Seal Chamber Config.
    ("WET_END_OPTIONS", 2): "Not Required",  # Casing Drain
    ("WET_END_OPTIONS", 6): "Not Required",  # Spot Facing
    ("WET_END_OPTIONS", 7): "NONE",          # Casing Wear Ring
    ("WET_END_OPTIONS", 8): "Not Required",  # Casing Mounting
    ("WET_END_OPTIONS", 9): "NONE",          # Seal Chamber Config
    # POWER (11): flag fields -> Not Required; Oiler -> NONE.
    ("POWER_FRAME_OPTIONS", 4): "NONE",          # Oiler Options
    ("POWER_FRAME_OPTIONS", 5): "Not Required",  # Sight Glass
    ("POWER_FRAME_OPTIONS", 6): "Not Required",  # Bearing Frame Cooling
    ("POWER_FRAME_OPTIONS", 7): "Not Required",  # Magnetic Drain
    ("POWER_FRAME_OPTIONS", 8): "Not Required",  # Expansion Chamber
    # BASEPLATE (9): Drip Pan -> NONE; flag fields -> Not Required.
    ("BASEPLATE_OPTIONS", 1): "NONE",            # Drip Pan
    ("BASEPLATE_OPTIONS", 2): "Not Required",
    ("BASEPLATE_OPTIONS", 3): "Not Required",
    ("BASEPLATE_OPTIONS", 4): "Not Required",
    ("BASEPLATE_OPTIONS", 5): "Not Required",
    ("BASEPLATE_OPTIONS", 6): "Not Required",
    ("BASEPLATE_OPTIONS", 7): "Not Required",
    ("BASEPLATE_OPTIONS", 8): "Not Required",
}

# The v0.1 workbook does NOT use an "N/A" collapse: numbering rows keep literal
# option values even when a controller field is NONE (e.g. Baseplate NONE => the
# ComboString is simply "NONE" with the remaining columns trailing-'*' trimmed).
# So there is NO SEGMENT_NONE_COLLAPSE. The natural trailing-'*' trim in
# _build_combo, plus the BASEPLATE gate below, reproduce the NONE rows.
SEGMENT_NONE_COLLAPSE = {}

# Segments where any field == "Custom" collapses the whole segment to a padded
# custom placeholder (Module1/Module2 exclude Custom-containing rows).
SEGMENT_CUSTOM_PLACEHOLDER = {
    "WET_END_OPTIONS": "____",
    "IMPELLER_OPTIONS": "__",
    "POWER_FRAME_OPTIONS": "____",
    "BASEPLATE_OPTIONS": "__",
}

# Default token when a field position isn't in SEGMENT_POSITION_DEFAULT.
_GENERIC_DEFAULT = "NONE"

# segment width (mirrors the loaded ExpectedWidth / SQL CHECK) for v0.1.
SEGMENT_WIDTH = {
    "WET_END_OPTIONS": 4, "IMPELLER_OPTIONS": 2, "POWER_FRAME_OPTIONS": 4,
    "BASEPLATE_OPTIONS": 2, "FLUSH_PLAN": 2, "MOTOR_FRAME": 2,
    "MOTOR_SPEC": 4,
}

# Retained-but-UNBUILT segments (no numbering table in v0.1) -> fixed zero-padded
# placeholder so the PN never errors and the slot is preserved. NOT '?'.
UNBUILT_PLACEHOLDER = {
    "BARRIER_PLAN": "0",
    "COOLING_PLAN": "00",
    "TESTING": "00",
    "DOCUMENTATION": "0000",
    "ADDITIONAL_OPTIONS": "00",
    "MOTOR_OPTIONS": "00",   # motor-options inert in the workbook
}

# placeholder emitted when a table-backed segment can't be resolved (mirrors the
# workbook "ERR"); the API surfaces this in failed_segments.
def _err(width):
    return "?" * width


def _norm(v):
    return "" if v is None else str(v).strip()


def base_identifier(cursor, series, size):
    """D<A#> for (series,size) from cfg.PumpModelReference (DEAN). None if absent."""
    row = cursor.execute(
        "SELECT BaseIdentifier FROM cfg.PumpModelReference "
        "WHERE PumpFamilyId = (SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode='DEAN') "
        "  AND IsActive = 1 AND UPPER(SeriesCode) = ? AND UPPER(SizeCode) = ?",
        _norm(series).upper(), _norm(size).upper(),
    ).fetchone()
    return row[0] if row else None


_DEAN_BATCH_ID = None  # cached DEAN 'Loaded' batch id (per process)


def _dean_batch_id(cursor):
    global _DEAN_BATCH_ID
    if _DEAN_BATCH_ID is None:
        row = cursor.execute(
            "SELECT TOP 1 ImportBatchId FROM stg.SegmentCombinationImportBatch "
            "WHERE FamilyCode='DEAN' AND Status='Loaded' ORDER BY ImportBatchId DESC"
        ).fetchone()
        _DEAN_BATCH_ID = int(row[0]) if row else -1
    return _DEAN_BATCH_ID


def _seg_lookup(cursor, segment_code, combo_string):
    """Exact CombinationKey lookup against the DEAN segment batch. Matches on the
    persisted CombinationKeyHash so it uses UX_SegmentCombinationImport_KeyHash
    (ImportBatchId, SegmentCode, CombinationKeyHash) - an index seek, not a scan
    of the 428K-row table."""
    bid = _dean_batch_id(cursor)
    if bid < 0:
        return None
    row = cursor.execute(
        "SELECT TOP 1 SegmentValue FROM stg.SegmentCombinationImport "
        "WHERE ImportBatchId = ? AND SegmentCode = ? "
        "  AND CombinationKeyHash = CONVERT(binary(32), "
        "        HASHBYTES('SHA2_256', CONVERT(varbinary(max), CAST(? AS nvarchar(2000))))) "
        "ORDER BY SourceId",
        bid, segment_code, combo_string,
    ).fetchone()
    return row[0] if row else None


def _has_custom(selections, segment_code):
    """True if any mapped field for this segment is 'Custom' (Module2 excludes it)."""
    for fld in SEGMENT_FIELD_ORDER[segment_code]:
        if fld and _norm(selections.get(fld, "")).lower() == "custom":
            return True
    return False


def _build_combo(selections, segment_code):
    """Build the '*'-joined ComboString in the numbering sheet's column order,
    applying per-position default tokens for unset fields, then trailing-'*'
    trimming, so the string matches the workbook's enumerated CombinationKey.
    The v0.1 workbook uses NO "N/A" collapse - just literal values + trailing
    trim (see SEGMENT_NONE_COLLAPSE docstring)."""
    order = SEGMENT_FIELD_ORDER[segment_code]
    parts = []
    for i, fld in enumerate(order):
        val = _norm(selections.get(fld, "")) if fld else ""
        if val == "":
            val = SEGMENT_POSITION_DEFAULT.get((segment_code, i), _GENERIC_DEFAULT)
        parts.append(val)
    combo = "*".join(parts)
    while combo.endswith("*"):     # Module1/Module2 trailing-'*' trim
        combo = combo[:-1]
    return combo


def _seg_parts(selections, segment_code):
    """The per-position values (in SEGMENT_FIELD_ORDER column order, defaults
    applied) WITHOUT the trailing-'*' trim - used to score nearest enumerated
    combinations. Lowercased to match the stored CombinationKey tokens."""
    order = SEGMENT_FIELD_ORDER[segment_code]
    parts = []
    for i, fld in enumerate(order):
        val = _norm(selections.get(fld, "")) if fld else ""
        if val == "":
            val = SEGMENT_POSITION_DEFAULT.get((segment_code, i), _GENERIC_DEFAULT)
        parts.append(str(val).strip().lower())
    return parts


def _nearest_seg_code(cursor, segment_code, selections):
    """NUMBERING-ONLY nearest-combination fallback for a table-backed segment.

    When the selected/STD-seeded combination for a segment is NOT one of the
    enumerated numbering rows (two authoritative sheets disagree - e.g. Pump
    Constraints marks CASING_MOUNTING='Yoke Foot' standard for RA3146, but the Wet
    End Numbering sheet only codes that wet-end config with 'Not Required' /
    'Required'), the exact lookup returns nothing and the segment would be '????'.

    Per the product decision (option A), the displayed configuration keeps its
    authoritative Pump-Constraints STD value; only the PART NUMBER snaps to the
    NEAREST enumerated combination so the segment always resolves to a real,
    buildable code. 'Nearest' = the coded row agreeing on the most positions, with
    the segment's FIRST field (material/anchor) weighted, ties broken to the
    earliest (standard) sheet row - identical scoring to the API's
    _dean_std_combo_autoadjust, so the two stay consistent. This NEVER invents a
    code: it always returns an enumerated row's code (or None if the segment has
    no rows at all). selections are NOT mutated.
    """
    bid = _dean_batch_id(cursor)
    if bid < 0:
        return None
    rows = cursor.execute(
        "SELECT CombinationKey, SegmentValue, SourceId FROM stg.SegmentCombinationImport "
        "WHERE ImportBatchId = ? AND SegmentCode = ?", bid, segment_code,
    ).fetchall()
    if not rows:
        return None
    want = _seg_parts(selections, segment_code)        # lowercased positions
    n = len(want)
    best_code = None
    best_score = None
    for ck, code, sid in rows:
        # CombinationKey tokens are stored original-cased; lowercase to compare
        # with the lowercased `want` positions (case-insensitive match).
        parts = [p.strip().lower() for p in str(ck).split("*")]
        parts += [""] * (n - len(parts))               # pad (trailing-* trimmed keys)
        anchor = 3 if (n and parts[0] == want[0]) else 0
        matches = sum(1 for i in range(n) if parts[i] == want[i])
        score = (anchor, matches, -int(sid or 0))      # tie -> earliest SourceId
        if best_score is None or score > best_score:
            best_score = score
            best_code = code
    return best_code


def resolve_trim(selections):
    """Impeller Trim (2 chars): inch-letter + decimal-letter of IMPELLER_TRIM.
    Handles bare integers ('4' -> 4",.000") and decimals ('4.125' -> 4",.125")."""
    raw = _norm(selections.get("IMPELLER_TRIM", ""))
    if not raw or raw.lower() == "custom":
        return "??"
    if "." in raw:
        inch_num = raw[: raw.find(".")]
        frac = raw[raw.find(".") + 1:].rstrip('"')
        # normalize the fractional part to 3 digits (".5" -> ".500", ".125" -> ".125")
        frac3 = (frac + "000")[:3] if frac else "000"
        dec = "." + frac3
    else:
        inch_num = raw
        dec = ".000"
    inch_part = inch_num + '"'
    dec_part = dec + '"'
    inch = _SPECIAL.get("trim_inch", {}).get(inch_part)
    dec_code = _SPECIAL.get("trim_decimal", {}).get(dec_part)
    if inch and dec_code:
        return inch + dec_code
    return "??"


def resolve_seal(selections):
    """Seal (5 chars): 00000 unless seal Included -> TBD__ (external seal DB)."""
    seal_opt = _norm(selections.get("SEAL_OPTION", ""))
    return "TBD__" if seal_opt.lower() == "included" else "00000"


def resolve_flush(cursor, selections):
    """Flush Plan (2): TABLE-BACKED against the Flush Plan Numbering sheet (v0.1).

    The workbook enumerates one row per (Flush Plan x routing x connections x
    temperature x cooling-media). We receive only FLUSH_PLAN from the SFO, so we
    resolve to that plan's STANDARD numbering row = the lowest Alphanumeric Code
    among rows whose ComboString begins with the plan value. NONE/blank -> the
    'NONE' row (code '00'). If the plan has no numbering row, emit the padded
    no-flush code '00' (retained, never '?': flush is not a disclosed-gap
    segment)."""
    plan = _norm(selections.get("FLUSH_PLAN", ""))
    if plan == "" or plan.upper() in ("NONE", "N/A"):
        code = _seg_lookup(cursor, "FLUSH_PLAN", "NONE")
        return code if code else "00"
    bid = _dean_batch_id(cursor)
    if bid < 0:
        return "00"
    # EXACT-combination resolution (D110 Flush Plan option A): when the four flush
    # sub-fields are selected, resolve to the code for that precise (plan, routing,
    # connections, temperature, cooling-media) combination by matching the full
    # CombinationKey. The sub-fields are now configurable and constrained to the
    # 185 enumerated flush combinations, so a complete flush config always has an
    # exact coded row.
    sub = [_norm(selections.get(f, "")) for f in (
        "FLUSH_PLAN_ROUTING", "FLUSH_CONNECTIONS",
        "FLUSH_TEMPERATURE_RANGE", "FLUSH_COOLING_MEDIA")]
    if all(s != "" for s in sub):
        combo_key = "*".join([plan] + sub)
        while combo_key.endswith("*"):      # mirror the loader's trailing-* trim
            combo_key = combo_key[:-1]
        exact = cursor.execute(
            "SELECT TOP 1 SegmentValue FROM stg.SegmentCombinationImport "
            "WHERE ImportBatchId = ? AND SegmentCode = 'FLUSH_PLAN' "
            "  AND CombinationKey = ? ORDER BY SegmentValue",
            bid, combo_key,
        ).fetchone()
        if exact:
            return exact[0]
        # no exact row -> fall through to the plan STD row (never invent a code)

    # STD row for the plan = lowest code whose combo starts with "<plan>*" or == plan
    row = cursor.execute(
        "SELECT TOP 1 SegmentValue FROM stg.SegmentCombinationImport "
        "WHERE ImportBatchId = ? AND SegmentCode = 'FLUSH_PLAN' "
        "  AND (CombinationKey = ? OR CombinationKey LIKE ?) "
        "ORDER BY SegmentValue",
        bid, plan, plan.replace("[", "[[]").replace("%", "[%]").replace("_", "[_]") + "*%",
    ).fetchone()
    return row[0] if row else "00"


def resolve_motor_frame(cursor, selections):
    """Motor Frame (2): TABLE-BACKED against the Motor Frame-Size sub-table
    (v0.1). FRAME_SIZE -> 2-char code. No frame selected -> gated '00'."""
    frame = _norm(selections.get("FRAME_SIZE", ""))
    if frame == "" or frame.upper() in ("NONE", "N/A"):
        return "00"
    code = _seg_lookup(cursor, "MOTOR_FRAME", frame)
    return code if code else "00"


def _canon_frame(v):
    """Canonical FRAME_SIZE for MOTOR_SPEC key matching (UPPER + VP->HP), mirroring
    scripts/load_dean_motor_numbering.canon_frame. The SeriesFieldOption FRAME_SIZE
    values are already canonicalized, but normalize defensively here too."""
    import re
    return re.sub(r"VP$", "HP", _norm(v).upper())


def resolve_motor_spec(cursor, selections):
    """Motor (4): the new multi-field motor spec -> 4-char Combined Alphanumeric
    Code (brand letter + 3-char base), via the MOTOR_SPEC combination table
    (Motor Numbering.xlsm). Builds the CombinationKey as the '*'-join of the 10
    motor fields in MOTOR_SPEC order (FRAME_SIZE canonicalized), matches it
    exactly against the loaded combos, and returns the code. A non-enumerated
    combination (incomplete selection, or one of the 21 big frames with no motor
    combo) returns the fixed '0000' placeholder - the PN stays clean and the
    Contact-Factory story is carried by pricing, not a '????' PN error."""
    order = SEGMENT_FIELD_ORDER["MOTOR_SPEC"]
    parts = []
    for fld in order:
        val = _canon_frame(selections.get(fld, "")) if fld == "FRAME_SIZE" \
            else _norm(selections.get(fld, ""))
        parts.append(val)
    # All 10 motor fields must be present to form a real combination; if any is
    # blank the motor is not fully specified -> placeholder.
    if any(p == "" for p in parts):
        return "0000"
    combo = "*".join(parts)
    code = _seg_lookup(cursor, "MOTOR_SPEC", combo)
    return code if code else "0000"


def resolve_segments(cursor, series, size, selections):
    """Resolve every Dean PN segment. Returns (segments_payload_dict, debug_dict).

    segments_payload keys match cfg.usp_AssembleConfiguredProduct @FamilyCode=DEAN.
    """
    base = base_identifier(cursor, series, size) or ("D" + "?" * 4)

    # Segments that snap the PART NUMBER to the nearest enumerated combination
    # when the exact (STD/selected) combination is not coded (option A: the
    # displayed config keeps its authoritative Pump-Constraints STD; only the PN
    # uses the nearest buildable code, so these segments never emit '????').
    _NEAREST_SNAP_SEGMENTS = {"WET_END_OPTIONS", "POWER_FRAME_OPTIONS",
                              "BASEPLATE_OPTIONS"}

    # --- table-backed segments (exact CombinationKey match, v0.1 numbering) ---
    def table(seg):
        # Custom selection -> the workbook's padded custom placeholder (segment
        # excluded from the enumerated numbering table).
        cust = SEGMENT_CUSTOM_PLACEHOLDER.get(seg)
        if cust and _has_custom(selections, seg):
            return cust
        combo = _build_combo(selections, seg)
        code = _seg_lookup(cursor, seg, combo)
        if code:
            return code
        # Exact combo not enumerated. For the snap segments, resolve the PN to the
        # nearest enumerated combination's code (option A) so the segment is never
        # '????'; other segments keep the error placeholder.
        if seg in _NEAREST_SNAP_SEGMENTS:
            near = _nearest_seg_code(cursor, seg, selections)
            if near:
                return near
        return _err(SEGMENT_WIDTH[seg])

    wet_end = table("WET_END_OPTIONS")
    imp_opts = table("IMPELLER_OPTIONS")
    # Power Frame is a table-backed segment like wet-end: its enumerated
    # combinations are the allow-list (enforced + STD-auto-adjusted by the API's
    # _apply_constraints / _dean_std_combo_autoadjust), so a resolved config
    # always carries a coded power-frame combination.
    power = table("POWER_FRAME_OPTIONS")

    # --- gated table-backed baseplate (v0.1: BASEPLATE=NONE row = code '00') ---
    baseplate_type = _norm(selections.get("BASEPLATE_TYPE", ""))
    if baseplate_type.upper() == "NONE" or baseplate_type == "":
        baseplate = "00"
    else:
        baseplate = table("BASEPLATE_OPTIONS")

    # --- table-backed flush + motor-frame (v0.1 own numbering sheets) ---
    flush = resolve_flush(cursor, selections)
    frame = resolve_motor_frame(cursor, selections)

    # --- retained-but-UNBUILT segments (no numbering table in v0.1). Fixed
    #     placeholders keep the PN error-free and the slot preserved (gaps F1/F2
    #     + no-sheet Testing/Documentation/Additional Options). ---
    cooling = UNBUILT_PLACEHOLDER["COOLING_PLAN"]
    barrier = UNBUILT_PLACEHOLDER["BARRIER_PLAN"]
    testing = UNBUILT_PLACEHOLDER["TESTING"]
    documentation = UNBUILT_PLACEHOLDER["DOCUMENTATION"]
    addl = UNBUILT_PLACEHOLDER["ADDITIONAL_OPTIONS"]

    # --- MOTOR (new Motor Numbering.xlsm): the 10-field motor spec resolves to a
    #     4-char Combined Alphanumeric Code via the MOTOR_SPEC combination table.
    #     The whole motor group IS this code now (motor_options folded in -> ''),
    #     so the PN motor group is a single 4-char segment. A combination that is
    #     NOT enumerated (e.g. a frame with no motor combo - the 21 big frames, or
    #     an incomplete motor selection) emits a fixed '0000' placeholder rather
    #     than the '????' error marker, so the PN stays clean; the C/F story is
    #     carried by pricing (price.DeanMotorPrice), not a broken PN. ---
    motor = resolve_motor_spec(cursor, selections)
    motor_options = ""

    # --- special segments ---
    trim = resolve_trim(selections)
    seal = resolve_seal(selections)

    # NOTE: seal is resolved (00000/TBD__) for reference but is OMITTED from the
    # Dean PN - the seal code is authored only in the external Seal Numbering
    # Access DB (unavailable), so the workbook never puts a real code here. Seal
    # status is surfaced in segment_debug; the PN excludes it. (D130, 2026-08-26.)
    payload = {
        "base_identifier": base,
        "wet_end": wet_end,
        "impeller_trim": trim,
        "impeller_options": imp_opts,
        "power_frame_options": power,
        "flush_plan": flush,
        "barrier_plan": barrier,
        "cooling_plan": cooling,
        "frame_size": frame,
        "baseplate_options": baseplate,
        "motor": motor,
        "motor_options": motor_options,
        "additional_options": addl,
        "testing": testing,
        "documentation": documentation,
    }

    # Python parity-oracle PN (must equal the SQL assembler's output). Seal excluded.
    # ADDITIONAL OPTIONS and TESTING & DOCUMENTATION are NOT part-number drivers
    # (engineering decision 2026-08-26): they are still resolved into the payload/
    # debug for reference, but the PN ends at the motor group - the trailing
    # '-{addl}-{testing}{documentation}' groups are intentionally omitted. The SQL
    # assembler's DEAN branch drops the same two groups so python==SQL parity holds.
    py_pn = (
        f"{base}-{wet_end}-{trim}{imp_opts}-{power}"
        f"-{flush}{barrier}{cooling}-{frame}{baseplate}"
        f"-{motor}{motor_options}"
    )

    failed = [k for k, v in payload.items() if "?" in str(v)]
    # seal status (out-of-band; not in PN). "included_external_db" => code comes
    # from the external Seal Numbering DB (pending); "none" => no seal.
    seal_status = "included_external_db" if seal == "TBD__" else "none"
    debug = {**payload, "seal_status": seal_status, "seal_code_placeholder": seal,
             "py_pn": py_pn, "failed_segments": failed}
    return payload, debug


def assemble_pn(payload):
    """Assemble the Dean PN from a segments payload (mirror of the SQL branch).
    Seal is excluded from the PN (see resolve_segments)."""
    return (
        f"{payload['base_identifier']}"
        f"-{payload['wet_end']}"
        f"-{payload['impeller_trim']}{payload['impeller_options']}"
        f"-{payload['power_frame_options']}"
        f"-{payload['flush_plan']}{payload['barrier_plan']}{payload['cooling_plan']}"
        f"-{payload['frame_size']}{payload['baseplate_options']}"
        f"-{payload['motor']}{payload['motor_options']}"
        # additional_options + testing/documentation are NOT PN drivers (dropped
        # per engineering decision 2026-08-26); PN ends at the motor group.
    )

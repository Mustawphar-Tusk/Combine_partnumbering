"""D130 - Dean Part Number resolver (family-scoped identifier authority).

Resolves a Dean configuration (a dict of Dean SFO field_code -> value, plus
series/size) into the engineering-segment codes that make up the Dean Part
Number, then the full PN, mirroring the workbook Smart Number!B5 + J5 formulas.

Storage this reads (all family-scoped, loaded by
scripts/load_dean_identifier_to_sql.py):
  - A#/D# identity: cfg.PumpModelReference (Series+Size -> BaseIdentifier=D<A#>)
  - segment String->Code maps: stg.SegmentCombinationImport (DEAN batch),
    matched EXACTLY on CombinationKey (the numbering sheet's '*'-joined String).

Special (non-table) segments per the Smart Number trace:
  - Impeller Trim  : inch-letter + decimal-letter (Smart Number B31:C43 / E34:F41)
  - Seal           : IF seal not "Included" -> "00000" else "TBD__"
  - Flush / Barrier: Config Info FA->FH / FK->FN lookup maps
  - Motor Frame    : gated -> "00" when no motor (full BASE(MATCH) matrix pending)
  - Motor          : gated -> "0000" when motor option != "Included"
  - Baseplate      : gated -> "000" when Baseplate Type = "NONE"
  - Motor Options  : inert in the workbook (static "00")

The Dean PN (seal segment EXCLUDED - see below):
  D<A#>-<WetEnd(4)>-<Trim(2)><ImpOpts(2)>-<PowerEnd(3)>
    -<Flush(2)><Barrier><Cooling(2)>-<Frame(2)><Baseplate(3)>
    -<Motor(3)><MotorOpts(2)>-<AddlOpts(2)>-<Testing(2)><Doc(4)>

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
    # Wet End Numbering String col O (12 fields)
    "WET_END_OPTIONS": [
        "PUMP_MATERIAL",        # Pump Material Class
        "CASING_MATERIAL",      # Casing Material
        "FLANGE_CONFIGURATION", # Flange Style
        "CASING_TAPS",          # Casing Taps
        "CASING_DRAIN",         # Drain Options
        "CASING_MOUNTING",      # Casing Mount
        "CASING_GASKET",        # Casing Gasket
        "SHIPPING_GASKET",      # Shipping Gasket
        "CASING_WEAR_RING",     # Wear Ring Material
        "TACK_WELD_WEAR_RINGS", # Tack weld wear rings
        "SEAL_CHAMBER_CONFIG",  # Seal Chamber Config
        "SPOT_FACING",          # Spot-Facing
    ],
    # Wet End Numbering String col AJ (impeller sub-table). Sheet order observed:
    # Material*Balance*WearRing*BalanceHoles
    "IMPELLER_OPTIONS": [
        "IMPELLER_MATERIAL",
        "IMPELLER_BALANCE",
        "IMPELLER_WEAR_RING_MATERIAL",
        None,  # Balance Holes (no direct Dean SFO field; workbook static)
    ],
    # Power End Numbering String col N (11 fields)
    "POWER_FRAME_OPTIONS": [
        "SHAFT_CONFIGURATION",
        "SHAFT_MATERIAL",
        "BEARING_LUBRICATION",  # Lubrication Options
        "OILER_OPTIONS",
        "BEARING_SEAL",         # Oil Seal
        "SIGHT_GLASS",
        "MAGNETIC_DRAIN",
        "EXPANSION_CHAMBER",
        "BEARING_FRAME_COOLING",
        "COUPLING_GUARD",
        "COUPLING_TYPE",
    ],
    # Misc Numbering cooling String col G (3 fields)
    "COOLING_PLAN": [
        "COOLING_PLAN",
        None,  # Cooling Plan Piping (derived)
        None,  # Cooling Plan Extras (derived)
    ],
    # Misc Numbering addl String col P (5 fields)
    "ADDITIONAL_OPTIONS": [
        "SHIPPING_GASKET",
        "AUXILLARY_NAMEPLATE",
        "CRATING",
        "PAINT_OPTIONS",
        "COATING",
    ],
    # Baseplate Numbering cols C..K (9 fields)
    "BASEPLATE_OPTIONS": [
        "BASEPLATE_TYPE",
        None,  # Drip Pan (DRIP_PAN field exists on some series; mapped below)
        "ALIGNMENT_LUGS",
        "LIFTING_LUGS",
        "LEVELLING_SCREWS",
        "GROUNDING_LUG",
        "GROUT_HOLE",
        "ISOLATION_PADS",
        "STILTS",
    ],
    # Test and Doc Numbering testing String col I (5 fields)
    "TESTING": [
        "PERFORMANCE_TESTING",
        "HYDROTEST",
        "GENERAL_INSPECTION",
        "VIBRATION",
        "SOUND_LEVEL",
    ],
    # Test and Doc Numbering documentation String col S (4 fields)
    "DOCUMENTATION": [
        "DOCUMENT_1",
        "DOCUMENT_2",
        "DOCUMENT_3",
        "DOCUMENT_4",
    ],
    # Motor Numbering String col O (11 fields)
    "MOTOR": [
        "MOTOR_OPTION",
        "MOTOR_CONTROL",
        "MOTOR_FRAME_LIST",
        "MOTOR_RATED_SPEED",
        "MOTOR_RATED_POWER",
        "MOTOR_VOLTAGE",
        "MOTOR_PHASE_FREQUENCY",
        "MOTOR_POLES",
        "MOTOR_ENCLOSURE",
        "MOTOR_EFFICIENCY",
        "MOTOR_BRAND",
    ],
}

# Some ComboString fields have a Dean SFO field under a different code; map here.
FIELD_ALIASES = {
    "DRIP_PAN": "DRIP_PAN",
}

# Default token for each ComboString POSITION when the mapped Dean field is
# absent/blank. Keyed by (segment_code, position_index). Verified against the
# loaded numbering data (the token that appears for the "nothing selected" row).
# Positions not listed default to "NONE".
SEGMENT_POSITION_DEFAULT = {
    # WET_END: Casing Taps (idx3) default is "No Taps"; flags -> Not Required;
    # material/config lists -> NONE. (Drain/Mount come from selections.)
    # NOTE: "No Taps" is the numbering-table standard value for Casing Taps even
    # though D110 applicability does not offer it (it only offers Custom / NPT*).
    # This is the documented D110-vs-numbering STD data gap (see DEAN_D130_EXIT).
    ("WET_END_OPTIONS", 3): "No Taps",       # Casing Taps
    ("WET_END_OPTIONS", 7): "Not Required",  # Shipping Gasket
    ("WET_END_OPTIONS", 9): "Not Required",  # Tack weld wear rings
    ("WET_END_OPTIONS", 11): "Not Required", # Spot-Facing
    # IMPELLER: Balance Holes (idx3) static "Not Required"
    ("IMPELLER_OPTIONS", 3): "Not Required",
    # POWER: Shaft Material (idx1) numbering-standard = "Steel" (D110 offers only
    # Custom for some series -> documented STD data gap). Flags -> Not Required.
    ("POWER_FRAME_OPTIONS", 1): "Steel",         # Shaft Material
    ("POWER_FRAME_OPTIONS", 5): "Not Required",  # Sight Glass
    ("POWER_FRAME_OPTIONS", 6): "Not Required",  # Magnetic Drain
    ("POWER_FRAME_OPTIONS", 7): "Not Required",  # Expansion Chamber
    ("POWER_FRAME_OPTIONS", 8): "Not Required",  # Bearing Frame Cooling
    # ADDITIONAL: Crating/Paint default "Standard"; gaskets/nameplate/coating -> Not Required/NONE
    ("ADDITIONAL_OPTIONS", 0): "Not Required",   # Shipping Gasket
    ("ADDITIONAL_OPTIONS", 1): "Not Required",   # Auxillary Nameplate
    ("ADDITIONAL_OPTIONS", 2): "Standard",       # Crating
    ("ADDITIONAL_OPTIONS", 3): "Standard",       # Paint Options
    ("ADDITIONAL_OPTIONS", 4): "Not Required",   # Coating
    # BASEPLATE flag fields -> Not Required
    ("BASEPLATE_OPTIONS", 2): "Not Required",
    ("BASEPLATE_OPTIONS", 3): "Not Required",
    ("BASEPLATE_OPTIONS", 4): "Not Required",
    ("BASEPLATE_OPTIONS", 5): "Not Required",
    ("BASEPLATE_OPTIONS", 6): "Not Required",
    ("BASEPLATE_OPTIONS", 7): "Not Required",
    ("BASEPLATE_OPTIONS", 8): "Not Required",
}

# NONE->N/A structural collapse (Module2 numbering enumeration). When the
# CONTROLLER position holds "NONE", the DEPENDENT positions collapse to "N/A".
# Verified against the loaded data (e.g. Wet End Casing Material=NONE ->
# Flange/Taps/Drain/Mount = N/A; Cooling Plan=NONE -> Piping/Extras = N/A).
SEGMENT_NONE_COLLAPSE = {
    "WET_END_OPTIONS": (1, [2, 3, 4, 5]),   # Casing Material NONE -> Flange,Taps,Drain,Mount
    "IMPELLER_OPTIONS": (0, [1, 2, 3]),     # Impeller Material NONE -> Balance,WearRing,BalHoles
    "COOLING_PLAN": (0, [1, 2]),            # Cooling Plan NONE -> Piping,Extras
    "BASEPLATE_OPTIONS": (0, [1, 2, 3, 4, 5, 6, 7, 8]),  # Baseplate Type NONE -> all deps
}

# Segments where any field == "Custom" collapses the whole segment to a padded
# custom placeholder (Module2 excludes Custom; Smart Number COUNTIFS(...,"Custom")).
SEGMENT_CUSTOM_PLACEHOLDER = {
    "WET_END_OPTIONS": "____",
    "IMPELLER_OPTIONS": "__",
}

# Default token when a field position isn't in SEGMENT_POSITION_DEFAULT.
_GENERIC_DEFAULT = "NONE"

# segment width (mirrors the loaded ExpectedWidth / SQL CHECK)
SEGMENT_WIDTH = {
    "WET_END_OPTIONS": 4, "IMPELLER_OPTIONS": 2, "POWER_FRAME_OPTIONS": 2,
    "COOLING_PLAN": 2, "ADDITIONAL_OPTIONS": 2, "BASEPLATE_OPTIONS": 3,
    "TESTING": 2, "DOCUMENTATION": 4, "MOTOR": 3,
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
    applying (1) per-position default tokens for unset fields and (2) the
    Module2 NONE->N/A structural collapse, so the string matches the workbook's
    enumerated key. See SEGMENT_POSITION_DEFAULT / SEGMENT_NONE_COLLAPSE."""
    order = SEGMENT_FIELD_ORDER[segment_code]
    parts = []
    for i, fld in enumerate(order):
        val = _norm(selections.get(fld, "")) if fld else ""
        if val == "":
            val = SEGMENT_POSITION_DEFAULT.get((segment_code, i), _GENERIC_DEFAULT)
        parts.append(val)

    # NONE -> N/A structural collapse: if the controller position is NONE, the
    # dependent positions become N/A (matching the numbering-table rows).
    collapse = SEGMENT_NONE_COLLAPSE.get(segment_code)
    if collapse:
        ctrl_idx, dep_idxs = collapse
        if ctrl_idx < len(parts) and parts[ctrl_idx].upper() == "NONE":
            for di in dep_idxs:
                if di < len(parts):
                    parts[di] = "N/A"
    return "*".join(parts)


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


def resolve_flush(selections):
    """Flush (2): Config Info FA(letter)->FH(base-36).

    The workbook derives the flush LETTER in a separate Data Sheet cell (H14); we
    only receive FLUSH_PLAN (a name/number). If a recognized letter is provided
    (FLUSH_PLAN_LETTER or a FLUSH_PLAN that IS a letter), map it. Otherwise -
    including the STD 'no dedicated flush' cases where FLUSH_PLAN is a pressure/
    spec value like 'P1200', or NONE/blank - fall back to the no-flush N/A code.
    The flush-name->letter mapping lives only in the Data Sheet's derived cell
    (not available here); non-'none' named plans without a letter surface as ??
    so the gap is visible rather than silently wrong."""
    flush_map = _SPECIAL.get("flush", {})
    letter = _norm(selections.get("FLUSH_PLAN_LETTER", ""))
    if letter and letter in flush_map:
        return flush_map[letter]
    plan = _norm(selections.get("FLUSH_PLAN", ""))
    if plan and plan in flush_map:          # FLUSH_PLAN itself is a letter
        return flush_map[plan]
    # No-flush / spec-value (e.g. 'P1200') / NONE / blank -> N/A code.
    if plan == "" or plan.upper() in ("NONE", "N/A") or plan.upper().startswith("P"):
        na = flush_map.get("N/A")
        if na is not None:
            return na
    return "??"


def resolve_barrier(selections):
    """Barrier (variable, usually 1): Config Info FK(code)->FN(base-36)."""
    letter = _norm(selections.get("BARRIER_PLAN_LETTER", "")) or \
        _norm(selections.get("BARRIER_PLAN", ""))
    code = _SPECIAL.get("barrier", {}).get(letter)
    if code is None and (letter == "" or letter.upper() in ("NONE", "N/A")):
        code = _SPECIAL.get("barrier", {}).get("N/A")
    return code if code is not None else "?"


def resolve_segments(cursor, series, size, selections):
    """Resolve every Dean PN segment. Returns (segments_payload_dict, debug_dict).

    segments_payload keys match cfg.usp_AssembleConfiguredProduct @FamilyCode=DEAN.
    """
    base = base_identifier(cursor, series, size) or ("D" + "?" * 4)

    # --- table-backed segments (exact CombinationKey match) ---
    def table(seg):
        # Custom selection -> the workbook's padded custom placeholder (segment
        # excluded from the enumerated numbering table).
        cust = SEGMENT_CUSTOM_PLACEHOLDER.get(seg)
        if cust and _has_custom(selections, seg):
            return cust
        combo = _build_combo(selections, seg)
        code = _seg_lookup(cursor, seg, combo)
        return code if code else _err(SEGMENT_WIDTH[seg])

    wet_end = table("WET_END_OPTIONS")
    imp_opts = table("IMPELLER_OPTIONS")
    power = table("POWER_FRAME_OPTIONS")
    cooling = table("COOLING_PLAN")
    addl = table("ADDITIONAL_OPTIONS")
    testing = table("TESTING")
    documentation = table("DOCUMENTATION")

    # --- gated segments ---
    baseplate_type = _norm(selections.get("BASEPLATE_TYPE", ""))
    if baseplate_type.upper() == "NONE" or baseplate_type == "":
        baseplate = "000"
    else:
        baseplate = table("BASEPLATE_OPTIONS")

    motor_opt = _norm(selections.get("MOTOR_OPTION", ""))
    if motor_opt.lower() != "included":
        motor = "0000"  # workbook emits 4 chars when not Included
    else:
        motor = table("MOTOR")

    # motor frame: gated to "00" when no motor/baseplate/coupling/frame.
    # Full BASE(MATCH) over the HP x RPM matrix (Table2486) is pending precise
    # engineering; default to the gated no-motor value.
    frame = "00"

    # motor options: inert in the workbook (static "00")
    motor_options = "00"

    # --- special segments ---
    trim = resolve_trim(selections)
    seal = resolve_seal(selections)
    flush = resolve_flush(selections)
    barrier = resolve_barrier(selections)

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
    py_pn = (
        f"{base}-{wet_end}-{trim}{imp_opts}-{power}"
        f"-{flush}{barrier}{cooling}-{frame}{baseplate}"
        f"-{motor}{motor_options}-{addl}-{testing}{documentation}"
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
        f"-{payload['additional_options']}"
        f"-{payload['testing']}{payload['documentation']}"
    )

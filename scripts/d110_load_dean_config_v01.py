"""D110 (re-base) — publish the Dean configuration model to SQL from the NEW
authoritative workbook workbooks/Dean/PumpConfiguration_Logic_0.1.xlsm.

This SUPERSEDES scripts/d110_load_dean_config.py (which read the old
PumpConfiguration_Logic.xlsm 'Pump Options' + the m023 reconciliation JSON).
Now BOTH the offered options AND the numbering derive from ONE workbook, closing
the config-vs-numbering divergence (engineering questions B1-B4, E2, E3).

SOURCES (all in PumpConfiguration_Logic_0.1.xlsm):
  * 'Config Options'  -> the field catalog (field header -> canonical code) +
    value domains. Header row 3; values rows 4..103; field header every 2 cols.
  * 'Pump Constraints' -> per-MODEL (A#/Series/Size) STD/X applicability matrix.
    Row 2 = group headers (option field), row 3 = individual option-value headers
    + identity A/B/C, data rows 4..209 (206 models). Cell = STD / X / blank.
  * 'Codependencies' -> driver->dependent allow whitelists + NONE-collapse notes.

Rules / safety (unchanged from the prior loader):
  * Family-scoped: writes ONLY PumpFamilyId=DEAN; NEVER touches FYBROC rows.
  * Idempotent: deletes existing DEAN rows in the three tables, then reloads.
  * SeriesFieldOption per model: SizeCode = model size; STD/X markers; blank not
    loaded. Ungated domain fields (no per-model markers) loaded per-series SizeCode
    NULL from Config Options domain.
  * Preserves the canonical FieldCode vocabulary the API/resolver already use.

Run:  $env:PYTHONPATH="."; python scripts/d110_load_dean_config_v01.py [--dry-run]
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pyodbc
from openpyxl import load_workbook

CS = ('DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;'
      'DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;Encrypt=yes;'
      'TrustServerCertificate=yes;')
WB_PATH = Path("workbooks/Dean/PumpConfiguration_Logic_0.1.xlsm")
WORKBOOK = "PumpConfiguration_Logic_0.1.xlsm"

# Canonical DEAN field codes currently in the DB (preserve this vocabulary).
CANONICAL_CODES = {
    "ALIGNMENT_LUGS","AUXILLARY_NAMEPLATE","BARRIER_PLAN","BASEPLATE_TYPE",
    "BEARING_FRAME_COOLING","BEARING_LUBRICATION","BEARING_SEAL","CASING_DRAIN",
    "CASING_GASKET","CASING_HEAT_JACKET","CASING_MATERIAL","CASING_MOUNTING",
    "CASING_TAPS","CASING_WEAR_RING","COATING","COOLING_PLAN","COOLING_PLAN_EXTRAS",
    "COOLING_PLAN_PIPING","COUPLING_GUARD","COUPLING_TYPE","CRATING","DRIP_PAN",
    "EXPANSION_CHAMBER","FLANGE_CONFIGURATION","FLUSH_PLAN","FRAME_SIZE",
    "GLAND_GASKET","GLAND_TYPE","GROUNDING_LUG","GROUT_HOLE","HYDROPADS",
    "IMPELLER_BALANCE","IMPELLER_MATERIAL","IMPELLER_TRIM","IMPELLER_WEAR_RING_MATERIAL",
    "INBOARD_ELASTOMER","INBOARD_HARDWARE_MATERIAL","INBOARD_ROTATING_FACE_MATERIAL",
    "INBOARD_STATIONARY_FACE_MATERIAL","ISOLATION_PADS","LANTERN_RING",
    "LEVELLING_SCREWS","LIFTING_LUGS","MAGNETIC_DRAIN","MIN_FLO_BUSHING",
    "OILER_OPTIONS","OUTBOARD_ELASTOMERS","OUTBOARD_HARDWARE_MATERIAL",
    "OUTBOARD_ROTATING_FACE_MATERIAL","OUTBOARD_STATIONARY_FACE_MATERIAL",
    "PAINT_OPTIONS","PUMP_CONFIGURATION","PUMP_MATERIAL","PUMPING_RING",
    "SEAL_CHAMBER_CONFIG","SEAL_CONFIGURATION","SEAL_MANUFACTURER","SEAL_OPTION",
    "SEAL_TYPE","SHAFT_CONFIGURATION","SHAFT_MATERIAL","SHAFT_SLEEVE_MATERIAL",
    "SHIPPING_GASKET","SIGHT_GLASS","SPOT_FACING","STILTS","TACK_WELD_WEAR_RINGS",
    "THROTTLE_BUSHING",
}
# Header-label -> canonical code aliases where normalization alone won't match.
LABEL_ALIASES = {
    "impeller wear ring material": "IMPELLER_WEAR_RING_MATERIAL",
    "inboard elastomer": "INBOARD_ELASTOMER",
    "outboard elastomers": "OUTBOARD_ELASTOMERS",
    "inboard rotating face material": "INBOARD_ROTATING_FACE_MATERIAL",
    "inboard stationary face material": "INBOARD_STATIONARY_FACE_MATERIAL",
    "outboard rotating face material": "OUTBOARD_ROTATING_FACE_MATERIAL",
    "outboard stationary face material": "OUTBOARD_STATIONARY_FACE_MATERIAL",
    "inboard hardware material": "INBOARD_HARDWARE_MATERIAL",
    "outboard hardware material": "OUTBOARD_HARDWARE_MATERIAL",
    "auxillary nameplate": "AUXILLARY_NAMEPLATE",
    "min-flo bushing": "MIN_FLO_BUSHING",
    "tack weld wear rings": "TACK_WELD_WEAR_RINGS",
    "cooling plan routing": "COOLING_PLAN_PIPING",  # DB uses PIPING for routing
    "cooling plan extras": "COOLING_PLAN_EXTRAS",
    "old jc style": None,          # not a configurable field code
    "flush plan code": None,       # derived code column, not an option field
    "barrier plan code": None,
}
# Config Options fields we do NOT load as options (identity/derived/not-in-DB).
SKIP_LABELS = {"old jc style", "flush plan code", "barrier plan code",
               "level switches", "pressure switch", "cooling connections",
               "cooling plan temperature", "flush plan routing",
               "flush connections", "flush temperature range",
               "flush cooling media", "barrier plan routing",
               "barrier connections", "barrier temperature range",
               "barrier cooling media", "tank capacity",
               "drip cover", "conduit box"}


def norm_label(label: str) -> str | None:
    """Map a workbook header label -> canonical DB field code (or None to skip)."""
    key = str(label).strip().lower()
    if key in LABEL_ALIASES:
        return LABEL_ALIASES[key]
    if key in SKIP_LABELS:
        return None
    code = re.sub(r"[^A-Z0-9]+", "_", str(label).strip().upper()).strip("_")
    return code if code in CANONICAL_CODES else None


def col_letter(i0):
    s = ""; c = i0 + 1
    while c > 0:
        c, r = divmod(c - 1, 26); s = chr(65 + r) + s
    return s


def _norm_value(field_code, value):
    v = str(value).strip()
    if field_code in ("BARRIER_PLAN", "FLUSH_PLAN") and v.upper().startswith("PLAN "):
        return "Plan " + v[5:]
    return v


# ---------------------------------------------------------------------------
# Read Pump Constraints (per-model STD/X applicability matrix).
# Row 2 = group headers (option field), row 3 = per-value headers + A/B/C identity,
# data rows 4..209. Assign each value column to the nearest group header at/left.
# ---------------------------------------------------------------------------
def read_pump_constraints(wb):
    ws = wb["Pump Constraints"]
    rows = list(ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True))

    def cell(row, idx1):  # idx1 = 1-based col
        return row[idx1 - 1] if 0 <= idx1 - 1 < len(row) else None

    row2, row3 = rows[1], rows[2]
    ncol = max(len(row2), len(row3))

    # group header positions (row2)
    group_at = {}
    for c in range(1, ncol + 1):
        v = cell(row2, c)
        if v is not None and str(v).strip():
            group_at[c] = str(v).strip()
    group_cols = sorted(group_at)

    def group_for(col):
        g = None
        for gc in group_cols:
            if gc <= col:
                g = group_at[gc]
            else:
                break
        return g

    # identity columns (row3): A Number / Series / Size
    id_cols = {}
    for c in range(1, ncol + 1):
        v = cell(row3, c)
        if v is None:
            continue
        h = str(v).strip().lower()
        if h == "a number":
            id_cols["a"] = c
        elif h == "series":
            id_cols["series"] = c
        elif h == "size":
            id_cols["size"] = c

    # value columns: row3 has a value header AND the group maps to a canonical code
    col_to_code = {}
    col_to_value = {}
    field_domains = {}
    unmapped = set()
    for c in range(1, ncol + 1):
        vh = cell(row3, c)
        if vh is None or str(vh).strip() == "":
            continue
        if c in id_cols.values():
            continue
        group = group_for(c)
        if group is None:
            continue
        code = norm_label(group)
        if code is None:
            unmapped.add(group)
            continue
        val = str(vh).strip()
        col_to_code[c] = code
        col_to_value[c] = val
        field_domains.setdefault(code, []).append(val)

    # models: data rows 4.. while A Number present
    models = []
    ac = id_cols.get("a"); sc = id_cols.get("series"); zc = id_cols.get("size")
    for r in rows[3:]:
        anum = cell(r, ac) if ac else None
        ser = cell(r, sc) if sc else None
        size = cell(r, zc) if zc else None
        if ser is None or str(ser).strip() == "":
            continue
        cells = {}
        for c, code in col_to_code.items():
            m = cell(r, c)
            mm = str(m).strip().upper() if m is not None else ""
            if mm in ("STD", "X"):
                cells.setdefault(code, {})[col_to_value[c]] = mm
        models.append({"a": str(anum).strip() if anum else "",
                       "series": str(ser).strip(),
                       "size": str(size).strip() if size is not None else "",
                       "cells": cells})
    return models, field_domains, sorted(unmapped)


# ---------------------------------------------------------------------------
# Read Codependencies -> ROW-ALIGNED multi-leg ALLOW tuples (FeasibleConstraint).
#
# Structure (confirmed against the sheet): row 6 = column-group headers (blank col
# separates groups). Under a group, EACH DATA ROW is ONE allowed tuple across that
# group's columns (2..4 legs). Sub-blocks RESTART at a row where the group's
# populated columns all hold field-label headers (a fresh header line). Cells that
# are notes (long sentences / 'If ...'/'No ...') invalidate that row. This matches
# the workbook exactly (e.g. Seal Configuration|Seal Type rows are 1 pair each;
# Seal Option|Gland Type|Flush Plan|Barrier Plan rows are 4-leg allow tuples).
# ---------------------------------------------------------------------------
_CODEP_HEADER_LABELS = {
    "series", "casing material", "impeller material", "shaft configuration",
    "bearing lubrication", "gland type", "seal configuration", "pumping ring",
    "cooling plan", "baseplate type", "casing taps", "casing gasket",
    "casing mounting", "seal type", "shaft sleeve material", "throttle bushing",
    "oiler options", "flush plan", "barrier plan", "inboard rotating face material",
    "inboard stationary face material", "inboard elastomer", "drip pan",
    "casing drain", "flange configuration", "impeller trim", "seal option",
    "shaft material", "bearing seal", "seal chamber config",
}


def _codep_is_note(v):
    s = str(v).strip()
    return len(s) > 40 or s.lower().startswith(("if ", "no ", "when "))


def read_codependencies(wb):
    """Return a list of allow tuples: each = [(code, value), ...] (2..4 legs)."""
    ws = wb["Codependencies"]
    rows = list(ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True))
    ncol = ws.max_column
    hdr6 = rows[5] if len(rows) > 5 else ()

    def cell(rn, ci):
        r = rows[rn - 1] if rn - 1 < len(rows) else None
        return r[ci] if r and ci < len(r) else None

    # contiguous header groups on row 6
    groups = []
    c = 0
    while c < ncol:
        if c < len(hdr6) and hdr6[c] is not None and str(hdr6[c]).strip():
            start = c
            while c < ncol and c < len(hdr6) and hdr6[c] is not None and str(hdr6[c]).strip():
                c += 1
            groups.append(list(range(start, c)))
        else:
            c += 1

    group_hdr_labels = {str(hdr6[c2]).strip().lower()
                        for grp in groups for c2 in grp if c2 < len(hdr6) and hdr6[c2]}
    valid_hdr = _CODEP_HEADER_LABELS | group_hdr_labels

    tuples = []
    for cols in groups:
        tname = "Codep_" + col_letter(cols[0])

        def is_header_row(rn):
            got = False
            for ci in cols:
                v = cell(rn, ci)
                if v is None or str(v).strip() == "":
                    continue
                got = True
                if norm_label(v) is None and str(v).strip().lower() != "series":
                    return False
                if str(v).strip().lower() not in valid_hdr:
                    return False
            return got

        cur_codes = None  # {col_idx: code} from the most recent header row
        for rn in range(6, len(rows) + 1):
            if is_header_row(rn):
                cur_codes = {}
                for ci in cols:
                    v = cell(rn, ci)
                    if v is not None and str(v).strip():
                        code = "SERIES" if str(v).strip().lower() == "series" else norm_label(v)
                        if code:
                            cur_codes[ci] = code
                continue
            if not cur_codes:
                continue
            legs = []
            bad = False
            for ci, code in cur_codes.items():
                v = cell(rn, ci)
                if v is None or str(v).strip() == "":
                    continue
                if _codep_is_note(v):
                    bad = True
                    break
                legs.append((code, str(v).strip()))
            if bad or len(legs) < 2:
                continue
            tuples.append((tname, legs))
    return tuples


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    print(f"Loading {WB_PATH} ...", flush=True)
    wb = load_workbook(WB_PATH, data_only=True, read_only=True)
    models, field_domains, unmapped = read_pump_constraints(wb)
    codeps = read_codependencies(wb)
    wb.close()

    series_set = sorted({m["series"] for m in models})
    n_std = sum(1 for m in models for vm in m["cells"].values()
                for mk in vm.values() if mk == "STD")
    print(f"Pump Constraints: {len(models)} models, {len(series_set)} series, "
          f"{len(field_domains)} mapped option fields, {n_std} STD cells")
    if unmapped:
        print(f"  UNMAPPED group headers (skipped): {unmapped}")
    print(f"Codependencies: {len(codeps)} driver->dependent allow tuples")

    from collections import Counter
    leg_dist = Counter(len(legs) for _, legs in codeps)
    print(f"  codep leg-count distribution: {dict(leg_dist)}")
    if args.dry_run:
        print("\n[dry-run] sample models:")
        for m in models[:3]:
            print(f"  {m['a']} {m['series']} {m['size']}: "
                  f"{sum(len(v) for v in m['cells'].values())} option cells, "
                  f"fields={list(m['cells'])[:6]}...")
        print("[dry-run] sample codep tuples:")
        for t in codeps[:4] + codeps[-2:]:
            print("  ", t[0], t[1])
        return

    conn = pyodbc.connect(CS, autocommit=True); c = conn.cursor()
    dean = c.execute("SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode='DEAN'").fetchone()[0]
    pub = c.execute("SELECT TOP 1 MetadataPublicationId FROM cfg.MetadataPublication "
                    "WHERE Status='Active' ORDER BY ActivatedAt DESC").fetchone()[0]
    print(f"DEAN family id={dean}  active publication id={pub}")

    fy = {t: c.execute(f"SELECT COUNT(*) FROM cfg.{t} WHERE PumpFamilyId<>?", dean).fetchone()[0]
          for t in ("FeasibleConstraint", "ConstraintFieldMap", "SeriesFieldOption")}
    print("pre non-DEAN:", fy)

    c.execute("DELETE FROM cfg.FeasibleConstraint WHERE PumpFamilyId=?", dean)
    c.execute("DELETE FROM cfg.ConstraintFieldMap WHERE PumpFamilyId=?", dean)
    c.execute("DELETE FROM cfg.SeriesFieldOption WHERE PumpFamilyId=?", dean)

    # ConstraintFieldMap: canonical code -> code (identity map; the constraint
    # legs already use canonical codes now). Includes SERIES (a valid constraint
    # leg though not an option field). Built AFTER seal-vocab filtering below, so
    # it covers exactly the enforced codes — computed here from the full set is
    # fine (extra map rows are harmless), but we recompute post-filter for clarity.
    seen_codes = sorted({code for _, legs in codeps for code, _ in legs})
    for code in seen_codes:
        c.execute("INSERT INTO cfg.ConstraintFieldMap (ConstraintFieldName, SFOFieldCode, PumpFamilyId) "
                  "VALUES (?, ?, ?)", code, code, dean)
    print(f"ConstraintFieldMap: {len(seen_codes)} DEAN rows")

    def insert_sfo(code, value, series_code, size_code, is_std, marker):
        c.execute(
            "INSERT INTO cfg.SeriesFieldOption "
            "(MetadataPublicationId, PumpFamilyId, SourceFieldCode, FieldCode, OptionValue, "
            " SeriesCode, SizeCode, WorkbookName, WorksheetName, SourceRow, SourceFieldCell, "
            " SourceValueCell, SourceSeriesCell, IsActive, CreatedAt, SelectionMarker, IsStandard) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, SYSUTCDATETIME(), ?, ?)",
            pub, dean, code, code, value, series_code, size_code, WORKBOOK,
            "Pump Constraints", 0, "", "", "", marker, 1 if is_std else 0,
        )

    n_sfo = 0
    for m in models:
        for code, valmap in m["cells"].items():
            for value, marker in valmap.items():
                insert_sfo(code, _norm_value(code, value), m["series"], m["size"],
                           marker == "STD", marker)
                n_sfo += 1
    print(f"SeriesFieldOption: {n_sfo} per-model rows")

    # SEAL codependencies are NOT enforced yet: the seal-type vocabulary differs
    # between the Pump Constraints seal columns (short 'Type N' names offered per
    # model) and the Codependencies seal columns (long descriptive names), so a
    # seal allow-list would prune the offered seal options to a dead-end. Seal is
    # the OPEN engineering item (A1) — engineering is still reconciling the seal
    # configuration code/vocabulary. Per direction, seal stays omitted-not-
    # discarded; we do NOT fabricate a seal vocabulary mapping. We load only the
    # NON-seal codependencies for enforcement, and skip seal-leg tuples (recorded
    # in DEAN_ENGINEERING_QUESTIONS.md A1 / new item). This is Dean-only.
    SEAL_CODEP_FIELDS = {
        "SEAL_TYPE", "SEAL_CONFIGURATION", "SEAL_OPTION", "SEAL_MANUFACTURER",
        "GLAND_TYPE", "BARRIER_PLAN", "THROTTLE_BUSHING", "PUMPING_RING",
        "INBOARD_ROTATING_FACE_MATERIAL", "INBOARD_STATIONARY_FACE_MATERIAL",
        "INBOARD_ELASTOMER", "INBOARD_HARDWARE_MATERIAL",
        "OUTBOARD_ROTATING_FACE_MATERIAL", "OUTBOARD_STATIONARY_FACE_MATERIAL",
        "OUTBOARD_ELASTOMERS", "OUTBOARD_HARDWARE_MATERIAL", "SHAFT_SLEEVE_MATERIAL",
    }
    codeps_enforced = [(t, legs) for (t, legs) in codeps
                       if not any(code in SEAL_CODEP_FIELDS for code, _ in legs)]
    n_seal_skipped = len(codeps) - len(codeps_enforced)
    print(f"Codependencies: {len(codeps_enforced)} enforced, "
          f"{n_seal_skipped} seal-vocab tuples skipped (pending engineering A1)")
    codeps = codeps_enforced

    # FeasibleConstraint: ROW-ALIGNED multi-leg (2..4) Allowed tuples.
    n_fc = 0
    for tname, legs in codeps:
        legs4 = legs[:4] + [(None, None)] * (4 - len(legs))
        (o1f, o1v), (o2f, o2v), (o3f, o3v), (o4f, o4v) = legs4
        c.execute(
            "INSERT INTO cfg.FeasibleConstraint "
            "(TableName, Option1Field, Option1Value, Option2Field, Option2Value, "
            " Option3Field, Option3Value, Option4Field, Option4Value, "
            " Allowed, SeriesApplicability, Description, PumpFamilyId) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Allowed', 'ALL_SERIES', ?, ?)",
            tname,
            o1f, (_norm_value(o1f, o1v) if o1f else None),
            o2f, (_norm_value(o2f, o2v) if o2f else None),
            o3f, (_norm_value(o3f, o3v) if o3f else None),
            o4f, (_norm_value(o4f, o4v) if o4f else None),
            f"Dean codependency {tname}", dean,
        )
        n_fc += 1
    enforced_dist = Counter(len(legs) for _, legs in codeps)
    print(f"FeasibleConstraint: {n_fc} DEAN allow tuples (enforced legs: {dict(enforced_dist)})")

    fy2 = {t: c.execute(f"SELECT COUNT(*) FROM cfg.{t} WHERE PumpFamilyId<>?", dean).fetchone()[0]
           for t in ("FeasibleConstraint", "ConstraintFieldMap", "SeriesFieldOption")}
    print("post non-DEAN:", fy2)
    assert fy == fy2, "FYBROC rows changed!"
    print("FYBROC unchanged. DONE.")
    conn.close()


if __name__ == "__main__":
    main()

"""Dean motor SELECTABLE OPTIONS from Motor Numbering.xlsm, sheet 'Pricing'.

Authority: Pricing rows 1..72, columns A..AC (the options block; field headers in
row 1, values below). The 'Constraints' and 'Base Codes' sheets are NOT read.
The 34,082 motor combinations (rows 98..34179, R..AD) (spec code + price / C.F.) further down the same
sheet are loaded separately by load_dean_motor_numbering.py.

What this writes (Dean only, idempotent):
  * The 9 motor option fields (Motor, Motor Control, Rated Speed, Rated Power,
    Voltage, Phase/Frequency, Enclosure, Efficiency, Brand) as series-level rows
    in cfg.SeriesFieldOption for every Dean series. STD: Motor = 'Included' (a
    pump configuration that includes a motor always has the motor included);
    the other motor fields have no STD.
  * FRAME_SIZE is NOT replaced: each series' applicable frame sizes come from
    Pump Constraints (some series have none). Values are only canonicalized in
    place (UPPER + VP->HP) to match the motor combinations.

Called at the end of d110_load_dean_config_v01.py (which rebuilds all Dean SFO
rows), and runnable alone:
  uv run python scripts/load_dean_motor_options.py [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import shutil
import tempfile
from pathlib import Path

import pyodbc
from openpyxl import load_workbook

CS = ('DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=PumpConfiguratorDB;'
      'Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;')
WB_PATH = Path("workbooks/Dean/Motor Numbering.xlsm")
BLOCK_ROWS = (1, 72)          # header row 1, values 2..72
BLOCK_MAX_COL = 29            # A..AC
HEADER_TO_FIELD = {
    "Motor": "MOTOR", "Motor Control": "MOTOR_CONTROL", "Frame Size": "FRAME_SIZE",
    "Rated Speed": "RATED_SPEED", "Rated Power": "RATED_POWER", "Voltage": "VOLTAGE",
    "Phase/Frequency": "PHASE_FREQUENCY", "Enclosure": "ENCLOSURE",
    "Efficiency": "EFFICIENCY", "Brand": "BRAND",
}
OPTION_FIELDS = ["MOTOR", "MOTOR_CONTROL", "RATED_SPEED", "RATED_POWER", "VOLTAGE",
                 "PHASE_FREQUENCY", "ENCLOSURE", "EFFICIENCY", "BRAND"]
STD_VALUES = {"MOTOR": "Included"}


def canon_frame(v):
    return re.sub(r"VP$", "HP", str(v).strip().upper())


def read_block(path=WB_PATH):
    """{field_code: [values in sheet order]} from Pricing A1:AC72."""
    tmp = Path(tempfile.mkdtemp()) / path.name
    shutil.copy(path, tmp)
    wb = load_workbook(tmp, data_only=True, read_only=True)
    rows = list(wb["Pricing"].iter_rows(min_row=BLOCK_ROWS[0], max_row=BLOCK_ROWS[1],
                                        max_col=BLOCK_MAX_COL, values_only=True))
    wb.close()
    out = {}
    for ci, h in enumerate(rows[0]):
        f = HEADER_TO_FIELD.get(str(h).strip()) if h is not None else None
        if not f:
            continue
        vals = []
        for r in rows[1:]:
            v = r[ci] if ci < len(r) else None
            if v not in (None, ""):
                vals.append(canon_frame(v) if f == "FRAME_SIZE" else str(v).strip())
        out[f] = list(dict.fromkeys(vals))
    missing = set(HEADER_TO_FIELD.values()) - set(out)
    if missing:
        raise SystemExit(f"Pricing options block is missing headers for {sorted(missing)}")
    return out


def combo_values(cur):
    """{field: set(values)} present in the loaded MOTOR_SPEC combinations."""
    out = {f: set() for f in HEADER_TO_FIELD.values()}
    for (sj,) in cur.execute("SELECT SelectionsJson FROM stg.SegmentCombinationImport "
                             "WHERE FamilyCode='DEAN' AND SegmentCode='MOTOR_SPEC'"):
        import json
        for f, v in json.loads(sj).items():
            if f in out:
                out[f].add(v)
    return out


def apply_motor_options(cur, dean, pub, block=None):
    block = block or read_block()
    ph = ",".join("?" * len(OPTION_FIELDS))
    series = sorted({r[0] for r in cur.execute(
        "SELECT DISTINCT SeriesCode FROM cfg.SeriesFieldOption WHERE PumpFamilyId=? "
        "AND FieldCode='PUMP_CONFIGURATION'", dean)})
    # canonicalize FRAME_SIZE in place (keeps each series' Pump Constraints set)
    n_canon = n_dup = 0
    seen = {}
    for sid, ser, size, val in cur.execute(
            "SELECT SeriesFieldOptionId, SeriesCode, SizeCode, OptionValue FROM cfg.SeriesFieldOption "
            "WHERE PumpFamilyId=? AND FieldCode='FRAME_SIZE' ORDER BY SeriesFieldOptionId", dean).fetchall():
        key = (ser, size, canon_frame(val))
        if key in seen:
            cur.execute("DELETE FROM cfg.SeriesFieldOption WHERE SeriesFieldOptionId=?", sid)
            n_dup += 1
            continue
        seen[key] = sid
        if canon_frame(val) != val:
            cur.execute("UPDATE cfg.SeriesFieldOption SET OptionValue=? WHERE SeriesFieldOptionId=?",
                        canon_frame(val), sid)
            n_canon += 1
    cur.execute(f"DELETE FROM cfg.SeriesFieldOption WHERE PumpFamilyId=? AND FieldCode IN ({ph})",
                dean, *OPTION_FIELDS)
    batch = []
    for ser in series:
        for f in OPTION_FIELDS:
            for v in block[f]:
                is_std = STD_VALUES.get(f) == v
                batch.append((pub, dean, f, f, v, ser, WB_PATH.name, "Pricing",
                              "STD" if is_std else "X", 1 if is_std else 0))
    cur.fast_executemany = True
    cur.executemany(
        "INSERT INTO cfg.SeriesFieldOption (MetadataPublicationId, PumpFamilyId, SourceFieldCode, "
        "FieldCode, OptionValue, SeriesCode, SizeCode, WorkbookName, WorksheetName, SourceRow, "
        "SourceFieldCell, SourceValueCell, SourceSeriesCell, IsActive, CreatedAt, SelectionMarker, "
        "IsStandard) VALUES (?,?,?,?,?,?,NULL,?,?,0,'A1:AC72','','',1,SYSUTCDATETIME(),?,?)", batch)
    return {"series": len(series), "rows": len(batch), "frame_canonicalized": n_canon,
            "frame_dupes_merged": n_dup}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    block = read_block()
    for f, v in block.items():
        print(f"  {f}: {len(v)} {v if len(v) <= 10 else v[:6] + ['...']}")
    conn = pyodbc.connect(CS, autocommit=True)
    cur = conn.cursor()
    cv = combo_values(cur)
    for f, vals in block.items():
        a_only, b_only = set(vals) - cv[f], cv[f] - set(vals)
        if a_only or b_only:
            print(f"  [{f}] block-only (no combination): {sorted(a_only)}  combos-only: {sorted(b_only)}")
    if a.dry_run:
        return 0
    dean = cur.execute("SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode='DEAN'").fetchone()[0]
    pub = cur.execute("SELECT TOP 1 MetadataPublicationId FROM cfg.MetadataPublication "
                      "WHERE Status='Active' ORDER BY ActivatedAt DESC").fetchone()[0]
    fy = cur.execute("SELECT COUNT(*) FROM cfg.SeriesFieldOption WHERE PumpFamilyId<>?", dean).fetchone()[0]
    print(apply_motor_options(cur, dean, pub, block))
    fy2 = cur.execute("SELECT COUNT(*) FROM cfg.SeriesFieldOption WHERE PumpFamilyId<>?", dean).fetchone()[0]
    assert fy == fy2, "non-DEAN SFO changed!"
    print("non-DEAN SFO unchanged:", fy2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

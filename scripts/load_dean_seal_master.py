"""Replace DEAN seal selection options with the SealNumbering.xlsx 'Master' sheet.

Master (row 2 headers, columns B..V) is the authority for seal selection options.
Each field's options are the contiguous non-blank block starting at row 3; notes,
price labels and stray values below that block (the "junk" cells) are excluded.
Seal Chamber Config is NOT replaced (it is a wet-end numbered field) and Seal
Option is not on Master. 'C/F' is a populated placeholder value, not an option, so
it is dropped from the replaced fields.

Scope: for every DEAN (series, size) that carries a replaced field, that field's
rows are replaced by the Master options (marker X). A previous STD is kept only if
that value exists in Master. Gland Gasket (new field) is added only for series whose
Seal Reference sheet is 'Misc.'. Fybroc rows are never touched.

Called by d110_load_dean_config_v01.py after the Pump Constraints load (so a
re-ingest keeps Master as the authority) and runnable alone:
  uv run python scripts/load_dean_seal_master.py [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import shutil
import tempfile
from pathlib import Path

import pyodbc
from openpyxl import load_workbook

CS = ('DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;'
      'DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;Encrypt=yes;'
      'TrustServerCertificate=yes;')
SRC = Path("workbooks/Dean/SealNumbering.xlsx")

MASTER_HEADER_TO_FIELD = {
    "seal configuration": "SEAL_CONFIGURATION",
    "seal type": "SEAL_TYPE",
    "seal manufacturer": "SEAL_MANUFACTURER",
    "inboard rotating face": "INBOARD_ROTATING_FACE_MATERIAL",
    "inboard stationary face": "INBOARD_STATIONARY_FACE_MATERIAL",
    "inboard elastomers": "INBOARD_ELASTOMER",
    "outboard rotating face": "OUTBOARD_ROTATING_FACE_MATERIAL",
    "outboard stationary face": "OUTBOARD_STATIONARY_FACE_MATERIAL",
    "outboard elastomers": "OUTBOARD_ELASTOMERS",
    "hydropads": "HYDROPADS",
    "pumping ring": "PUMPING_RING",
    "throttle bushing": "THROTTLE_BUSHING",
    "min flo bushing": "MIN_FLO_BUSHING",
    "lantern ring": "LANTERN_RING",
    "inboard seal hardware": "INBOARD_HARDWARE_MATERIAL",
    "outboard seal hardware": "OUTBOARD_HARDWARE_MATERIAL",
    "gland style": "GLAND_TYPE",
    "gland gasket": "GLAND_GASKET",
    "sleeve material": "SHAFT_SLEEVE_MATERIAL",
    # intentionally NOT replaced: 'seal chamber config' (wet-end numbered field)
}


def _n(s):
    return re.sub(r"\s+", " ", str(s or "").strip()).lower()


def read_master(path=SRC):
    tmp = Path(tempfile.mkdtemp()) / path.name
    shutil.copy(path, tmp)
    wb = load_workbook(tmp, data_only=True, read_only=True)
    rows = list(wb["Master"].iter_rows(min_row=1, max_row=70, max_col=22, values_only=True))
    wb.close()
    hdr = rows[1]
    domains = {}
    for ci in range(1, 22):
        f = MASTER_HEADER_TO_FIELD.get(_n(hdr[ci]))
        if not f:
            continue
        vals = []
        for r in range(2, len(rows)):
            v = rows[r][ci]
            if v is None or str(v).strip() == "":
                break
            vals.append(re.sub(r"\s+", " ", str(v).strip()))
        domains[f] = list(dict.fromkeys(vals))
    return domains


def apply_master_options(cur, dean, pub, domains=None):
    """Replace DEAN seal options. Returns summary dict. Caller owns the connection."""
    domains = domains or read_master()
    fields = tuple(domains)
    ph = ",".join("?" * len(fields))
    misc_series = {r[0] for r in cur.execute(
        "SELECT SeriesCode FROM cfg.DeanSealReference WHERE SealRefKey = 'Misc.'")}
    # (series,size) pairs that carry any replaced field (excluding the new gasket field)
    pairs = cur.execute(
        f"SELECT DISTINCT SeriesCode, SizeCode FROM cfg.SeriesFieldOption "
        f"WHERE PumpFamilyId=? AND FieldCode IN ({ph}) AND FieldCode<>'GLAND_GASKET'",
        dean, *fields).fetchall()
    old_std = {}
    for ser, size, fc, val in cur.execute(
            f"SELECT SeriesCode, SizeCode, FieldCode, OptionValue FROM cfg.SeriesFieldOption "
            f"WHERE PumpFamilyId=? AND IsStandard=1 AND FieldCode IN ({ph})", dean, *fields):
        old_std[(ser, size, fc)] = val
    cur.execute(f"DELETE FROM cfg.SeriesFieldOption WHERE PumpFamilyId=? AND FieldCode IN ({ph})",
                dean, *fields)
    sql = ("INSERT INTO cfg.SeriesFieldOption (MetadataPublicationId, PumpFamilyId, "
           "SourceFieldCode, FieldCode, OptionValue, SeriesCode, SizeCode, WorkbookName, "
           "WorksheetName, SourceRow, SourceFieldCell, SourceValueCell, SourceSeriesCell, "
           "IsActive, CreatedAt, SelectionMarker, IsStandard) "
           "VALUES (?,?,?,?,?,?,?,?,?,0,'','','',1,SYSUTCDATETIME(),?,?)")
    batch, n_std = [], 0
    for ser, size in pairs:
        for fc, vals in domains.items():
            if fc == "GLAND_GASKET" and ser not in misc_series:
                continue
            prev = old_std.get((ser, size, fc))
            std_val = next((v for v in vals if prev is not None and _n(v) == _n(prev)), None)
            for v in vals:
                is_std = std_val is not None and v == std_val
                n_std += is_std
                batch.append((pub, dean, fc, fc, v, ser, size, SRC.name, "Master",
                              "STD" if is_std else "X", 1 if is_std else 0))
    cur.fast_executemany = True
    cur.executemany(sql, batch)
    return {"pairs": len(pairs), "rows": len(batch), "std": n_std,
            "fields": len(domains), "misc_series": len(misc_series)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    domains = read_master()
    for f, v in domains.items():
        print(f"  {f}: {len(v)} {v if len(v) < 10 else v[:5] + ['...']}")
    if a.dry_run:
        return 0
    conn = pyodbc.connect(CS, autocommit=True)
    cur = conn.cursor()
    dean = cur.execute("SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode='DEAN'").fetchone()[0]
    pub = cur.execute("SELECT TOP 1 MetadataPublicationId FROM cfg.MetadataPublication "
                      "WHERE Status='Active' ORDER BY ActivatedAt DESC").fetchone()[0]
    fy = cur.execute("SELECT COUNT(*) FROM cfg.SeriesFieldOption WHERE PumpFamilyId<>?", dean).fetchone()[0]
    print(apply_master_options(cur, dean, pub, domains))
    fy2 = cur.execute("SELECT COUNT(*) FROM cfg.SeriesFieldOption WHERE PumpFamilyId<>?", dean).fetchone()[0]
    assert fy == fy2, "non-DEAN SFO changed!"
    print("non-DEAN SFO unchanged:", fy2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Replace DEAN seal selection options with the SealNumbering.xlsx 'Master' sheet.

Master (row 2 headers, columns B..V) is the authority for seal selection options.
Each field's options are the contiguous non-blank block starting at row 3; notes,
price labels and stray values below that block (the "junk" cells) are excluded.
Seal Chamber Config is NOT replaced (it is a wet-end numbered field) and Seal
Option is not on Master. 'C/F' is a populated placeholder value, not an option, so
it is dropped from the replaced fields.

Scope: for every DEAN (series, size) that carries a replaced field, that field's
rows are replaced by the Master options (marker X, no STD seed). Which of those
options APPLY to a series is decided at runtime by src/api/dean_seal.py from the
series' Seal Reference sheet and the selected Seal Type. Gland Gasket (new field) is
added only for series whose Seal Reference sheet is 'Misc.'. Fybroc rows are never
touched.

Called by d110_load_dean_config_v01.py after the Pump Constraints load (so a
re-ingest keeps Master as the authority) and runnable alone:
  uv run python scripts/load_dean_seal_master.py [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import sys
import shutil
import tempfile
from pathlib import Path
from collections import Counter

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


# Pump Constraints spelling -> Master spelling (same option, different label).
PC_TO_MASTER = {
    ("OUTBOARD_HARDWARE_MATERIAL", "hastelloy c"): "Hastelloy",
    ("SHAFT_SLEEVE_MATERIAL", "420 ss"): "420",
    ("SHAFT_SLEEVE_MATERIAL", "420 ss hardened"): "420 Hardened",
}


def to_master(fc, v, canon):
    """Master spelling of a Pump Constraints value, or None if Master has no such option."""
    a = PC_TO_MASTER.get((fc, _n(v)))
    return a if a is not None else canon[fc].get(_n(v))


def read_pc_models():
    """Pump Constraints models (series, size, cells) via the d110 parser."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import d110_load_dean_config_v01 as D
    tmp = Path(tempfile.mkdtemp()) / D.WB_PATH.name
    shutil.copy(D.WB_PATH, tmp)
    wb = load_workbook(tmp, data_only=True, read_only=True)
    models, _fd, _un = D.read_pump_constraints(wb)
    wb.close()
    return models


def apply_master_options(cur, dean, pub, domains=None, models=None):
    """Rebuild DEAN seal options.

    Vocabulary authority = SealNumbering 'Master'. Which options a (series, size)
    OFFERS, and which one is STD, come from Pump Constraints (per model): an option
    is offered iff Pump Constraints offers it for that model AND Master lists it
    (Pump Constraints spellings are matched to the Master spelling). STD = the Pump
    Constraints STD value when it is a Master value. Gland Gasket (not in Pump
    Constraints) gets the Master options for Misc. series only, no STD. Which
    permutations are actually buildable is decided at runtime by the series' Seal
    Reference sheet (src/api/dean_seal.py). Caller owns the connection.
    """
    domains = domains or read_master()
    models = models if models is not None else read_pc_models()
    fields = tuple(domains)
    ph = ",".join("?" * len(fields))
    misc_series = {r[0] for r in cur.execute(
        "SELECT SeriesCode FROM cfg.DeanSealReference WHERE SealRefKey = 'Misc.'")}
    canon = {f: {_n(v): v for v in vals} for f, vals in domains.items()}
    cur.execute(f"DELETE FROM cfg.SeriesFieldOption WHERE PumpFamilyId=? AND FieldCode IN ({ph})",
                dean, *fields)
    sql = ("INSERT INTO cfg.SeriesFieldOption (MetadataPublicationId, PumpFamilyId, "
           "SourceFieldCode, FieldCode, OptionValue, SeriesCode, SizeCode, WorkbookName, "
           "WorksheetName, SourceRow, SourceFieldCell, SourceValueCell, SourceSeriesCell, "
           "IsActive, CreatedAt, SelectionMarker, IsStandard) "
           "VALUES (?,?,?,?,?,?,?,?,?,0,'','','',1,SYSUTCDATETIME(),?,?)")
    batch = []
    st = {"models": 0, "std": 0, "pc_values_dropped": Counter(), "std_dropped": Counter(),
          "models_with_std": 0}
    for m in models:
        ser, size = m["series"], m["size"]
        st["models"] += 1
        got_std = False
        for fc in fields:
            if fc == "GLAND_GASKET":
                if ser in misc_series:
                    for v in domains[fc]:
                        batch.append((pub, dean, fc, fc, v, ser, size, SRC.name, "Master", "X", 0))
                continue
            seen = {}
            for v, mk in (m["cells"].get(fc) or {}).items():
                cv = to_master(fc, v, canon)
                if cv is None:
                    st["pc_values_dropped"][(fc, v)] += 1
                    if mk == "STD":
                        st["std_dropped"][(fc, v)] += 1
                    continue
                seen[cv] = "STD" if (mk == "STD" or seen.get(cv) == "STD") else "X"
            for cv in domains[fc]:          # Master order
                if cv in seen:
                    is_std = seen[cv] == "STD"
                    st["std"] += is_std
                    got_std |= is_std
                    batch.append((pub, dean, fc, fc, cv, ser, size, "PumpConfiguration_Logic_0.1.xlsm + "
                                  + SRC.name, "Pump Constraints", seen[cv], 1 if is_std else 0))
        st["models_with_std"] += got_std
    cur.fast_executemany = True
    cur.executemany(sql, batch)
    return {"models": st["models"], "rows": len(batch), "std_cells": st["std"],
            "models_with_std": st["models_with_std"], "fields": len(domains),
            "misc_series": len(misc_series),
            "pc_values_dropped": dict(st["pc_values_dropped"]),
            "std_dropped": dict(st["std_dropped"])}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    domains = read_master()
    for f, v in domains.items():
        print(f"  {f}: {len(v)} {v if len(v) < 10 else v[:5] + ['...']}")
    if a.dry_run:
        models = read_pc_models()
        canon = {f: {_n(v): v for v in vals} for f, vals in domains.items()}
        miss = Counter((f, v) for m in models for f in domains for v in (m["cells"].get(f) or {})
                       if to_master(f, v, canon) is None)
        print("Pump Constraints values not on Master (field, value): models", dict(miss))
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

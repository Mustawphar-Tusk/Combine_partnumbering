"""Load Dean seal spec + price mapping from SealNumbering.xlsx into cfg.DeanSealSpec.

Sheets "1.000"/"1.375"/"1.750"/"2.125"/"2.250"/"3.000" Shafts" and "Misc." are
each a cfg.DeanSealReference.SealRefKey. The Combined Table and per-Type sheets
are intentionally NOT read. Idempotent (clears + reloads). Dean-only, additive.

Run:  uv run python scripts/load_dean_seal_spec.py [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

import pyodbc
from openpyxl import load_workbook

sys.path.insert(0, ".")
from src.api.dean_seal import (GASKET_SHEETS, SHEET_HEADER_TO_FIELD,  # noqa: E402
                               combo_hash, combo_key)

CS = ('DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;'
      'DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;Encrypt=yes;'
      'TrustServerCertificate=yes;')
SRC = Path("workbooks/Dean/SealNumbering.xlsx")
SQL_PATH = Path("sql/38_Create_Dean_Seal_Spec.sql")
SHEETS = ['1.000" Shafts', '1.375" Shafts', '1.750" Shafts', '2.125" Shafts',
          '2.250" Shafts', '3.000" Shafts', "Misc."]


def apply_migration(conn):
    cur = conn.cursor()
    if cur.execute("SELECT OBJECT_ID('cfg.DeanSealSpec','U')").fetchone()[0] is not None:
        return
    for batch in re.split(r"(?im)^\s*GO\s*$", SQL_PATH.read_text(encoding="utf-8-sig")):
        if batch.strip():
            cur.execute(batch)
            while cur.nextset():
                pass
    print("Applied sql/38.")


def classify_price(p):
    """-> (raw, amount, status)"""
    if p is None or str(p).strip() == "":
        return None, None, "BLANK"
    if isinstance(p, (int, float)):
        return str(p), round(float(p), 2), "PRICED"
    s = str(p).strip()
    u = s.upper().replace(".", "").replace(" ", "")
    if u == "CF":
        return s, None, "CF"
    if u == "TBD":
        return s, None, "TBD"
    try:
        return s, round(float(s.replace(",", "").replace("$", "")), 2), "PRICED"
    except ValueError:
        return s, None, "TBD"


def read_sheet(wb, name):
    it = wb[name].iter_rows(min_row=3, values_only=True)
    header = next(it)
    idx = {re.sub(r"\s+", " ", str(h).strip().lower()): i
           for i, h in enumerate(header) if h}
    field_idx = {SHEET_HEADER_TO_FIELD[h]: i for h, i in idx.items()
                 if h in SHEET_HEADER_TO_FIELD}
    ci, pi = idx["alphanumeric code"], idx.get("price")
    out = []
    for n, row in enumerate(it, start=4):
        if row is None or ci >= len(row) or row[ci] is None or str(row[ci]).strip() == "":
            continue
        vals = {f: ("" if row[i] is None else str(row[i])) for f, i in field_idx.items()}
        key = combo_key(vals, name)
        raw, amt, st = classify_price(row[pi] if pi is not None and pi < len(row) else None)
        out.append((name, str(row[ci]).strip(), key, combo_hash(key), raw, amt, st, n))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    tmp = Path(tempfile.mkdtemp()) / SRC.name
    shutil.copy(SRC, tmp)
    wb = load_workbook(tmp, data_only=True, read_only=True)
    all_rows = []
    for s in SHEETS:
        rows = read_sheet(wb, s)
        dup = sum(1 for v in Counter((r[0], r[3]) for r in rows).values() if v > 1)
        st = Counter(r[6] for r in rows)
        print(f"{s!r}: {len(rows)} rows, duplicate combos={dup}, price={dict(st)}")
        all_rows += rows
    wb.close()
    if args.dry_run:
        return 0
    conn = pyodbc.connect(CS, autocommit=True)
    apply_migration(conn)
    cur = conn.cursor()
    cur.execute("DELETE FROM cfg.DeanSealSpec")
    cur.fast_executemany = True
    cur.executemany(
        "INSERT INTO cfg.DeanSealSpec (SealRefKey, SealCode, ComboKey, ComboHash, PriceRaw, "
        "PriceAmount, PriceStatus, SourceRow) VALUES (?,?,?,?,?,?,?,?)", all_rows)
    n = cur.execute("SELECT COUNT(*) FROM cfg.DeanSealSpec").fetchone()[0]
    print(f"Loaded {n} rows into cfg.DeanSealSpec.")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

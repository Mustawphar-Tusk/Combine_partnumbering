"""Load Dean seal spec + price mapping from SealNumbering.xlsx, ONE TABLE PER SHEET.

Sheets "1.000"/"1.375"/"1.750"/"2.125"/"2.250"/"3.000" Shafts" and "Misc." are each
a cfg.DeanSealReference.SealRefKey with its own table cfg.DeanSealSpec_<sheet>
(sql/39; PRIMARY KEY on the permutation hash). Collision rule (owner): when the
same permutation (same values across every column) appears more than once on a
sheet, the EARLIER row (and its code/price) is retained and the later rows are
discarded (logged in cfg.DeanSealSpecDiscarded). Permutation numbers are then
re-sequenced 1..N in sheet order (PermutationNo); the retained rows keep their codes. The Combined Table and per-Type sheets are NOT
read. Idempotent (clears + reloads). Dean-only, additive. Drops the superseded
combined cfg.DeanSealSpec (sql/38) after a successful load.

Run:  uv run python scripts/load_dean_seal_spec.py [--dry-run]
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import pyodbc
from openpyxl import load_workbook

sys.path.insert(0, ".")
from src.api.dean_seal import (GASKET_SHEETS, SHEET_HEADER_TO_FIELD,  # noqa: E402
                               SHEET_TABLE, combo_hash, combo_key)

CS = ('DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;'
      'DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;Encrypt=yes;'
      'TrustServerCertificate=yes;')
SRC = Path("workbooks/Dean/SealNumbering.xlsx")
SQL_PATH = Path("sql/39_Create_Dean_Seal_Sheet_Tables.sql")
SHEETS = list(SHEET_TABLE)


def apply_migration(conn):
    cur = conn.cursor()
    text = SQL_PATH.read_text(encoding="utf-8-sig")
    for batch in re.split(r"(?im)^\s*GO\s*$", text):
        if batch.strip():
            cur.execute(batch)
            while cur.nextset():
                pass


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
    """-> rows (sheet, code, key, hash, price_raw, amount, status, source_row)"""
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


def dedupe(rows):
    """-> (kept, discarded). Rows are in sheet order. For a repeated permutation the
    earlier row is kept and every later row is discarded. `kept` rows get a new
    sequential permutation number 1..N (position 8 appended: PermutationNo);
    `discarded` rows get the kept row appended (position 8: the retained row)."""
    first = {}
    kept, disc = [], []
    for r in rows:
        k = first.get(r[3])
        if k is None:
            first[r[3]] = r
            kept.append(r)
        else:
            disc.append(r + (k,))
    kept = [r + (i,) for i, r in enumerate(kept, start=1)]
    return kept, disc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    tmp = Path(tempfile.mkdtemp()) / SRC.name
    shutil.copy(SRC, tmp)
    wb = load_workbook(tmp, data_only=True, read_only=True)
    loaded = {}
    for s in SHEETS:
        rows = read_sheet(wb, s)
        clean, coll = dedupe(rows)
        loaded[s] = (clean, coll)
        print(f"{s!r}: {len(rows)} coded rows -> {len(clean)} unique permutations kept, "
              f"{len(coll)} later duplicate rows discarded")
    wb.close()
    if args.dry_run:
        return 0
    conn = pyodbc.connect(CS, autocommit=True)
    cur = conn.cursor()
    cur.fast_executemany = True
    # tables from the first (sql/39 v1) shape lack PermutationNo -> recreate
    cur.execute("IF OBJECT_ID('cfg.DeanSealSpecCollision','U') IS NOT NULL DROP TABLE cfg.DeanSealSpecCollision")
    for s_ in SHEETS:
        t_ = f"cfg.DeanSealSpec_{SHEET_TABLE[s_]}"
        cur.execute(f"IF OBJECT_ID('{t_}','U') IS NOT NULL AND COL_LENGTH('{t_}','PermutationNo') IS NULL DROP TABLE {t_}")
    apply_migration(conn)
    cur.execute("DELETE FROM cfg.DeanSealSpecDiscarded")
    cur.execute("DELETE FROM cfg.DeanSealSheet")
    for s, (clean, coll) in loaded.items():
        tbl = SHEET_TABLE[s]
        cur.execute(f"DELETE FROM cfg.DeanSealSpec_{tbl}")
        cur.executemany(
            f"INSERT INTO cfg.DeanSealSpec_{tbl} (PermutationNo, ComboHash, ComboKey, SealCode, "
            f"PriceRaw, PriceAmount, PriceStatus, SourceRow) VALUES (?,?,?,?,?,?,?,?)",
            [(r[8], r[3], r[2], r[1], r[4], r[5], r[6], r[7]) for r in clean])
        if coll:
            cur.executemany(
                "INSERT INTO cfg.DeanSealSpecDiscarded (SealRefKey, ComboHash, ComboKey, SealCode, "
                "KeptSealCode, PriceRaw, SourceRow) VALUES (?,?,?,?,?,?,?)",
                [(r[0], r[3], r[2], r[1], r[8][1], r[4], r[7]) for r in coll])
        cur.execute("INSERT INTO cfg.DeanSealSheet (SealRefKey, SpecTable, HasGasket) VALUES (?,?,?)",
                    s, f"DeanSealSpec_{tbl}", 1 if s in GASKET_SHEETS else 0)
        n = cur.execute(f"SELECT COUNT(*) FROM cfg.DeanSealSpec_{tbl}").fetchone()[0]
        print(f"  cfg.DeanSealSpec_{tbl}: {n} rows")
    nc = cur.execute("SELECT COUNT(*) FROM cfg.DeanSealSpecDiscarded").fetchone()[0]
    print(f"  cfg.DeanSealSpecDiscarded: {nc} rows")
    cur.execute("IF OBJECT_ID('cfg.DeanSealSpec','U') IS NOT NULL DROP TABLE cfg.DeanSealSpec")
    print("Dropped superseded combined table cfg.DeanSealSpec (sql/38).")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

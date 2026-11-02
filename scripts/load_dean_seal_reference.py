"""DEAN D-R1 - load the per-series Seal Reference Table (capture-only).

Reads the new "Seal Reference Table" column (header on row 3) from the revised
'Pump Constraints' sheet of PumpConfiguration_Logic_0.1.xlsm and loads one row per
series into cfg.DeanSealReference (series -> seal-ref key). Idempotent (clears +
reloads the table). NOT wired into the PN; Fybroc untouched (Dean-only table).

Run:  uv run python scripts/load_dean_seal_reference.py [--dry-run]
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
SQL_PATH = Path("sql/35_Create_Dean_Seal_Reference.sql")


def _apply_migration(conn) -> None:
    """Ensure cfg.DeanSealReference exists (apply sql/35 if missing)."""
    cur = conn.cursor()
    exists = cur.execute("SELECT OBJECT_ID('cfg.DeanSealReference','U')").fetchone()[0]
    if exists is not None:
        return
    text = SQL_PATH.read_text(encoding="utf-8-sig")
    for batch in re.split(r"(?im)^\s*GO\s*$", text):
        b = batch.strip()
        if b:
            cur.execute(b)
            while cur.nextset():
                pass
    print("Applied sql/35 (cfg.DeanSealReference created).")


def read_seal_reference(wb) -> list[tuple[str, str, int]]:
    """Yield (series, seal_ref_key, source_row). Identity cols (A Number/Series/
    Size) on row 3; the Seal Reference Table header is also on row 3. Data rows 4+.
    One (series -> key) is taken from the first data row of each series."""
    ws = wb["Pump Constraints"]
    # locate the Series column and the Seal Reference Table column from row 3
    series_col = srt_col = None
    for c in range(1, ws.max_column + 1):
        v = ws.cell(row=3, column=c).value
        if v is None:
            continue
        h = str(v).strip().lower()
        if h == "series":
            series_col = c
        elif h == "seal reference table":
            srt_col = c
    if series_col is None or srt_col is None:
        raise SystemExit(f"Could not find Series ({series_col}) / "
                         f"Seal Reference Table ({srt_col}) columns on row 3.")

    out: list[tuple[str, str, int]] = []
    seen: dict[str, str] = {}
    for r in range(4, ws.max_row + 1):
        ser = ws.cell(row=r, column=series_col).value
        if ser is None or str(ser).strip() == "":
            continue
        ser = str(ser).strip()
        key = ws.cell(row=r, column=srt_col).value
        key = "" if key is None else str(key).strip()
        if ser in seen:
            # Flag a genuine conflict (same series, different non-empty key).
            if key and seen[ser] and key != seen[ser]:
                print(f"  WARN series {ser}: conflicting seal-ref '{seen[ser]}' vs '{key}' "
                      f"(row {r}); keeping first.")
            continue
        if key == "":
            # don't register a series on an empty cell; wait for a populated row
            continue
        seen[ser] = key
        out.append((ser, key, r))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    wb = load_workbook(WB_PATH, data_only=True, read_only=True)
    rows = read_seal_reference(wb)
    wb.close()
    print(f"Seal Reference Table: {len(rows)} series-> seal-ref keys parsed.")
    distinct = sorted({k for _, k, _ in rows})
    print(f"  distinct keys: {distinct}")
    if args.dry_run:
        for s, k, r in rows:
            print(f"   {s} -> {k!r} (row {r})")
        return 0

    conn = pyodbc.connect(CS, autocommit=True)
    _apply_migration(conn)
    cur = conn.cursor()
    cur.execute("DELETE FROM cfg.DeanSealReference")
    cur.fast_executemany = True
    cur.executemany(
        "INSERT INTO cfg.DeanSealReference (SeriesCode, SealRefKey, SourceRow) VALUES (?, ?, ?)",
        rows,
    )
    n = cur.execute("SELECT COUNT(*) FROM cfg.DeanSealReference").fetchone()[0]
    print(f"Loaded {n} rows into cfg.DeanSealReference.")
    conn.close()
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

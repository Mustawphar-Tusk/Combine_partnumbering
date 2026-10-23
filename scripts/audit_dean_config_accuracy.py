"""D110 exhaustive Dean CONFIG DATA ACCURACY audit (Excel sheet as oracle).

Proves, for EVERY (series, size, field), that cfg.SeriesFieldOption (DEAN) matches
the authoritative "Pump Constraints" sheet of PumpConfiguration_Logic_0.1.xlsm
EXACTLY:
  * every STD/X cell in the sheet is present in the DB (no MISSING),
  * every DB row corresponds to an STD/X cell in the sheet (no EXTRA),
  * the STD flag / SelectionMarker matches the sheet cell (no STD-MISMATCH).

The sheet is re-parsed INDEPENDENTLY here (own column-group walk) so this is a
true oracle, not a replay of the loader's parse. Only the canonicalization
contract (norm_label field-code mapping + _norm_value value normalization) is
reused from the loader, because that IS the agreed contract between sheet labels
and DB codes.

Expectations are derived entirely from the sheet (nothing hardcoded). Exits 0 iff
the DB is a byte-exact image of the sheet's STD/X matrix; non-zero on any diff.

Run:  $env:PYTHONPATH="."; python scripts/audit_dean_config_accuracy.py
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import pyodbc
from openpyxl import load_workbook

# Reuse ONLY the canonicalization contract from the loader (not its parse).
from scripts.d110_load_dean_config_v01 import norm_label, _norm_value  # type: ignore

CS = ('DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;'
      'DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;Encrypt=yes;'
      'TrustServerCertificate=yes;')
WB_PATH = Path("workbooks/Dean/PumpConfiguration_Logic_0.1.xlsm")


def _col_letter(i0: int) -> str:
    s, c = "", i0 + 1
    while c > 0:
        c, r = divmod(c - 1, 26)
        s = chr(65 + r) + s
    return s


def parse_sheet_oracle():
    """Independent re-parse of 'Pump Constraints'.

    Returns:
      expected: {(series, size): {field_code: {norm_value: 'STD'|'X'}}}
      meta: dict with counts + the raw (series,size) order and any anomalies.
    """
    wb = load_workbook(WB_PATH, data_only=True, read_only=True)
    ws = wb["Pump Constraints"]
    grid = [list(r) for r in ws.iter_rows(min_row=1, max_row=ws.max_row,
                                          values_only=True)]
    wb.close()

    def g(row_idx0, col_idx0):
        row = grid[row_idx0] if 0 <= row_idx0 < len(grid) else []
        return row[col_idx0] if 0 <= col_idx0 < len(row) else None

    ncol = max((len(r) for r in grid), default=0)
    row2 = 1  # 0-based -> sheet row 2 = group headers
    row3 = 2  # sheet row 3 = value headers + identity

    # group header positions on row 2 (independent contiguous-left assignment)
    group_at = {}
    for c0 in range(ncol):
        v = g(row2, c0)
        if v is not None and str(v).strip():
            group_at[c0] = str(v).strip()
    group_cols = sorted(group_at)

    def group_for(c0):
        chosen = None
        for gc in group_cols:
            if gc <= c0:
                chosen = group_at[gc]
            else:
                break
        return chosen

    # identity columns on row 3
    id_cols = {}
    for c0 in range(ncol):
        v = g(row3, c0)
        if v is None:
            continue
        h = str(v).strip().lower()
        if h == "a number":
            id_cols["a"] = c0
        elif h == "series":
            id_cols["series"] = c0
        elif h == "size":
            id_cols["size"] = c0
    assert {"series", "size"} <= set(id_cols), f"identity cols missing: {id_cols}"

    # value columns -> (field_code, raw_value_header)
    col_field = {}
    col_value = {}
    unmapped_groups = set()
    mapped_fields = set()
    for c0 in range(ncol):
        vh = g(row3, c0)
        if vh is None or str(vh).strip() == "":
            continue
        if c0 in id_cols.values():
            continue
        grp = group_for(c0)
        if grp is None:
            continue
        code = norm_label(grp)
        if code is None:
            unmapped_groups.add(grp)
            continue
        col_field[c0] = code
        col_value[c0] = str(vh).strip()
        mapped_fields.add(code)

    # data rows 4.. (0-based 3..) while series present
    expected = {}
    order = []
    n_cells = 0
    dup_value_headers = 0
    sc, zc = id_cols["series"], id_cols["size"]
    ac = id_cols.get("a")
    for r0 in range(3, len(grid)):
        ser = g(r0, sc)
        if ser is None or str(ser).strip() == "":
            continue
        series = str(ser).strip()
        size = g(r0, zc)
        size = str(size).strip() if size is not None else ""
        key = (series, size)
        fieldmap = expected.setdefault(key, {})
        order.append(key)
        for c0, code in col_field.items():
            mk = g(r0, c0)
            mk = str(mk).strip().upper() if mk is not None else ""
            if mk not in ("STD", "X"):
                continue
            nv = _norm_value(code, col_value[c0])
            vm = fieldmap.setdefault(code, {})
            if nv in vm:
                dup_value_headers += 1  # duplicate value header column collapses
            vm[nv] = mk
            n_cells += 1

    # collapse means the stored count can be < raw cell count; recompute stored
    stored_cells = sum(len(vm) for fm in expected.values() for vm in fm.values())
    meta = {
        "models": len(expected),
        "series": len({s for s, _ in expected}),
        "fields": len(mapped_fields),
        "raw_cells": n_cells,
        "stored_cells": stored_cells,
        "dup_value_headers": dup_value_headers,
        "unmapped_groups": sorted(unmapped_groups),
        "order": order,
    }
    return expected, meta


def read_db():
    """{(series, size): {field: {value: 'STD'|'X'}}} from DB DEAN active rows."""
    conn = pyodbc.connect(CS)
    c = conn.cursor()
    dean = c.execute("SELECT PumpFamilyId FROM cfg.PumpFamily "
                     "WHERE FamilyCode='DEAN'").fetchone()[0]
    rows = c.execute(
        "SELECT SeriesCode, SizeCode, FieldCode, OptionValue, SelectionMarker, IsStandard "
        "FROM cfg.SeriesFieldOption WHERE PumpFamilyId=? AND IsActive=1", dean
    ).fetchall()
    conn.close()
    actual = {}
    dup = 0
    for ser, size, field, value, marker, is_std in rows:
        key = (str(ser).strip(), str(size).strip() if size is not None else "")
        mk = (marker or "").strip().upper()
        if mk not in ("STD", "X"):
            mk = "STD" if is_std else "X"
        vm = actual.setdefault(key, {}).setdefault(field, {})
        if value in vm:
            dup += 1
        vm[value] = mk
    return actual, dup, len(rows)


def main():
    print("=" * 92)
    print("DEAN CONFIG DATA-ACCURACY AUDIT (Pump Constraints sheet == DB, per field)")
    print("=" * 92)

    expected, meta = parse_sheet_oracle()
    actual, db_dup, db_rows = read_db()

    print(f"sheet oracle: {meta['models']} models, {meta['series']} series, "
          f"{meta['fields']} mapped fields, {meta['raw_cells']} raw STD/X cells "
          f"-> {meta['stored_cells']} distinct (model,field,value) "
          f"(dup value headers collapsed: {meta['dup_value_headers']})")
    print(f"DB:           {db_rows} DEAN active rows "
          f"(duplicate (model,field,value) in DB: {db_dup})")
    if meta["unmapped_groups"]:
        print(f"  NOTE unmapped (skipped) group headers: {meta['unmapped_groups']}")

    passed = failed = 0

    def ok(cond, msg):
        nonlocal passed, failed
        if cond:
            passed += 1
        else:
            failed += 1
            print(f"  [FAIL] {msg}")

    # (0) structural: same set of (series,size) models, and no DB dup
    exp_models = set(expected)
    act_models = set(actual)
    ok(db_dup == 0, f"DB has duplicate (model,field,value) rows: {db_dup}")
    ok(exp_models == act_models,
       f"model set differs: only-sheet={sorted(exp_models - act_models)[:8]} "
       f"only-db={sorted(act_models - exp_models)[:8]}")

    # (1..3) per (model, field) exact equality
    missing = []      # sheet has, DB lacks
    extra = []        # DB has, sheet lacks
    std_mismatch = []  # value present both sides but marker differs
    field_missing = []  # whole field present one side only for a model

    all_models = sorted(exp_models | act_models)
    for key in all_models:
        ef = expected.get(key, {})
        af = actual.get(key, {})
        for field in set(ef) | set(af):
            ev = ef.get(field)
            av = af.get(field)
            if ev is None:
                field_missing.append((key, field, "DB-only-field"))
                for val in av:
                    extra.append((key, field, val, av[val]))
                continue
            if av is None:
                field_missing.append((key, field, "sheet-only-field"))
                for val in ev:
                    missing.append((key, field, val, ev[val]))
                continue
            for val in set(ev) | set(av):
                em = ev.get(val)
                am = av.get(val)
                if em is not None and am is None:
                    missing.append((key, field, val, em))
                elif am is not None and em is None:
                    extra.append((key, field, val, am))
                elif em != am:
                    std_mismatch.append((key, field, val, f"sheet={em} db={am}"))

    print("\n=== per-(model,field) exact equality ===")
    ok(len(missing) == 0, f"{len(missing)} MISSING (sheet has, DB lacks)")
    ok(len(extra) == 0, f"{len(extra)} EXTRA (DB has, sheet lacks)")
    ok(len(std_mismatch) == 0, f"{len(std_mismatch)} STD/marker mismatches")
    ok(len(field_missing) == 0, f"{len(field_missing)} whole-field presence diffs")

    def sample(lst, n=12):
        for item in lst[:n]:
            print("     ", item)
        if len(lst) > n:
            print(f"      ... (+{len(lst) - n} more)")

    if missing:
        print("  -- MISSING sample --"); sample(missing)
    if extra:
        print("  -- EXTRA sample --"); sample(extra)
    if std_mismatch:
        print("  -- STD-MISMATCH sample --"); sample(std_mismatch)
    if field_missing:
        print("  -- FIELD-PRESENCE sample --"); sample(field_missing)

    # (4) STD-count parity (exactly one authoritative STD count from the sheet)
    exp_std = sum(1 for fm in expected.values() for vm in fm.values()
                  for mk in vm.values() if mk == "STD")
    act_std = sum(1 for fm in actual.values() for vm in fm.values()
                  for mk in vm.values() if mk == "STD")
    print("\n=== STD-flag parity ===")
    ok(exp_std == act_std, f"STD count differs: sheet={exp_std} db={act_std}")
    print(f"  sheet STD cells={exp_std}  db STD rows={act_std}")

    # (5) each model that has any STD field: at most one STD per field
    multi_std = []
    for key, fm in actual.items():
        for field, vm in fm.items():
            stds = [v for v, mk in vm.items() if mk == "STD"]
            if len(stds) > 1:
                multi_std.append((key, field, stds))
    print("\n=== at most one STD per (model,field) ===")
    ok(len(multi_std) == 0, f"{len(multi_std)} (model,field) with >1 STD")
    if multi_std:
        sample(multi_std)

    print("\n" + "=" * 92)
    print(f"RESULT: {passed} passed, {failed} failed")
    print("=" * 92)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

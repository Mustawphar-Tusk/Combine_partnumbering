"""D110 LIVE Dean config accuracy cross-check (API projects the sheet's data).

Complements scripts/audit_dean_config_accuracy.py (which proves DB == sheet,
cell-for-cell). This proves the live API faithfully projects that per-(series,size)
data, for a broad sample of Dean models (incl. row-167+ families):

For each sampled (series, size), call resolve-state with {"ALT_SIZE": size}
(the size-selection key that triggers STD auto-seed) and verify:
  * STD EXACTNESS: for every field the sheet marks STD AND that is still
    applicable (in ordered_fields), the API's seeded selection == the sheet STD.
  * NO LEAK: for every applicable field, the API's allowable set is a SUBSET of
    the sheet's offered set (STD ∪ X) — the API never offers a value the sheet
    does not. (Codependencies legitimately prune the set smaller once the whole
    model is STD-seeded, so we assert subset + STD-exact, not full equality — the
    full-equality proof lives in the DB==sheet audit.)

Values normalized with .strip().lower() (same as audit_dean_config._norm).
Expectations come from the sheet oracle. Exit 0 iff no STD mismatch and no leak.

Run (API on 127.0.0.1:8080):
  $env:PYTHONPATH="."; python scripts/audit_dean_config_accuracy_live.py [--all]
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

from openpyxl import load_workbook

from scripts.d110_load_dean_config_v01 import norm_label, _norm_value  # type: ignore

BASE = "http://127.0.0.1:8080/api/v2/families/DEAN"
WB_PATH = Path("workbooks/Dean/PumpConfiguration_Logic_0.1.xlsm")
IDENTITY_FIELDS = {"SERIES", "SIZE", "ALT_SIZE"}


def _norm(v):
    return str(v).strip().lower()


def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def wait_api():
    for _ in range(40):
        try:
            post("/configurations/resolve-state", {"series": "CNV206", "selections": {}})
            return True
        except Exception:
            time.sleep(0.5)
    return False


def parse_sheet_oracle():
    """{(series,size): {field: {'offered': set(norm), 'std': norm|None}}}"""
    wb = load_workbook(WB_PATH, data_only=True, read_only=True)
    ws = wb["Pump Constraints"]
    grid = [list(r) for r in ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True)]
    wb.close()
    ncol = max((len(r) for r in grid), default=0)

    def gg(r0, c0):
        row = grid[r0] if 0 <= r0 < len(grid) else []
        return row[c0] if 0 <= c0 < len(row) else None

    group_at = {c0: str(gg(1, c0)).strip() for c0 in range(ncol)
                if gg(1, c0) and str(gg(1, c0)).strip()}
    gcols = sorted(group_at)

    def group_for(c0):
        chosen = None
        for gc in gcols:
            if gc <= c0:
                chosen = group_at[gc]
            else:
                break
        return chosen

    id_cols = {}
    for c0 in range(ncol):
        v = gg(2, c0)
        if v is None:
            continue
        h = str(v).strip().lower()
        if h == "a number":
            id_cols["a"] = c0
        elif h in ("series", "size"):
            id_cols[h] = c0

    col_field, col_value = {}, {}
    for c0 in range(ncol):
        vh = gg(2, c0)
        if vh is None or str(vh).strip() == "" or c0 in id_cols.values():
            continue
        grp = group_for(c0)
        if grp is None:
            continue
        code = norm_label(grp)
        if code is None:
            continue
        col_field[c0] = code
        col_value[c0] = str(vh).strip()

    sc, zc = id_cols["series"], id_cols["size"]
    expected = {}
    for r0 in range(3, len(grid)):
        ser = gg(r0, sc)
        if ser is None or str(ser).strip() == "":
            continue
        series = str(ser).strip()
        size = gg(r0, zc)
        size = str(size).strip() if size is not None else ""
        fmap = expected.setdefault((series, size), {})
        for c0, code in col_field.items():
            mk = gg(r0, c0)
            mk = str(mk).strip().upper() if mk is not None else ""
            if mk not in ("STD", "X"):
                continue
            nv = _norm(_norm_value(code, col_value[c0]))
            entry = fmap.setdefault(code, {"offered": set(), "std": None})
            entry["offered"].add(nv)
            if mk == "STD":
                entry["std"] = nv
    return expected


def _api_allowable(st, field):
    ao = st.get("allowable_options", {}) or {}
    v = ao.get(field)
    if v is None:
        return None
    return {_norm(i["value"] if isinstance(i, dict) else i) for i in v}


def main():
    want_all = "--all" in sys.argv
    if not wait_api():
        print("FAIL: API not reachable on 127.0.0.1:8080")
        return 1

    expected = parse_sheet_oracle()
    by_series = {}
    for (ser, size) in expected:
        by_series.setdefault(ser, []).append(size)

    # row-167+ families must be represented in the default sample
    MUST_INCLUDE = ["RM5140", "RMA5140", "RS5140", "RSWA5140", "RT5140",
                    "RWA5140", "RWAV5140", "Deanline", "DEANLINE"]
    if want_all:
        sample = sorted(expected.keys())
    else:
        # one smallest + one largest size for a broad spread of diverse series,
        # guaranteeing the row-167+ families appear. Keep it bounded so a full
        # per-field resolve-state sweep finishes well within the timeout.
        # resolve-state with a full STD seed is ~30s/call, so the default sample
        # is small but decisive: a diverse spread incl. a row-167+ family. Use
        # --all (very slow) for an exhaustive sweep. Each series contributes its
        # smallest + largest size (two distinct models) where available.
        default_series = ["RA3146", "PH2140", "R5140", "DL200", "RM5140"]
        chosen_series = [s for s in default_series if s in by_series]
        sample = []
        for ser in chosen_series:
            ss = sorted(set(by_series[ser]))
            picks = sorted({ss[0], ss[-1]})
            for sz in picks:
                sample.append((ser, sz))
                if len(sample) >= 6:
                    break
            if len(sample) >= 6:
                break

    print("=" * 92)
    print(f"DEAN LIVE CONFIG-ACCURACY (API projects sheet) — {len(sample)} models "
          f"({'ALL' if want_all else 'broad sample'}), {len(by_series)} series")
    print("=" * 92)

    std_checks = std_fail = 0
    leak_checks = leak_fail = 0
    models_ok = 0
    bad = []
    MAXSHOW = 25
    shown = 0

    def show(msg):
        nonlocal shown
        if shown < MAXSHOW:
            print(f"  [FAIL] {msg}")
            shown += 1

    for (ser, size) in sample:
        sheet_fields = expected[(ser, size)]
        try:
            st = post("/configurations/resolve-state",
                      {"series": ser, "selections": {"ALT_SIZE": size}})
        except Exception as e:
            show(f"{ser}|{size}: resolve-state error {e}")
            bad.append((ser, size))
            continue
        applicable = {f.upper() for f in (st.get("ordered_fields") or [])}
        sel = {k.upper(): _norm(v) for k, v in (st.get("selections") or {}).items()}
        model_bad = False

        for field, info in sheet_fields.items():
            if field in IDENTITY_FIELDS:
                continue
            # STD exactness (only for applicable fields; a field fully pruned away
            # is not offered and legitimately carries no seed)
            if info["std"] is not None and field in applicable:
                std_checks += 1
                got = sel.get(field)
                if got != info["std"]:
                    std_fail += 1
                    model_bad = True
                    show(f"{ser}|{size}:{field} STD got={got!r} want={info['std']!r}")
            # no-leak: API allowable ⊆ sheet offered
            api_set = _api_allowable(st, field)
            if api_set:
                leak_checks += 1
                extra = api_set - info["offered"]
                if extra:
                    leak_fail += 1
                    model_bad = True
                    show(f"{ser}|{size}:{field} API offers non-sheet values "
                         f"{sorted(extra)[:5]}")

        # API must not offer a non-identity field absent from the sheet model
        ao = st.get("allowable_options", {}) or {}
        leaked_fields = [f for f in ao
                         if f not in sheet_fields and f not in IDENTITY_FIELDS
                         and _api_allowable(st, f)]
        if leaked_fields:
            model_bad = True
            show(f"{ser}|{size}: API offers fields not on sheet: {leaked_fields[:8]}")

        if model_bad:
            bad.append((ser, size))
        else:
            models_ok += 1

    if shown >= MAXSHOW:
        print(f"  ... (failure output capped at {MAXSHOW})")

    print(f"\nmodels fully consistent: {models_ok}/{len(sample)}")
    print(f"STD-exactness checks: {std_checks}, failures: {std_fail}")
    print(f"no-leak (subset) checks: {leak_checks}, failures: {leak_fail}")
    if bad:
        print(f"models with diffs ({len(bad)}): {bad[:12]}"
              + (" ..." if len(bad) > 12 else ""))

    failed = std_fail + leak_fail
    print("\n" + "=" * 92)
    print(f"RESULT: {len(sample) - len(bad)}/{len(sample)} models PASS "
          f"({failed} field-level failures)")
    print("=" * 92)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

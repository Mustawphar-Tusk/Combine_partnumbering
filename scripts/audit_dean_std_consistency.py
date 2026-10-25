"""D110 Dean STD-CONSISTENCY audit.

The authoritative Pump Constraints matrix marks exactly one STD value per
(series, size, field). That full STD set IS, by definition, a complete valid
shippable configuration. Therefore seeding the whole STD set must resolve with
EVERY STD value kept (none pruned) and NONE reported as incompatible.

This audit catches the class of bug where a codependency allow-list whose
vocabulary does not line up with the Pump Constraints offered values wrongly
prunes a sheet-STD value (e.g. CNV206: COOLING_PLAN=NONE + CASING_MOUNTING=NONE
flagged as a conflict though both are the sheet STD).

For each sampled (or --all) Dean (series, size):
  1. read the DB STD set for that model,
  2. POST resolve-state with {"ALT_SIZE": size} (seeds the STD set),
  3. FAIL if any STD field is reported in `conflicts`, OR a STD field's value is
     absent from its own allowable list (pruned), OR resolve is not valid.

Expectations derived from the DB; exit non-zero on any wrongly-incompatible STD.

Run (API on 127.0.0.1:8080):
  $env:PYTHONPATH="."; python scripts/audit_dean_std_consistency.py [--all]
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request

import pyodbc

BASE = "http://127.0.0.1:8080/api/v2/families/DEAN"
CS = ('DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;'
      'DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;Encrypt=yes;'
      'TrustServerCertificate=yes;')
IDENTITY_FIELDS = {"SERIES", "SIZE", "ALT_SIZE"}


def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode())


def wait_api():
    for _ in range(60):
        try:
            post("/configurations/resolve-state", {"series": "CNV206", "selections": {}})
            return True
        except Exception:
            time.sleep(0.5)
    return False


def _norm(v):
    return str(v).strip().lower()


def load_std_sets():
    """{(series,size): {field: std_value}} from DB DEAN active STD rows."""
    conn = pyodbc.connect(CS)
    c = conn.cursor()
    dean = c.execute("SELECT PumpFamilyId FROM cfg.PumpFamily "
                     "WHERE FamilyCode='DEAN'").fetchone()[0]
    rows = c.execute(
        "SELECT SeriesCode, SizeCode, FieldCode, OptionValue "
        "FROM cfg.SeriesFieldOption "
        "WHERE PumpFamilyId=? AND IsActive=1 AND IsStandard=1", dean).fetchall()
    conn.close()
    out = {}
    for ser, size, field, val in rows:
        key = (str(ser).strip(), str(size).strip() if size is not None else "")
        out.setdefault(key, {})[field] = val
    return out


def main():
    want_all = "--all" in sys.argv
    if not wait_api():
        print("FAIL: API not reachable on 127.0.0.1:8080")
        return 1

    std_sets = load_std_sets()
    by_series = {}
    for (ser, size) in std_sets:
        by_series.setdefault(ser, []).append(size)

    if want_all:
        sample = sorted(std_sets.keys())
    else:
        # broad, bounded sample (resolve-state ~30s/call). Always include CNV206
        # (the reported case) and a spread incl. a row-167+ family.
        must = ["CNV206", "PH2140", "R5140", "DL200", "RA3146", "RM5140"]
        sample = []
        for ser in must:
            if ser in by_series:
                for sz in sorted(set(by_series[ser])):
                    sample.append((ser, sz))
                    break  # one size per series keeps it bounded
        # ensure CNV206 BOTH sizes (the reported model is a specific size)
        for sz in sorted(set(by_series.get("CNV206", []))):
            if ("CNV206", sz) not in sample:
                sample.append(("CNV206", sz))

    print("=" * 92)
    print(f"DEAN STD-CONSISTENCY AUDIT — {len(sample)} models "
          f"({'ALL' if want_all else 'broad sample'}), {len(by_series)} series")
    print("=" * 92)

    passed = failed = 0
    bad_models = []
    MAXSHOW = 40
    shown = 0

    def show(msg):
        nonlocal shown
        if shown < MAXSHOW:
            print(f"  [FAIL] {msg}")
            shown += 1

    for (ser, size) in sample:
        std = std_sets[(ser, size)]
        try:
            st = post("/configurations/resolve-state",
                      {"series": ser, "selections": {"ALT_SIZE": size}})
        except Exception as e:
            show(f"{ser}|{size}: resolve-state error {e}")
            bad_models.append((ser, size))
            failed += 1
            continue

        model_bad = False

        # (a) resolve must be valid
        if st.get("valid") is not True:
            show(f"{ser}|{size}: resolve valid={st.get('valid')} errors={st.get('errors')}")
            model_bad = True

        # (b) no STD field may appear as a conflict
        conflicts = st.get("conflicts") or []
        conflict_fields = {(_c.get("field") or "").upper() for _c in conflicts}
        std_in_conflict = sorted(f for f in conflict_fields
                                 if f in std and f not in IDENTITY_FIELDS)
        if std_in_conflict:
            # include who they conflict with for clarity
            detail = []
            for _c in conflicts:
                f = (_c.get("field") or "").upper()
                if f in std_in_conflict:
                    detail.append(f"{f}={std.get(f)!r} vs {_c.get('conflicts_with')}")
            show(f"{ser}|{size}: STD field(s) reported conflicting: {detail}")
            model_bad = True

        # (c) each STD field's STD value must survive in its own allowable list
        ao = st.get("allowable_options") or {}
        for field, sval in std.items():
            if field in IDENTITY_FIELDS:
                continue
            opts = ao.get(field)
            if opts is None:
                continue  # field not applicable/offered in this projection (ok)
            vals = {_norm(o["value"] if isinstance(o, dict) else o) for o in opts}
            if _norm(sval) not in vals:
                show(f"{ser}|{size}:{field} STD {sval!r} pruned from its own "
                     f"allowable {sorted(vals)[:6]}")
                model_bad = True

        if model_bad:
            bad_models.append((ser, size))
            failed += 1
        else:
            passed += 1

    if shown >= MAXSHOW:
        print(f"  ... (failure output capped at {MAXSHOW})")

    print(f"\nmodels STD-consistent: {passed}/{len(sample)}")
    if bad_models:
        print(f"models with STD incompatibility ({len(bad_models)}): "
              f"{bad_models[:15]}" + (" ..." if len(bad_models) > 15 else ""))

    print("\n" + "=" * 92)
    print(f"RESULT: {passed} passed, {failed} failed")
    print("=" * 92)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

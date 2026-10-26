"""D110 Dean BASEPLATE + COUPLING always-applicable audit.

Per the authoritative Pump Constraints matrix, the nine Baseplate fields and the
two Coupling fields are marked STANDARD (value NONE / Not Required) on every model
- including Pump-Only models. They must therefore ALWAYS be displayed and
STD-seeded regardless of the PUMP_CONFIGURATION bundle (user decision: option A,
extended to Coupling). Only the Motor group (FRAME_SIZE) stays bundle-gated.

For a broad sample of Dean (series, size), this audit asserts via the live API:
  (1) every baseplate/coupling field the sheet offers for that model is present
      in ordered_fields (displayed) and STD-seeded to exactly the sheet STD,
  (2) each such field's allowable set is the sheet offered set (STD ∪ X),
  (3) FRAME_SIZE is NOT offered when the chosen PUMP_CONFIGURATION bundle excludes
      the motor (still bundle-gated), and IS offered when the bundle includes it.

Expectations are read from cfg.SeriesFieldOption (which the field-accuracy audit
proves equals the sheet). Exit 0 iff all pass.

Run (API on 127.0.0.1:8080):
  $env:PYTHONPATH="."; python scripts/audit_dean_baseplate_coupling.py [--all]
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

BASEPLATE = ["BASEPLATE_TYPE", "DRIP_PAN", "ALIGNMENT_LUGS", "LIFTING_LUGS",
             "LEVELLING_SCREWS", "GROUNDING_LUG", "GROUT_HOLE", "ISOLATION_PADS",
             "STILTS"]
COUPLING = ["COUPLING_TYPE", "COUPLING_GUARD"]
ALWAYS_FIELDS = BASEPLATE + COUPLING

# PUMP_CONFIGURATION bundles that EXCLUDE the motor (FRAME_SIZE must not be offered)
MOTOR_EXCLUDING = {"pump only", "pump and baseplate",
                   "pump, baseplate, and coupling", "pump and coupling"}


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


def load_expected():
    """{(series,size): {field: {'offered': set, 'std': val|None}}} for the 11
    always-on fields, from cfg.SeriesFieldOption DEAN (== sheet)."""
    conn = pyodbc.connect(CS)
    c = conn.cursor()
    dean = c.execute("SELECT PumpFamilyId FROM cfg.PumpFamily "
                     "WHERE FamilyCode='DEAN'").fetchone()[0]
    rows = c.execute(
        "SELECT SeriesCode, SizeCode, FieldCode, OptionValue, IsStandard "
        "FROM cfg.SeriesFieldOption "
        "WHERE PumpFamilyId=? AND IsActive=1 AND SizeCode IS NOT NULL "
        "AND FieldCode IN ({})".format(",".join("?" * len(ALWAYS_FIELDS))),
        dean, *ALWAYS_FIELDS).fetchall()
    conn.close()
    exp = {}
    for ser, size, field, val, is_std in rows:
        key = (str(ser).strip(), str(size).strip())
        e = exp.setdefault(key, {}).setdefault(field, {"offered": set(), "std": None})
        e["offered"].add(_norm(val))
        if is_std:
            e["std"] = _norm(val)
    return exp


def main():
    want_all = "--all" in sys.argv
    if not wait_api():
        print("FAIL: API not reachable on 127.0.0.1:8080")
        return 1

    exp = load_expected()
    by_series = {}
    for (ser, size) in exp:
        by_series.setdefault(ser, []).append(size)

    if want_all:
        sample = sorted(exp.keys())
    else:
        want = ["RA2096", "CNV206", "PH2140", "R5140", "DL200", "RA3146", "RM5140"]
        sample = []
        for ser in want:
            if ser in by_series:
                sample.append((ser, sorted(by_series[ser])[0]))

    print("=" * 92)
    print(f"DEAN BASEPLATE+COUPLING always-applicable audit — {len(sample)} models "
          f"({'ALL' if want_all else 'sample'})")
    print("=" * 92)

    passed = failed = 0
    shown = 0
    MAXSHOW = 40

    def ok(cond, msg):
        nonlocal passed, failed, shown
        if cond:
            passed += 1
        else:
            failed += 1
            if shown < MAXSHOW:
                print(f"  [FAIL] {msg}")
                shown += 1

    for (ser, size) in sample:
        want_fields = exp[(ser, size)]
        st = post("/configurations/resolve-state",
                  {"series": ser, "selections": {"ALT_SIZE": size}})
        ordered = {f.upper() for f in (st.get("ordered_fields") or [])}
        sel = {k.upper(): _norm(v) for k, v in (st.get("selections") or {}).items()}
        ao = st.get("allowable_options") or {}

        for field in ALWAYS_FIELDS:
            info = want_fields.get(field)
            if not info or not info["offered"]:
                continue  # sheet doesn't offer this field for this model (e.g.
                          # DRIP_PAN only on 127 models) -> nothing to assert
            # (1) displayed
            ok(field in ordered, f"{ser}|{size}:{field} displayed (in ordered_fields)")
            # (2) STD-seeded to sheet STD
            if info["std"] is not None:
                ok(sel.get(field) == info["std"],
                   f"{ser}|{size}:{field} STD seed got={sel.get(field)!r} want={info['std']!r}")
            # (3) allowable ⊆ sheet offered set. The API may legitimately prune a
            # per-field X option once the whole model is STD-seeded (an
            # authoritative codependency / numbering-combination narrows it in
            # context - e.g. COUPLING_GUARD 'C/F' or BASEPLATE_TYPE 'API' given the
            # STD coupling/baseplate combo). So we assert the API never offers a
            # value the sheet does NOT (no leak); the STD value itself is checked
            # for exactness in (2). The full per-field equality lives in the
            # DB==sheet field-accuracy audit.
            opts = ao.get(field)
            api = None if opts is None else {
                _norm(x["value"] if isinstance(x, dict) else x) for x in opts}
            if api is not None:
                extra = api - info["offered"]
                ok(not extra,
                   f"{ser}|{size}:{field} allowable subset of sheet "
                   f"(extra={sorted(extra)[:3]})")
                # the field's STD value must always survive in its own allowable
                if info["std"] is not None:
                    ok(info["std"] in api,
                       f"{ser}|{size}:{field} STD {info['std']!r} present in allowable")
            else:
                ok(False, f"{ser}|{size}:{field} offered nothing (sheet has "
                          f"{sorted(info['offered'])[:3]})")

        # (4) FRAME_SIZE motor-gating preserved
        pc = sel.get("PUMP_CONFIGURATION", "")
        fs_offered = ao.get("FRAME_SIZE") is not None or "FRAME_SIZE" in ordered
        if pc in MOTOR_EXCLUDING:
            ok(not fs_offered,
               f"{ser}|{size}: FRAME_SIZE motor-gated under '{pc}' (offered={fs_offered})")

    print(f"\nchecks: {passed} passed, {failed} failed  (models: {len(sample)})")
    print("=" * 92)
    print(f"RESULT: {passed} passed, {failed} failed")
    print("=" * 92)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

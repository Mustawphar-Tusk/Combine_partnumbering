"""D110 Dean segment-numbering RESOLVE audit (nearest-combination snap).

The Pump Constraints STD seed for some models is a wet-end / power-frame /
baseplate combination the Wet End / Power Frame / Baseplate Numbering sheets do
not enumerate (two authoritative sheets disagree - e.g. RA3146 STD CASING_MOUNTING
='Yoke Foot' with Ductile Iron, which the Wet End sheet only codes with Not
Required / Required). Previously the segment resolved to '????' and the whole PN
was unbuildable.

Per option A the PART NUMBER snaps to the NEAREST enumerated combination's code
(the displayed configuration keeps its authoritative Pump-Constraints STD). This
audit asserts, for a broad sample of Dean (series, size):

  (1) the STD-seeded config resolves WET_END, POWER_FRAME and BASEPLATE to a code
      that is NON-'????', width-correct, and is a real enumerated combination's
      Alphanumeric Code for that segment (the snap never invents a code),
  (2) the full resolved Part Number contains no '?' at all,
  (3) python == SQL PN parity holds (parity_ok).

Expectations derive from stg.SegmentCombinationImport (the loaded numbering) and
the live resolver. Exit 0 iff all pass.

Run (API on 127.0.0.1:8080):
  $env:PYTHONPATH="."; python scripts/audit_dean_wet_end_resolve.py [--all]
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

# PN payload key -> (segment code, expected width)
SNAP_SEGMENTS = {
    "wet_end": ("WET_END_OPTIONS", 4),
    "power_frame_options": ("POWER_FRAME_OPTIONS", 4),
    "baseplate_options": ("BASEPLATE_OPTIONS", 2),
}


def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def wait_api():
    for _ in range(60):
        try:
            post("/configurations/resolve-state", {"series": "CNV206", "selections": {}})
            return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    want_all = "--all" in sys.argv
    if not wait_api():
        print("FAIL: API not reachable on 127.0.0.1:8080")
        return 1

    conn = pyodbc.connect(CS)
    c = conn.cursor()
    dean = c.execute("SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode='DEAN'").fetchone()[0]
    bid = c.execute("SELECT TOP 1 ImportBatchId FROM stg.SegmentCombinationImportBatch "
                    "WHERE FamilyCode='DEAN' ORDER BY ImportBatchId DESC").fetchone()[0]
    # valid code sets per segment (every enumerated Alphanumeric Code)
    code_sets = {}
    for _k, (seg, _w) in SNAP_SEGMENTS.items():
        code_sets[seg] = {r[0] for r in c.execute(
            "SELECT DISTINCT SegmentValue FROM stg.SegmentCombinationImport "
            "WHERE ImportBatchId=? AND SegmentCode=?", bid, seg).fetchall()}

    # sample models (series,size); default spread incl RA3146 (reported) + row-167+
    models = c.execute(
        "SELECT DISTINCT SeriesCode, SizeCode FROM cfg.SeriesFieldOption "
        "WHERE PumpFamilyId=? AND IsActive=1 AND SizeCode IS NOT NULL", dean).fetchall()
    by_series = {}
    for ser, sz in models:
        by_series.setdefault(ser, []).append(sz)
    if want_all:
        sample = sorted((s, z) for s, zs in by_series.items() for z in zs)
    else:
        want = ["RA3146", "RA2096", "CNV206", "PH2140", "R5140", "DL200",
                "RM5140", "RWAV4096"]
        sample = [(s, sorted(by_series[s])[0]) for s in want if s in by_series]

    print("=" * 92)
    print(f"DEAN SEGMENT-RESOLVE audit (nearest-combo snap) — {len(sample)} models "
          f"({'ALL' if want_all else 'sample'})")
    print("=" * 92)

    passed = failed = 0
    bad = []

    def ok(cond, msg):
        nonlocal passed, failed
        if cond:
            passed += 1
        else:
            failed += 1
            print(f"  [FAIL] {msg}")

    for ser, sz in sample:
        st = post("/configurations/resolve-state",
                  {"series": ser, "selections": {"ALT_SIZE": sz}})
        sel = {k: v for k, v in (st.get("selections") or {}).items()}
        sel["SERIES"] = ser
        r = post("/configured-products/resolve",
                 {"series": ser, "selections": sel, "requested_by": "wetend-audit"})
        pn = r.get("part_number") or ""
        dbg = r.get("segment_debug") or {}
        model_bad = False

        # (1) each snap segment resolves to a valid enumerated code, non-????
        for key, (seg, width) in SNAP_SEGMENTS.items():
            code = dbg.get(key)
            if code is None:
                continue
            # BASEPLATE gated to '00' when BASEPLATE_TYPE NONE/blank is legitimate
            if key == "baseplate_options" and code == "00":
                continue
            good = ("?" not in str(code) and len(str(code)) == width
                    and str(code) in code_sets[seg])
            if not good:
                ok(False, f"{ser}|{sz}: {seg} code={code!r} not a valid enumerated "
                          f"{width}-char code")
                model_bad = True
            else:
                passed += 1

        # (2) full PN has no '?'
        if "?" in pn:
            ok(False, f"{ser}|{sz}: PN still contains '?': {pn}")
            model_bad = True
        else:
            passed += 1

        # (3) python==sql parity
        if r.get("parity_ok") is not True:
            ok(False, f"{ser}|{sz}: parity_ok={r.get('parity_ok')} "
                      f"(py={dbg.get('py_pn')} sql={pn})")
            model_bad = True
        else:
            passed += 1

        if model_bad:
            bad.append((ser, sz))

    conn.close()
    print(f"\nmodels fully resolved: {len(sample) - len(bad)}/{len(sample)}")
    if bad:
        print(f"models with unresolved/parity issues: {bad[:12]}")
    print("\n" + "=" * 92)
    print(f"RESULT: {passed} passed, {failed} failed")
    print("=" * 92)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

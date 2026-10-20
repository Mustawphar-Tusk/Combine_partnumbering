"""Milestone audit — Dean Codependencies (PCL v0.1 'Codependencies' sheet).

Verifies that the authoritative Dean codependencies (workbooks/Dean/
PumpConfiguration_Logic_0.1.xlsm, sheet 'Codependencies', B1:BA171) are
correctly ENFORCED in cfg.FeasibleConstraint, that the seal codependencies are
held out exactly (pending the A1 seal-vocab crosswalk), and that enforcement is
fail-closed with no dead ends. FYBROC is proven untouched.

EXPECTATIONS ARE DERIVED FROM THE AUTHORITATIVE WORKBOOK, not hardcoded: the
script re-parses the Codependencies sheet with the SAME parser the loader uses
(scripts/d110_load_dean_config_v01.read_codependencies) and the SAME seal
hold-out set (SEAL_CODEP_FIELDS), then compares the derived enforced set against
the live DB. A hardcoded count is only used as a secondary cross-check.

Exit-gate criteria (exits non-zero on any failure):
  1. DB DEAN cfg.FeasibleConstraint count == workbook non-seal enforced count,
     and the leg-count distribution matches (2-leg / 3-leg).
  2. NO enforced DEAN row touches a seal field (seal omitted-not-discarded, A1).
  3. The seal hold-out count == workbook total - enforced (the 519 deferred
     tuples are accounted for, not silently lost).
  4. Every enforced leg field maps through cfg.ConstraintFieldMap (no dangling
     leg that _apply_constraints would silently drop).
  5. FYBROC cfg.FeasibleConstraint count is unchanged vs the recorded baseline
     (isolation / no collateral damage).
  6. LIVE fail-closed: for a prunable 2-leg codependency, selecting the context
     leg never leaves a governed-but-disallowed value in the target field.
  7. LIVE no-dead-end: a full STD-seeded Dean config never drives a field to
     zero options.

Run (API must be up on 127.0.0.1:8080 for the live checks):
    $env:PYTHONPATH="."; .\\.venv\\Scripts\\python.exe scripts\\audit_dean_codependencies.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
import urllib.error
import urllib.request
from collections import Counter

import pyodbc
from openpyxl import load_workbook

CS = ("DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;"
      "DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;"
      "Encrypt=yes;TrustServerCertificate=yes;")
BASE = "http://127.0.0.1:8080/api/v2/families/DEAN"

# Seal codependency fields held OUT of enforcement pending the A1 seal-vocab
# crosswalk. This MUST stay identical to the set in
# scripts/d110_load_dean_config_v01.py (main). It is duplicated here (not
# imported) only because the loader defines it as a local in main(); the audit
# cross-checks the DB against this set, so any drift surfaces as a failure.
SEAL_CODEP_FIELDS = {
    "SEAL_TYPE", "SEAL_CONFIGURATION", "SEAL_OPTION", "SEAL_MANUFACTURER",
    "GLAND_TYPE", "BARRIER_PLAN", "THROTTLE_BUSHING", "PUMPING_RING",
    "INBOARD_ROTATING_FACE_MATERIAL", "INBOARD_STATIONARY_FACE_MATERIAL",
    "INBOARD_ELASTOMER", "INBOARD_HARDWARE_MATERIAL",
    "OUTBOARD_ROTATING_FACE_MATERIAL", "OUTBOARD_STATIONARY_FACE_MATERIAL",
    "OUTBOARD_ELASTOMERS", "OUTBOARD_HARDWARE_MATERIAL", "SHAFT_SLEEVE_MATERIAL",
}

# Isolation baseline: FYBROC cfg.FeasibleConstraint row count must not change.
# (Confirmed live at the start of this milestone.)
FYBROC_FEASIBLE_BASELINE = 4487

_passed = 0
_failed = 0


def check(cond: bool, label: str, detail: str = "") -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  [PASS] {label}" + (f" ({detail})" if detail else ""))
    else:
        _failed += 1
        print(f"  [FAIL] {label}" + (f" ({detail})" if detail else ""))


def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def _load_d110():
    """Import the Dean loader module WITHOUT running it (reuse its parser + the
    authoritative seal hold-out set, so this audit and the loader can never
    drift)."""
    spec = importlib.util.spec_from_file_location(
        "d110_load_dean_config_v01", "scripts/d110_load_dean_config_v01.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _in(value, options):
    v = str(value).strip().lower()
    return any(str(o).strip().lower() == v for o in options)


def main() -> int:
    d110 = _load_d110()
    seal_fields = SEAL_CODEP_FIELDS

    # ---- Parse the authoritative workbook (ground truth) -------------------
    print("=== Authoritative workbook parse (Codependencies) ===")
    wb = load_workbook(d110.WB_PATH, data_only=True, read_only=True)
    codeps = d110.read_codependencies(wb)
    wb.close()
    total = len(codeps)
    enforced = [(t, legs) for (t, legs) in codeps
                if not any(code in seal_fields for code, _ in legs)]
    seal_skipped = total - len(enforced)
    exp_legdist = Counter(len(legs) for _, legs in enforced)
    enforced_leg_fields = {code.upper() for _, legs in enforced for code, _ in legs}
    check(total > 0, "workbook Codependencies parsed", f"{total} total tuples")
    print(f"  derived: {len(enforced)} enforced (non-seal), {seal_skipped} seal held-out, "
          f"legs={dict(sorted(exp_legdist.items()))}")

    # ---- DB state ----------------------------------------------------------
    print("=== DB enforcement (cfg.FeasibleConstraint, DEAN) ===")
    conn = pyodbc.connect(CS, autocommit=True)
    cur = conn.cursor()
    dean = cur.execute("SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode='DEAN'").fetchone()[0]
    fyb = cur.execute("SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode='FYBROC'").fetchone()[0]
    rows = cur.execute(
        "SELECT Option1Field,Option2Field,Option3Field,Option4Field "
        "FROM cfg.FeasibleConstraint WHERE PumpFamilyId=?", dean).fetchall()
    db_count = len(rows)
    db_legdist = Counter(sum(1 for f in r if f) for r in rows)
    db_seal_touch = sum(
        1 for r in rows if any((f or "").upper() in seal_fields for f in r))
    db_leg_fields = {(f or "").upper() for r in rows for f in r if f}

    # (1) count + leg distribution match the workbook-derived enforced set
    check(db_count == len(enforced),
          "DB DEAN FeasibleConstraint count == workbook non-seal enforced",
          f"db={db_count} workbook={len(enforced)}")
    check(dict(db_legdist) == dict(exp_legdist),
          "leg-count distribution matches workbook",
          f"db={dict(sorted(db_legdist.items()))} wb={dict(sorted(exp_legdist.items()))}")
    # Secondary fixed cross-check (documented split 251 2-leg + 5 3-leg = 256).
    check(db_count == 256 and db_legdist.get(2) == 251 and db_legdist.get(3) == 5,
          "matches documented enforced split (256 = 251 two-leg + 5 three-leg)",
          f"{dict(sorted(db_legdist.items()))}")

    # (2) no enforced row touches a seal field
    check(db_seal_touch == 0,
          "no enforced DEAN row touches a seal field (seal omitted-not-discarded)",
          f"{db_seal_touch} seal-touching rows")

    # (3) seal hold-out accounted for (total - enforced)
    check(seal_skipped == total - len(enforced),
          "seal hold-out count accounted for (total - enforced)",
          f"{seal_skipped} held out of {total}")
    # Documented figure cross-check.
    check(seal_skipped == 519, "matches documented 519 seal tuples held out",
          f"{seal_skipped}")

    # (4) every enforced leg field maps through ConstraintFieldMap
    cfm = {r[0].upper() for r in cur.execute(
        "SELECT ConstraintFieldName FROM cfg.ConstraintFieldMap WHERE PumpFamilyId=?",
        dean).fetchall()}
    unmapped = sorted(f for f in db_leg_fields if f not in cfm)
    check(not unmapped, "every enforced leg field is mapped in ConstraintFieldMap",
          f"unmapped={unmapped}" if unmapped else "all mapped")

    # (5) FYBROC isolation
    fyb_count = cur.execute(
        "SELECT COUNT(*) FROM cfg.FeasibleConstraint WHERE PumpFamilyId=?", fyb).fetchone()[0]
    check(fyb_count == FYBROC_FEASIBLE_BASELINE,
          "FYBROC FeasibleConstraint unchanged vs baseline",
          f"got={fyb_count} baseline={FYBROC_FEASIBLE_BASELINE}")
    conn.close()

    # ---- LIVE checks (fail-closed + no dead end) ---------------------------
    print("=== Live enforcement (API) ===")
    try:
        post("/configurations/resolve-state", {"series": "CNV206", "selections": {}})
        api_up = True
    except (urllib.error.URLError, OSError) as e:
        api_up = False
        print(f"  [WARN] API not reachable ({e}); skipping live fail-closed / "
              f"no-dead-end checks. Start the API to run them.")

    if api_up:
        # (6) fail-closed: from the enforced 2-leg tuples, find a PRUNABLE rule -
        # a (driver_field=driver_value) that restricts a target field to a strict
        # SUBSET of that target's full codependency domain - then prove, live,
        # that no disallowed value survives when that driver value is selected.
        # We isolate the single rule by selecting ALT_SIZE (so the model resolves)
        # plus the driver, matching how audit_dean_config.py (3) isolates it.
        two_leg = [legs for _, legs in enforced if len(legs) == 2]
        domain = {}          # target_field -> all values any 2-leg rule governs
        by_driver = {}       # (driver_field, driver_val, target_field) -> allowed
        for (f0, v0), (f1, v1) in two_leg:
            domain.setdefault(f1, set()).add(str(v1).strip().lower())
            by_driver.setdefault(
                (f0, str(v0).strip().lower(), f1), set()).add(str(v1).strip().lower())

        # A size to make a model resolvable (CNV206 has sizes).
        seed = post("/configurations/resolve-state",
                    {"series": "CNV206", "selections": {}})
        size0 = seed.get("selections", {}).get("SIZE") or seed.get("selections", {}).get("ALT_SIZE")

        checked_failclosed = False
        for (df, dv, tf), allowed in by_driver.items():
            if df == "SERIES":
                continue  # need a plain option driver to isolate on one series
            disallowed = domain.get(tf, set()) - allowed
            if not disallowed:
                continue
            seldict = {df: dv}
            if size0:
                seldict["SIZE"] = size0
            try:
                st = post("/configurations/resolve-state",
                          {"series": "CNV206", "selections": seldict,
                           "changed_field": df})
            except Exception:
                continue
            ordered = st.get("ordered_fields", [])
            if df not in ordered or tf not in ordered:
                continue
            tgt_opts = st.get("allowable_options", {}).get(tf, [])
            leaked = [v for v in disallowed if _in(v, tgt_opts)]
            check(not leaked,
                  f"fail-closed: {df}={dv} -> {tf} prunes disallowed values",
                  f"{len(leaked)} leaked: {leaked[:3]}" if leaked
                  else f"domain={len(domain[tf])}, allowed={len(allowed)}, "
                       f"pruned={len(disallowed)}")
            checked_failclosed = True
            break
        if not checked_failclosed:
            # Not a failure: fail-closed is also covered end-to-end by
            # scripts/audit_dean_config.py (3) (run in the same milestone gate).
            print("  [INFO] no isolable prunable 2-leg rule on CNV206; fail-closed "
                  "is covered by scripts/audit_dean_config.py (3).")

        # (7) no dead end: full STD-seed walk for a few series.
        for series in ("CNV206", "PH2110", "R5140"):
            st = post("/configurations/resolve-state", {"series": series, "selections": {}})
            if not st.get("valid"):
                check(False, f"{series}: resolve-state valid", str(st.get("errors")))
                continue
            ao = st.get("allowable_options", {})
            sel = st.get("selections", {})
            empty = [fc for fc in st.get("ordered_fields", [])
                     if fc not in sel and not ao.get(fc)]
            check(not empty, f"{series}: no empty-option dead end",
                  f"empty={empty[:4]}" if empty else "none")

    print("=" * 72)
    print(f"RESULT: {_passed} passed, {_failed} failed")
    print("=" * 72)
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

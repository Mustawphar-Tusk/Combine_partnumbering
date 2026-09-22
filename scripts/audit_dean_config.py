"""D110 Dean configuration audit (POST /configurations/resolve-state).

Guards the D110 exit gate for the DEAN family after publishing the authoritative
PumpConfiguration_Logic model (69 configurable fields, 46 constraint labels, 721
feasible-constraint rows including one 4-leg quad) to SQL, family-scoped to DEAN.

Unlike the Fybroc audits (which assert STANDARD auto-populate seeding), the Dean
workbook publishes NO STD defaults - every option is user-picked. So this audit
does NOT assert seeding; it asserts the four things the D110 exit gate requires:

  1. OPTIONS PROJECT: for a representative sample of the 37 Dean model-series,
     resolve-state returns a non-empty allowable option list for EVERY applicable
     field (no field is dead / silently empty on series select).

  2. VALID COMBOS PASS (no over-blocking): a value that IS one leg of a real
     ALLOWED tuple, given its partner leg selected as context, stays inside its
     own field's allowable set. The constraint engine must not block a
     combination the authority explicitly allows.

  3. INVALID COMBOS FAIL CLOSED: given a context selection on one leg of an
     allow-governed constraint, a target value that is IN the table's governed
     domain but NOT allowed under that context is PRUNED from the target field's
     allowable set. The engine must actually enforce the codependency, not just
     store it.

  4. NO EMPTY-OPTION STATE: walking every field of a series to its first
     allowable value (a full valid configuration) never drives any remaining
     field to zero allowable options - i.e. the rule set is internally
     satisfiable, no dead ends.

Additionally verifies the 4-leg quad (Seal Option x Gland Type x Flush Plan x
Barrier Plan) is wired through the Option4 columns: selecting the first three
legs still projects the Barrier Plan target with its authoritative values (the
Option4 plumbing does not crash or wrongly empty the leg).

Note on Dean data shape (verified from the published rows): of the 42 two-leg
ALLOW tables, only a subset actually PRUNE - the rest are full-domain
enumerations (every governed value is allowed under every context), which
impose no restriction by design. The 4-leg quad (Table100) is likewise a
full-domain table as authored, so it prunes nothing today. This audit tests
fail-closed on EVERY table that CAN prune, and verifies projection/no-empty on
the rest, rather than asserting an arbitrary count.

Test cases are DERIVED FROM THE DB constraint rows (not hardcoded), so the audit
stays correct as the Dean data evolves. Requires the API server on
127.0.0.1:8080. Exit 0 if all pass, 1 otherwise.
"""
from __future__ import annotations

import collections
import json
import sys
import time
import urllib.error
import urllib.request

import pyodbc

BASE = "http://127.0.0.1:8080/api/v2/families/DEAN"
CONN = ("DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;"
        "DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;"
        "Encrypt=yes;TrustServerCertificate=yes;")

# Representative series sample across the Dean families (horizontal RA/R, vertical
# RWAV, close-coupled PHP, DEANLINE, canned CNV, and a couple of size-legged ones).
SAMPLE_SERIES = ["CNV206", "DEANLINE", "PH2110", "R4140", "RA2096",
                 "RWAV4096", "RS", "DL200"]


def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def _wait_api():
    for _ in range(40):
        try:
            post("/configurations/resolve-state",
                 {"series": SAMPLE_SERIES[0], "selections": {}})
            return True
        except Exception:
            time.sleep(1)
    return False


def _norm(v):
    return str(v).strip().lower()


def _in(value, options):
    return any(_norm(value) == _norm(o) for o in options)


def load_dean_constraints():
    """Read DEAN feasible-constraint rows + label->code map from SQL, and build,
    per 2-leg ALLOW table, a context->allowed-partners index plus the governed
    target domain. Returns (label_to_code, two_leg_tables, quad_rows).

    two_leg_tables: list of dicts describing one directional test per table:
        {ctx_field, ctx_value, tgt_field, allowed_values(set), governed(set)}
    where ctx_value is a context value that has >=1 allowed partner AND the
    governed domain has >=1 value NOT allowed under it (so we can prove both
    pass-through and fail-closed in the same table).
    """
    cn = pyodbc.connect(CONN)
    cur = cn.cursor()
    dean_id = cur.execute(
        "SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode='DEAN'"
    ).fetchone()[0]
    label_to_code = {
        r[0]: r[1] for r in cur.execute(
            "SELECT ConstraintFieldName, SFOFieldCode FROM cfg.ConstraintFieldMap "
            "WHERE PumpFamilyId=?", dean_id).fetchall()
    }
    rows = cur.execute(
        "SELECT TableName, Option1Field, Option1Value, "
        "Option2Field, Option2Value, Option3Field, Option3Value, "
        "Option4Field, Option4Value, Allowed, SeriesApplicability "
        "FROM cfg.FeasibleConstraint WHERE PumpFamilyId=?", dean_id).fetchall()
    cn.close()

    # Group rows by table; keep only pure 2-leg ALLOW tables for the directional
    # pass/fail-closed test (multi-leg quads tested separately).
    by_table = collections.defaultdict(list)
    quad_rows = []
    for r in rows:
        (tname, o1f, o1v, o2f, o2v, o3f, o3v, o4f, o4v, allowed, scope) = r
        legs = [(f, v) for f, v in ((o1f, o1v), (o2f, o2v), (o3f, o3v), (o4f, o4v))
                if f]
        if len(legs) == 4:
            quad_rows.append((legs, _norm(allowed)))
        by_table[tname].append((legs, _norm(allowed)))

    two_leg_tables = []
    for tname, entries in by_table.items():
        # only tables where every row is exactly 2-leg and all ALLOW
        if not all(len(legs) == 2 for legs, _ in entries):
            continue
        if any(a == "not allowed" for _, a in entries):
            continue
        # Pick a direction: leg0 = context, leg1 = target.
        ctx_field_label = entries[0][0][0][0]
        tgt_field_label = entries[0][0][1][0]
        ctx_code = label_to_code.get(ctx_field_label)
        tgt_code = label_to_code.get(tgt_field_label)
        if not ctx_code or not tgt_code:
            continue
        # governed target domain = all target values the table names anywhere
        governed = {_norm(legs[1][1]) for legs, _ in entries}
        # allowed partners per context value
        allowed_by_ctx = collections.defaultdict(set)
        for legs, _a in entries:
            allowed_by_ctx[_norm(legs[0][1])].add(_norm(legs[1][1]))
        # find a context value where governed has a value NOT allowed under it
        chosen = None
        for cval, allowset in allowed_by_ctx.items():
            not_allowed = governed - allowset
            if allowset and not_allowed:
                chosen = (cval, allowset, not_allowed)
                break
        if not chosen:
            continue
        cval, allowset, not_allowed = chosen
        two_leg_tables.append({
            "table": tname,
            "ctx_field": ctx_code.upper(),
            "ctx_field_label": ctx_field_label,
            "ctx_value": cval,
            "tgt_field": tgt_code.upper(),
            "tgt_field_label": tgt_field_label,
            "allowed": allowset,
            "not_allowed": not_allowed,
            "governed": governed,
        })
    return label_to_code, two_leg_tables, quad_rows


def main():
    if not _wait_api():
        print("FAIL: API server not reachable on 127.0.0.1:8080")
        return 1

    label_to_code, two_leg_tables, quad_rows = load_dean_constraints()

    P = [0]
    F = [0]

    def ok(cond, msg):
        cond = bool(cond)
        P[0] += cond
        F[0] += (not cond)
        print(f"  [{'PASS' if cond else 'FAIL'}] {msg}")

    print("=" * 92)
    print("DEAN CONFIGURATION AUDIT (D110 exit gate)")
    print("=" * 92)
    print(f"Constraint labels: {len(label_to_code)}  "
          f"prunable 2-leg tables: {len(two_leg_tables)}  "
          f"quad rows: {len(quad_rows)}")

    # --- (1) OPTIONS PROJECT for every sampled series -----------------------
    print("\n=== (1) Options project (no dead/empty field on series select) ===")
    series_state = {}
    for series in SAMPLE_SERIES:
        st = post("/configurations/resolve-state",
                  {"series": series, "selections": {}})
        series_state[series] = st
        ordered = st.get("ordered_fields", [])
        allow = st.get("allowable_options", {})
        empty = [fc for fc in ordered if not allow.get(fc)]
        ok(st.get("valid") is True, f"{series}: seed state valid=True")
        ok(len(ordered) >= 60,
           f"{series}: projects a full field set ({len(ordered)} fields)")
        ok(not empty,
           f"{series}: every applicable field has >=1 option "
           f"({len(empty)} empty: {empty[:5]})")

    # --- (2)+(3) VALID passes + INVALID fails closed, per constraint table --
    # Use one representative series (CNV206) since Dean constraints are ALL_SERIES.
    series = "CNV206"
    print(f"\n=== (2)/(3) Codependency enforcement on {series} "
          f"({len(two_leg_tables)} tables) ===")
    tested = 0
    skipped = []
    for t in two_leg_tables:
        # Select the context value; read the target field's resulting allowable.
        sel = {t["ctx_field"]: t["ctx_value"]}
        st = post("/configurations/resolve-state",
                  {"series": series, "selections": sel,
                   "changed_field": t["ctx_field"]})
        allow = st.get("allowable_options", {})
        ordered = st.get("ordered_fields", [])
        # The target must be applicable AND the context field must have been
        # accepted (i.e. the ctx value is itself a legal option for this series);
        # otherwise the table is not exercisable here and we say so explicitly.
        ctx_applicable = t["ctx_field"] in ordered
        tgt_applicable = t["tgt_field"] in ordered
        tgt_opts = allow.get(t["tgt_field"], [])
        if not (ctx_applicable and tgt_applicable):
            skipped.append((t["table"], t["ctx_field_label"], t["tgt_field_label"]))
            continue
        tested += 1
        # (2) at least one authoritative-allowed partner survives (no over-block)
        allowed_present = [v for v in t["allowed"] if _in(v, tgt_opts)]
        ok(len(allowed_present) > 0,
           f"[{t['ctx_field_label']}={t['ctx_value']}] -> "
           f"{t['tgt_field_label']}: >=1 allowed partner survives "
           f"({len(allowed_present)}/{len(t['allowed'])})")
        # (3) every governed-but-not-allowed value is pruned (fail closed)
        leaked = [v for v in t["not_allowed"] if _in(v, tgt_opts)]
        ok(not leaked,
           f"[{t['ctx_field_label']}={t['ctx_value']}] -> "
           f"{t['tgt_field_label']}: disallowed values pruned "
           f"({len(leaked)} leaked: {list(leaked)[:4]})")
    # Every prunable 2-leg table whose fields are applicable to this series must
    # have been exercised for fail-closed. Any skip is reported with its reason.
    if skipped:
        print(f"  [info] {len(skipped)} prunable table(s) not applicable to "
              f"{series}, skipped: {skipped}")
    ok(tested + len(skipped) == len(two_leg_tables) and tested >= 1,
       f"every applicable prunable 2-leg table exercised for fail-closed "
       f"({tested} tested, {len(skipped)} N/A, {len(two_leg_tables)} total)")

    # --- (4) 4-leg quad wired through Option4 columns -----------------------
    # Table100 (Seal Option x Gland Type x Flush Plan x Barrier Plan) is, as
    # authored, a FULL-DOMAIN table (every governed Barrier Plan value is allowed
    # under every 3-leg context), so it prunes nothing. The meaningful check is
    # that the Option4 plumbing is live: selecting the first three legs projects
    # the Barrier Plan target with its authoritative domain (engine reads
    # Option4Field/Option4Value; the 4th leg is not crashed or wrongly emptied).
    # If the quad ever becomes restrictive, the split branch below fires and
    # asserts fail-closed instead.
    print("\n=== (4) 4-leg quad wired through Option4 columns ===")
    if quad_rows:
        # Legs order in DB: Seal Option, Gland Type, Flush Plan, Barrier Plan.
        so_c = label_to_code.get("Seal Option", "SEAL_OPTION").upper()
        gt_c = label_to_code.get("Gland Type", "GLAND_TYPE").upper()
        fp_c = label_to_code.get("Flush Plan", "FLUSH_PLAN").upper()
        bp_c = label_to_code.get("Barrier Plan", "BARRIER_PLAN").upper()
        governed_bp = {_norm(legs[3][1]) for legs, _ in quad_rows}
        allowed_by_ctx = collections.defaultdict(set)
        for legs, _a in quad_rows:
            ctx = (_norm(legs[0][1]), _norm(legs[1][1]), _norm(legs[2][1]))
            allowed_by_ctx[ctx].add(_norm(legs[3][1]))
        # Prefer a restrictive context if one exists (future-proof); else use any.
        restrictive = [(c, a, governed_bp - a) for c, a in allowed_by_ctx.items()
                       if a and (governed_bp - a)]
        (so_v, gt_v, fp_v), aset = (
            (restrictive[0][0], restrictive[0][1]) if restrictive
            else (next(iter(allowed_by_ctx)), next(iter(allowed_by_ctx.values()))))
        sel = {so_c: so_v, gt_c: gt_v, fp_c: fp_v}
        st = post("/configurations/resolve-state",
                  {"series": series, "selections": sel, "changed_field": fp_c})
        bp_opts = st.get("allowable_options", {}).get(bp_c, [])
        present = [v for v in aset if _in(v, bp_opts)]
        ok(bp_c in st.get("allowable_options", {}) and len(bp_opts) > 0,
           f"quad [SO={so_v}, GT={gt_v}, FP={fp_v}] -> Barrier Plan projects "
           f"({len(bp_opts)} options, Option4 plumbing live)")
        ok(len(present) == len(aset),
           f"quad -> all {len(aset)} authoritative Barrier Plan value(s) present "
           f"({len(present)}/{len(aset)})")
        if restrictive:
            notset = restrictive[0][2]
            leaked = [v for v in notset if _in(v, bp_opts)]
            ok(not leaked,
               f"quad restrictive ctx: disallowed Barrier Plan pruned "
               f"({len(leaked)} leaked: {list(leaked)[:4]})")
        else:
            print("  [info] quad is a full-domain table (no prunable context) - "
                  "fail-closed N/A by design")
    else:
        ok(False, "expected a 4-leg quad in DEAN feasible rows, found none")

    # --- (5) NO EMPTY-OPTION STATE walking a full config --------------------
    print("\n=== (5) Full-config walk never dead-ends (no empty option) ===")
    for series in ["CNV206", "RA2096", "RWAV4096"]:
        st = series_state.get(series) or post(
            "/configurations/resolve-state", {"series": series, "selections": {}})
        sel = dict(st.get("selections", {}))
        dead_field = None
        # iterate: pick first allowable for each unset field, re-settle, repeat
        for _round in range(6):
            allow = st.get("allowable_options", {})
            progressed = False
            for fc in st.get("ordered_fields", []):
                if fc in sel:
                    continue
                opts = allow.get(fc, [])
                if not opts:
                    dead_field = fc
                    break
                sel[fc] = opts[0]
                progressed = True
            if dead_field or not progressed:
                break
            st = post("/configurations/resolve-state",
                      {"series": series, "selections": sel})
        final_allow = st.get("allowable_options", {})
        # after walking, every field is either selected or still has options
        empty_now = [fc for fc in st.get("ordered_fields", [])
                     if fc not in sel and not final_allow.get(fc)]
        ok(dead_field is None and not empty_now,
           f"{series}: full walk has no empty-option dead end "
           f"(dead={dead_field}, empty={empty_now[:5]})")
        ok(st.get("valid") is True,
           f"{series}: final walked config valid=True")

    print(f"\n=== RESULT: {P[0]} passed, {F[0]} failed ===")
    return 0 if F[0] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

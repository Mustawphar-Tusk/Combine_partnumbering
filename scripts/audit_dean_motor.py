"""Dean MOTOR numbering audit (re-runnable; exit non-zero on any failure).

Expectations come from Motor Numbering.xlsm 'Pricing' (options block A1:AC72 and
the motor combinations) and Pump Constraints (per-series frame sizes):
  A. Options: every Dean series offers exactly the Pricing-block values for the 9
     motor fields; Motor STD = 'Included', no other motor STD; FRAME_SIZE per
     (series, size) == the Pump Constraints frame set (canonical form).
  B. Block <-> combinations: every block value occurs in the motor combinations
     and every combination value is in the block.
  C. Price: one price.DeanMotorPrice row per combination code; numeric vs C.F.
     split equals the workbook.
  D. API: Motor auto-selected 'Included' for every bundle that includes a motor
     (fresh seed and on change); bundles without a motor drop the motor fields; a
     full motor spec gives the combination's code in the PN and its price / C.F.;
     frame options shown == Pump Constraints frames that have a motor combination.
  E. Isolation: non-DEAN rows unchanged.

Run (API on 127.0.0.1:8080):
  $env:PYTHONPATH="."; uv run python scripts/audit_dean_motor.py
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import pyodbc

sys.path.insert(0, "scripts")
import load_dean_motor_options as MO  # noqa: E402
import load_dean_motor_numbering as MN  # noqa: E402

CS = MO.CS
BASE = "http://127.0.0.1:8080/api/v2/families/DEAN"
passed = failed = 0


def ok(cond, msg, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  [PASS] {msg}")
    else:
        failed += 1
        print(f"  [FAIL] {msg} {detail}")


def post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode())


def main():
    c = pyodbc.connect(CS).cursor()
    dean = c.execute("SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode='DEAN'").fetchone()[0]
    block = MO.read_block()

    print("A. Motor options and frame sizes")
    series = sorted({r[0] for r in c.execute(
        "SELECT DISTINCT SeriesCode FROM cfg.SeriesFieldOption WHERE PumpFamilyId=? AND FieldCode='PUMP_CONFIGURATION'", dean)})
    got = defaultdict(list)
    std = {}
    for ser, f, v, s in c.execute(
            "SELECT SeriesCode, FieldCode, OptionValue, IsStandard FROM cfg.SeriesFieldOption WHERE PumpFamilyId=? "
            "AND FieldCode IN (%s) AND SizeCode IS NULL" % ",".join("?" * len(MO.OPTION_FIELDS)), dean, *MO.OPTION_FIELDS):
        got[(ser, f)].append(v)
        if s:
            std[(ser, f)] = v
    bad = [(s, f) for s in series for f in MO.OPTION_FIELDS if sorted(got.get((s, f), [])) != sorted(block[f])]
    ok(not bad, f"{len(series)} series x {len(MO.OPTION_FIELDS)} motor fields == Pricing A1:AC72 values", str(bad[:4]))
    ok(all(std.get((s, "MOTOR")) == "Included" for s in series) and
       all(f == "MOTOR" for (_s, f) in std), "Motor STD = 'Included' on every series; no other motor field has a STD")
    # FRAME_SIZE vs Pump Constraints
    import d110_load_dean_config_v01 as D
    tmp = Path(tempfile.mkdtemp()) / D.WB_PATH.name
    shutil.copy(D.WB_PATH, tmp)
    from openpyxl import load_workbook
    wb = load_workbook(tmp, data_only=True, read_only=True)
    models, _fd, _un = D.read_pump_constraints(wb)
    wb.close()
    pc_frames = {(m["series"], m["size"]): {MO.canon_frame(D._norm_value("FRAME_SIZE", v))
                                            for v in (m["cells"].get("FRAME_SIZE") or {})} for m in models}
    db_frames = defaultdict(set)
    for ser, size, v in c.execute("SELECT SeriesCode, SizeCode, OptionValue FROM cfg.SeriesFieldOption "
                                  "WHERE PumpFamilyId=? AND FieldCode='FRAME_SIZE'", dean):
        db_frames[(ser, size)].add(v)
    badf = [k for k in pc_frames if pc_frames[k] != db_frames.get(k, set())]
    ok(not badf, f"FRAME_SIZE per (series,size) == Pump Constraints ({len(pc_frames)} models)", str(badf[:3]))
    no_frames = sorted({k[0] for k, v in pc_frames.items() if not v})
    print(f"    series with no Pump Constraints frame size: {no_frames}")

    print("B. Pricing block <-> motor combinations")
    cv = MO.combo_values(c)
    diff = {f: (sorted(set(block[f]) - cv[f]), sorted(cv[f] - set(block[f]))) for f in block
            if set(block[f]) != cv[f]}
    ok(not diff, "every block value has combinations and every combination value is in the block", str(diff)[:200])
    ncombo = c.execute("SELECT COUNT(*), COUNT(DISTINCT SegmentValue) FROM stg.SegmentCombinationImport "
                       "WHERE FamilyCode='DEAN' AND SegmentCode='MOTOR_SPEC'").fetchone()

    print("C. Motor price")
    tmpm = Path(tempfile.mkdtemp()) / MN.WB_PATH.name
    shutil.copy(MN.WB_PATH, tmpm)
    wbm = load_workbook(tmpm, data_only=True, read_only=True)
    combos = list(MN.read_combos(wbm))
    wbm.close()
    wb_num = sum(1 for *_x, pr in combos if MN._price_num(pr)[1] is False)
    pr = c.execute("SELECT COUNT(*), SUM(CASE WHEN IsContactFactory=0 THEN 1 ELSE 0 END) FROM price.DeanMotorPrice").fetchone()
    ok(ncombo[0] == len(combos) == ncombo[1], f"MOTOR_SPEC combinations == workbook ({len(combos):,}, codes unique)", str(tuple(ncombo)))
    ok(tuple(pr) == (len(combos), wb_num), f"price.DeanMotorPrice rows/numeric == workbook ({len(combos):,} / {wb_num}; rest C.F.)", str(tuple(pr)))
    wb96 = load_workbook(tmpm, data_only=True, read_only=True)
    pre = [r[MN.COL_COMBINED - 1] for r in wb96["Pricing"].iter_rows(min_row=96, max_row=MN.COMBO_FIRST_DATA_ROW - 1,
                                                                       max_col=MN.COL_PRICE, values_only=True)]
    wb96.close()
    leaked = c.execute("SELECT COUNT(*) FROM stg.SegmentCombinationImport WHERE FamilyCode='DEAN' AND SegmentCode='MOTOR_SPEC' "
                       "AND SegmentValue IN (%s)" % ",".join("?" * len(pre)), *pre).fetchone()[0] if pre else 0
    ok(MN.COMBO_FIRST_DATA_ROW == 98 and min(r[1] for r in combos) == 98 and max(r[1] for r in combos) == 34179 and leaked == 0,
       f"combinations come from rows 98..34179 only (rows 96-97 codes {pre} not loaded)")
    perm = [r[0] for r in c.execute("SELECT SourceId FROM stg.SegmentCombinationImport WHERE FamilyCode='DEAN' "
                                    "AND SegmentCode='MOTOR_SPEC' ORDER BY SourceRow")]
    ok(perm == list(range(1, len(perm) + 1)),
       f"regenerated permutation numbers are 1..{len(perm)}, increasing in sheet order, unique")
    nk = c.execute("SELECT COUNT(DISTINCT CombinationKey) FROM stg.SegmentCombinationImport WHERE FamilyCode='DEAN' "
                   "AND SegmentCode='MOTOR_SPEC'").fetchone()[0]
    ok(nk == len(perm), "no permutation collision: every motor combination (10 spec values) is unique", f"{nk} vs {len(perm)}")
    pm = c.execute("SELECT COUNT(*) FROM price.DeanMotorPrice p JOIN stg.SegmentCombinationImport s ON s.SegmentValue=p.MotorCode "
                   "AND s.FamilyCode='DEAN' AND s.SegmentCode='MOTOR_SPEC' WHERE s.SourceId<>p.PermutationNo").fetchone()[0]
    ok(pm == 0, "price.DeanMotorPrice.PermutationNo matches the spec permutation for every code")
    miss = c.execute("SELECT COUNT(*) FROM stg.SegmentCombinationImport s LEFT JOIN price.DeanMotorPrice p "
                     "ON p.MotorCode=s.SegmentValue WHERE s.FamilyCode='DEAN' AND s.SegmentCode='MOTOR_SPEC' "
                     "AND p.MotorCode IS NULL").fetchone()[0]
    ok(miss == 0, "every motor code has a price row (numeric or C.F.)", str(miss))

    print("D. API behaviour")
    combo_frames = cv["FRAME_SIZE"]
    # fresh seeds
    bad_seed, bad_drop, bad_auto, bad_frames = [], [], [], []
    for ser in series:
        st = post("/configurations/resolve-state", {"series": ser, "selections": {}})
        sel = st.get("selections") or {}
        pc = str(sel.get("PUMP_CONFIGURATION") or "")
        has_motor = "motor" in pc.lower()
        if has_motor and sel.get("MOTOR") != "Included":
            bad_seed.append((ser, pc, sel.get("MOTOR")))
        if not has_motor and any(f in sel for f in MO.OPTION_FIELDS + ["FRAME_SIZE"]):
            bad_drop.append((ser, pc))
        opts = st.get("allowable_options") or {}
        pcs = opts.get("PUMP_CONFIGURATION") or []
        mb = next((b for b in pcs if "motor" in b.lower()), None)
        if mb:
            sel2 = {k: v for k, v in sel.items() if k not in MO.OPTION_FIELDS}
            sel2["PUMP_CONFIGURATION"] = mb
            st2 = post("/configurations/resolve-state", {"series": ser, "selections": sel2,
                                                         "changed_field": "PUMP_CONFIGURATION"})
            s2 = st2.get("selections") or {}
            if s2.get("MOTOR") != "Included" or (st2.get("reset_fields") or {}).get("MOTOR") != "Included":
                bad_auto.append((ser, mb, s2.get("MOTOR")))
            sz = str(s2.get("ALT_SIZE") or s2.get("SIZE") or "").lower()
            key = next((k for k in pc_frames if k[0] == ser and str(k[1]).lower() == sz), None)
            exp = {f for f in pc_frames.get(key, set()) if f in combo_frames}
            gotf = set((st2.get("allowable_options") or {}).get("FRAME_SIZE") or [])
            if gotf != exp:
                bad_frames.append((ser, len(gotf), len(exp), sorted(gotf ^ exp)[:3]))
    ok(not bad_seed, "fresh configuration with a motor bundle seeds Motor = 'Included'", str(bad_seed[:4]))
    ok(not bad_drop, "bundles without a motor carry no motor fields", str(bad_drop[:4]))
    ok(not bad_auto, "switching to a motor bundle auto-selects Motor = 'Included' (reported in reset_fields)", str(bad_auto[:4]))
    ok(not bad_frames, "frame options shown == Pump Constraints frames that have a motor combination (all series)", str(bad_frames[:4]))

    # full motor spec -> PN code + price
    fields = MN.MOTOR_FIELD_ORDER
    by_frame = defaultdict(list)
    for _sid, _sr, _ck, code, sel, prc in combos:
        by_frame[sel["FRAME_SIZE"]].append((code, sel, prc))
    checked = 0
    for want_cf in (False, True):
        for ser in ("R4140", "RA3146", "DL200"):
            st = post("/configurations/resolve-state", {"series": ser, "selections": {}})
            sel = dict(st.get("selections") or {})
            sz = str(sel.get("ALT_SIZE") or sel.get("SIZE") or "").lower()
            key = next((k for k in pc_frames if k[0] == ser and str(k[1]).lower() == sz), None)
            cand = [x for f in sorted(pc_frames.get(key, set())) for x in by_frame.get(f, [])
                    if MN._price_num(x[2])[1] is want_cf]
            if not cand:
                continue
            code, msel, prc = cand[0]
            sel.update({"PUMP_CONFIGURATION": "Pump and Motor", **msel, "SERIES": ser})
            res = post("/configured-products/resolve", {"series": ser, "selections": sel, "requested_by": "motor-audit"})
            pn = res.get("part_number") or ""
            comp = [x for x in res.get("component_pricing") or [] if x.get("component") == "Motor"]
            amt = MN._price_num(prc)[0]
            good = pn.endswith("-" + code) and res.get("parity_ok") is True and comp and (
                (comp[0].get("amount") is None) if want_cf else abs((comp[0].get("amount") or 0) - amt) < 0.01)
            ok(good, f"{ser}: motor {'C.F.' if want_cf else 'priced'} spec -> PN ...-{code}, Motor line "
               f"{'C/F' if want_cf else amt}", f"pn={pn} comp={comp}")
            checked += 1
            break

    print("E. Isolation")
    for t, exp in (("SeriesFieldOption", 3638), ("FeasibleConstraint", 4487), ("ConstraintFieldMap", 28)):
        v = c.execute(f"SELECT COUNT(*) FROM cfg.{t} WHERE PumpFamilyId<>?", dean).fetchone()[0]
        ok(v == exp, f"non-DEAN cfg.{t} == {exp}", str(v))
    print(f"\nRESULT: {passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

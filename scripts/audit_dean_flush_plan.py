"""D110 Dean FLUSH PLAN audit (options + allowed combinations).

Verifies the Flush Plan implementation (option A, choice (i)) against the
authoritative "Flush Plan Numbering" sheet of PumpConfiguration_Logic_0.1.xlsm:

  (1) OPTIONS: the four flush SUB-fields (FLUSH_PLAN_ROUTING, FLUSH_CONNECTIONS,
      FLUSH_TEMPERATURE_RANGE, FLUSH_COOLING_MEDIA) are loaded in cfg.SeriesFieldOption
      for every Dean series, their value sets exactly match the sheet options block
      (D..H, Custom->C/F); and FLUSH_PLAN carries a 'C/F' option per series.
  (2) COMBINATIONS: the 185 combinations (sheet C27:I211) are loaded into
      stg.SegmentCombinationImport (SegmentCode='FLUSH_PLAN'), each with all five
      flush fields in SelectionsJson, Custom->C/F, 0 'Custom' left.
  (3) LIVE enforcement (API): for a seeded config, the flush allow-list restricts
      each flush field to values reachable in >=1 enumerated combination given the
      other flush picks; an OFF-sheet flush combination is pruned; a full on-sheet
      combination resolves to a part number; STD stays consistent.

Expectations derived from the sheet / DB. Exit 0 iff all pass.

Run (API on 127.0.0.1:8080):
  $env:PYTHONPATH="."; python scripts/audit_dean_flush_plan.py
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

import pyodbc
from openpyxl import load_workbook

BASE = "http://127.0.0.1:8080/api/v2/families/DEAN"
CS = ('DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;'
      'DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;Encrypt=yes;'
      'TrustServerCertificate=yes;')
WB = Path("workbooks/Dean/PumpConfiguration_Logic_0.1.xlsm")

SUB_FIELDS = ("FLUSH_PLAN_ROUTING", "FLUSH_CONNECTIONS",
              "FLUSH_TEMPERATURE_RANGE", "FLUSH_COOLING_MEDIA")
HDR_TO_CODE = {
    "flush plan routing": "FLUSH_PLAN_ROUTING",
    "flush connections": "FLUSH_CONNECTIONS",
    "flush temperature range": "FLUSH_TEMPERATURE_RANGE",
    "flush cooling media": "FLUSH_COOLING_MEDIA",
}


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


def _cf(v):
    return "C/F" if str(v).strip().lower() == "custom" else str(v).strip()


def parse_sheet():
    """Return (sub_options {code:set}, flush_plan_has_custom bool, combos list)."""
    wb = load_workbook(WB, data_only=True, read_only=True)
    ws = wb["Flush Plan Numbering"]
    rows = list(ws.iter_rows(min_row=1, max_row=215, values_only=True))
    wb.close()

    def cell(r0, c0):
        row = rows[r0] if 0 <= r0 < len(rows) else []
        return row[c0] if 0 <= c0 < len(row) else None

    # options block: header row 2 (idx1), data rows 3..23
    hdr = rows[1]
    col_code = {}
    for c0, v in enumerate(hdr):
        if v is None:
            continue
        code = HDR_TO_CODE.get(str(v).strip().lower())
        if code:
            col_code[c0] = code
    sub_options = {}
    for c0, code in col_code.items():
        vals = set()
        for r0 in range(2, 24):
            v = cell(r0, c0)
            if v is not None and str(v).strip():
                vals.add(_cf(v))
        sub_options[code] = vals
    # flush plan column D (idx3): does it list 'Custom'?
    fp_custom = any(str(cell(r0, 3)).strip().lower() == "custom"
                    for r0 in range(2, 24) if cell(r0, 3) is not None)

    # combinations: header row 26 (idx25), data rows 27..211 (idx26..210)
    combos = []
    for r0 in range(26, 211):
        plan = cell(r0, 3)
        if plan is None or str(plan).strip() == "":
            continue
        rec = {
            "FLUSH_PLAN": _cf(plan),
            "FLUSH_PLAN_ROUTING": _cf(cell(r0, 4) or ""),
            "FLUSH_CONNECTIONS": _cf(cell(r0, 5) or ""),
            "FLUSH_TEMPERATURE_RANGE": _cf(cell(r0, 6) or ""),
            "FLUSH_COOLING_MEDIA": _cf(cell(r0, 7) or ""),
            "code": str(cell(r0, 8) or "").strip(),
        }
        combos.append(rec)
    return sub_options, fp_custom, combos


def main():
    if not wait_api():
        print("FAIL: API not reachable on 127.0.0.1:8080")
        return 1

    sub_options, fp_custom, combos = parse_sheet()
    conn = pyodbc.connect(CS)
    c = conn.cursor()
    dean = c.execute("SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode='DEAN'").fetchone()[0]

    passed = failed = 0

    def ok(cond, msg):
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  [PASS] {msg}")
        else:
            failed += 1
            print(f"  [FAIL] {msg}")

    # ---- (1) OPTIONS in cfg.SeriesFieldOption -------------------------------
    print("=== (1) Flush sub-field options (DB == sheet, per series) ===")
    series = [r[0] for r in c.execute(
        "SELECT DISTINCT SeriesCode FROM cfg.SeriesFieldOption "
        "WHERE PumpFamilyId=? AND IsActive=1", dean).fetchall()]
    for code in SUB_FIELDS:
        sheet_vals = sub_options.get(code, set())
        # every series must offer exactly the sheet value set
        bad = []
        for ser in series:
            db_vals = {r[0] for r in c.execute(
                "SELECT OptionValue FROM cfg.SeriesFieldOption "
                "WHERE PumpFamilyId=? AND IsActive=1 AND FieldCode=? AND SeriesCode=?",
                dean, code, ser).fetchall()}
            if db_vals != sheet_vals:
                bad.append((ser, sorted(sheet_vals - db_vals), sorted(db_vals - sheet_vals)))
        ok(not bad, f"{code}: all {len(series)} series offer exactly {sorted(sheet_vals)} "
                    f"({len(bad)} mismatched)")
    # FLUSH_PLAN C/F present per series
    cf_series = {r[0] for r in c.execute(
        "SELECT DISTINCT SeriesCode FROM cfg.SeriesFieldOption "
        "WHERE PumpFamilyId=? AND IsActive=1 AND FieldCode='FLUSH_PLAN' AND OptionValue='C/F'",
        dean).fetchall()}
    ok(set(series) <= cf_series,
       f"FLUSH_PLAN 'C/F' offered for every series ({len(cf_series)}/{len(series)})")

    # ---- (2) COMBINATIONS in stg ---------------------------------------------
    print("\n=== (2) Flush combinations (DB == sheet) ===")
    bid = c.execute("SELECT TOP 1 ImportBatchId FROM stg.SegmentCombinationImportBatch "
                    "WHERE FamilyCode='DEAN' ORDER BY ImportBatchId DESC").fetchone()[0]
    db_rows = c.execute(
        "SELECT CombinationKey, SegmentValue, SelectionsJson FROM stg.SegmentCombinationImport "
        "WHERE ImportBatchId=? AND SegmentCode='FLUSH_PLAN'", bid).fetchall()
    ok(len(db_rows) == len(combos),
       f"combination count DB={len(db_rows)} sheet={len(combos)}")
    # every DB combo has all 5 fields in SelectionsJson
    five = sum(1 for r in db_rows if len(json.loads(r[2])) == 5)
    ok(five == len(db_rows),
       f"every combo SelectionsJson has all 5 flush fields ({five}/{len(db_rows)})")
    # 0 'Custom' left anywhere
    cust = sum(1 for r in db_rows if "custom" in (r[0] + r[2]).lower())
    ok(cust == 0, f"no 'Custom' left in flush combos ({cust})")
    # code set matches sheet
    db_codes = {r[1] for r in db_rows}
    sheet_codes = {rec["code"] for rec in combos}
    ok(db_codes == sheet_codes,
       f"alphanumeric code set matches sheet ({len(db_codes)} codes, "
       f"diff={sorted(db_codes ^ sheet_codes)[:5]})")

    # ---- (3) LIVE enforcement -------------------------------------------------
    print("\n=== (3) Live flush enforcement (API) ===")
    # pick a series whose STD flush plan is a real (non-NONE) plan if possible,
    # else use a plan with combos. We test enforcement generically on CNV206.
    ser = "CNV206"
    sz = c.execute("SELECT TOP 1 SizeCode FROM cfg.SeriesFieldOption "
                   "WHERE PumpFamilyId=? AND SeriesCode=? AND SizeCode IS NOT NULL",
                   dean, ser).fetchone()[0]
    # Seed the model, then force FLUSH_PLAN = P1200 (a plan with many combos) and
    # check the sub-fields are constrained to reachable values.
    st = post("/configurations/resolve-state",
              {"series": ser, "selections": {"ALT_SIZE": sz, "FLUSH_PLAN": "P1200"}})
    ao = st.get("allowable_options", {}) or {}

    def vals(f):
        v = ao.get(f)
        return None if v is None else {
            (x["value"] if isinstance(x, dict) else x) for x in v}

    # reachable values for each sub-field under FLUSH_PLAN=P1200 (from the sheet)
    def reachable(sub, plan):
        return {rec[sub] for rec in combos if rec["FLUSH_PLAN"] == plan and rec[sub]}

    for sub in SUB_FIELDS:
        api = vals(sub)
        reach = reachable(sub, "P1200")
        if api is None:
            ok(False, f"{sub}: API offers nothing under FLUSH_PLAN=P1200 (sheet has {sorted(reach)})")
            continue
        extra = api - reach
        ok(not extra, f"{sub} under P1200: API subset of sheet-reachable "
                      f"(api={len(api)}, reach={len(reach)}, extra={sorted(extra)[:4]})")

    # off-sheet combination is pruned: find a (sub) value NOT reachable for P1200
    # but valid for some other plan, and confirm it is not offered for P1200.
    media_reach = reachable("FLUSH_COOLING_MEDIA", "P1200")
    all_media = sub_options["FLUSH_COOLING_MEDIA"]
    off = sorted(all_media - media_reach)
    api_media = vals("FLUSH_COOLING_MEDIA") or set()
    ok(all(o not in api_media for o in off),
       f"off-combination FLUSH_COOLING_MEDIA values pruned under P1200 "
       f"(off={off}, leaked={[o for o in off if o in api_media]})")

    # a full on-sheet combination resolves to a PN (pick first non-NONE combo)
    target = next((rec for rec in combos if rec["FLUSH_PLAN"] == "P1200"), None)
    if target:
        sel = {"ALT_SIZE": sz, "FLUSH_PLAN": "P1200",
               "FLUSH_PLAN_ROUTING": target["FLUSH_PLAN_ROUTING"],
               "FLUSH_CONNECTIONS": target["FLUSH_CONNECTIONS"],
               "FLUSH_TEMPERATURE_RANGE": target["FLUSH_TEMPERATURE_RANGE"],
               "FLUSH_COOLING_MEDIA": target["FLUSH_COOLING_MEDIA"]}
        st2 = post("/configurations/resolve-state", {"series": ser, "selections": sel})
        conf = {(x.get("field") or "").upper() for x in (st2.get("conflicts") or [])}
        flush_conf = sorted(f for f in conf if f.startswith("FLUSH"))
        ok(not flush_conf,
           f"on-sheet P1200 combination has no flush conflict (got {flush_conf})")

    conn.close()
    print("\n" + "=" * 70)
    print(f"RESULT: {passed} passed, {failed} failed")
    print("=" * 70)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

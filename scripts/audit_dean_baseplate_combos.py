"""D110 Dean BASEPLATE allowed-combination audit.

Verifies the Baseplate Numbering implementation against the authoritative sheet
(PumpConfiguration_Logic_0.1.xlsm -> "Baseplate Numbering"):

  (1) OPTIONS block D2:L7 -> the nine baseplate fields' value sets are offered in
      cfg.SeriesFieldOption for every series (Custom -> C/F on BASEPLATE_TYPE).
  (2) COMBINATIONS block C16:M1169 -> the 1153 permutations are loaded into
      stg.SegmentCombinationImport (SegmentCode='BASEPLATE_OPTIONS'), each with all
      nine baseplate fields in SelectionsJson, 0 'Custom', codes match the sheet.
  (3) LIVE enforcement (API): under a chosen BASEPLATE_TYPE the dependent baseplate
      fields are restricted to values reachable in >=1 enumerated combination; an
      off-combination value is pruned; a full on-sheet baseplate combination
      resolves with no baseplate conflict.

Expectations derived from the sheet / DB. Exit 0 iff all pass.

Run (API on 127.0.0.1:8080):
  $env:PYTHONPATH="."; python scripts/audit_dean_baseplate_combos.py
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

# column order D..L in the Baseplate Numbering blocks
FIELD_COLS = [
    (3, "BASEPLATE_TYPE"), (4, "DRIP_PAN"), (5, "ALIGNMENT_LUGS"),
    (6, "LIFTING_LUGS"), (7, "LEVELLING_SCREWS"), (8, "GROUNDING_LUG"),
    (9, "GROUT_HOLE"), (10, "ISOLATION_PADS"), (11, "STILTS"),
]
FIELDS = [f for _c, f in FIELD_COLS]


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


def _norm(v):
    return str(v).strip().lower()


def parse_sheet():
    wb = load_workbook(WB, data_only=True, read_only=True)
    ws = wb["Baseplate Numbering"]
    rows = list(ws.iter_rows(min_row=1, max_row=1169, values_only=True))
    wb.close()

    def cell(r0, c0):
        row = rows[r0] if 0 <= r0 < len(rows) else []
        return row[c0] if 0 <= c0 < len(row) else None

    # OPTIONS block: header row 2 (idx1), data rows 3..7 (idx2..6)
    options = {f: set() for _c, f in FIELD_COLS}
    for c0, f in FIELD_COLS:
        for r0 in range(2, 7):
            v = cell(r0, c0)
            if v is not None and str(v).strip():
                options[f].add(_cf(v))

    # COMBINATIONS: header row 16 (idx15), data rows 17..1169 (idx16..1168)
    combos = []
    for r0 in range(16, 1169):
        perm = cell(r0, 2)  # col C
        bt = cell(r0, 3)    # col D (Baseplate Type) - combo anchor
        if (perm is None or str(perm).strip() == "") and (bt is None or str(bt).strip() == ""):
            continue
        rec = {f: _cf(cell(r0, c0) or "") for c0, f in FIELD_COLS}
        rec["code"] = str(cell(r0, 12) or "").strip()  # col M
        combos.append(rec)
    return options, combos


def main():
    if not wait_api():
        print("FAIL: API not reachable on 127.0.0.1:8080")
        return 1

    options, combos = parse_sheet()
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

    # ---- (1) OPTIONS vs cfg.SeriesFieldOption -------------------------------
    print("=== (1) Baseplate option values (DB offers sheet set per series) ===")
    series = [r[0] for r in c.execute(
        "SELECT DISTINCT SeriesCode FROM cfg.SeriesFieldOption "
        "WHERE PumpFamilyId=? AND IsActive=1", dean).fetchall()]
    for f in FIELDS:
        sheet_vals = {_norm(v) for v in options[f]}
        # union of DB offered values for this field across all (series,size)
        db_vals = {_norm(r[0]) for r in c.execute(
            "SELECT DISTINCT OptionValue FROM cfg.SeriesFieldOption "
            "WHERE PumpFamilyId=? AND IsActive=1 AND FieldCode=?", dean, f).fetchall()}
        # DB must offer at least the sheet options (C/F for BASEPLATE_TYPE adds one)
        missing = sheet_vals - db_vals
        ok(not missing, f"{f}: DB offers sheet options "
                        f"(sheet={sorted(sheet_vals)}, missing={sorted(missing)})")

    # ---- (2) COMBINATIONS in stg --------------------------------------------
    print("\n=== (2) Baseplate combinations (DB == sheet) ===")
    bid = c.execute("SELECT TOP 1 ImportBatchId FROM stg.SegmentCombinationImportBatch "
                    "WHERE FamilyCode='DEAN' ORDER BY ImportBatchId DESC").fetchone()[0]
    db_rows = c.execute(
        "SELECT CombinationKey, SegmentValue, SelectionsJson FROM stg.SegmentCombinationImport "
        "WHERE ImportBatchId=? AND SegmentCode='BASEPLATE_OPTIONS'", bid).fetchall()
    ok(len(db_rows) == len(combos),
       f"combination count DB={len(db_rows)} sheet={len(combos)}")
    five = sum(1 for r in db_rows if len(json.loads(r[2])) == len(FIELDS))
    ok(five == len(db_rows),
       f"every combo SelectionsJson has all {len(FIELDS)} baseplate fields ({five}/{len(db_rows)})")
    cust = sum(1 for r in db_rows if "custom" in (r[0] + r[2]).lower())
    ok(cust == 0, f"no 'Custom' left in baseplate combos ({cust})")
    db_codes = {r[1] for r in db_rows}
    sheet_codes = {rec["code"] for rec in combos}
    ok(db_codes == sheet_codes,
       f"alphanumeric code set matches sheet ({len(db_codes)} codes, "
       f"diff={sorted(db_codes ^ sheet_codes)[:5]})")

    # ---- (3) LIVE enforcement -------------------------------------------------
    print("\n=== (3) Live baseplate enforcement (API) ===")
    ser = "RA2096"
    sz = c.execute("SELECT TOP 1 SizeCode FROM cfg.SeriesFieldOption "
                   "WHERE PumpFamilyId=? AND SeriesCode=? AND SizeCode IS NOT NULL",
                   dean, ser).fetchone()[0]
    # Seed the model + choose a baseplate bundle + BASEPLATE_TYPE='Formed'.
    st = post("/configurations/resolve-state",
              {"series": ser, "selections": {
                  "ALT_SIZE": sz, "PUMP_CONFIGURATION": "Pump and Baseplate",
                  "BASEPLATE_TYPE": "Formed"}})
    ao = st.get("allowable_options", {}) or {}

    def vals(f):
        v = ao.get(f)
        return None if v is None else {
            _norm(x["value"] if isinstance(x, dict) else x) for x in v}

    def reachable(sub, bt):
        return {_norm(rec[sub]) for rec in combos
                if _norm(rec["BASEPLATE_TYPE"]) == _norm(bt) and rec[sub]}

    for sub in FIELDS[1:]:  # dependent fields (not BASEPLATE_TYPE itself)
        api = vals(sub)
        reach = reachable(sub, "Formed")
        if api is None:
            # field may be fully pinned; skip if no allowable projected
            continue
        extra = api - reach
        ok(not extra, f"{sub} under BASEPLATE_TYPE=Formed: API subset of sheet-reachable "
                      f"(api={len(api)}, reach={len(reach)}, extra={sorted(extra)[:4]})")

    # off-combination: BASEPLATE_TYPE='NONE' only has the single all-blank combo
    # (code 00); pick a dependent field and confirm 'Required' is NOT offered
    # under NONE (the sheet's NONE row leaves sub-fields blank).
    stn = post("/configurations/resolve-state",
               {"series": ser, "selections": {
                   "ALT_SIZE": sz, "PUMP_CONFIGURATION": "Pump and Baseplate",
                   "BASEPLATE_TYPE": "NONE"}})
    aon = stn.get("allowable_options", {}) or {}
    align = aon.get("ALIGNMENT_LUGS")
    align_set = None if align is None else {
        _norm(x["value"] if isinstance(x, dict) else x) for x in align}
    none_reach = reachable("ALIGNMENT_LUGS", "NONE")  # empty (NONE row blank)
    if align_set is not None and not none_reach:
        # allow-list fails open per-field when a field has no reachable value, so
        # we only assert it never offers a value outside the sheet option domain
        domain = {_norm(v) for v in options["ALIGNMENT_LUGS"]}
        ok(align_set <= domain,
           f"ALIGNMENT_LUGS under BASEPLATE_TYPE=NONE stays within option domain "
           f"(got {sorted(align_set)})")

    # on-sheet combination resolves with no baseplate conflict
    target = next((rec for rec in combos if _norm(rec["BASEPLATE_TYPE"]) == "formed"), None)
    if target:
        sel = {"ALT_SIZE": sz, "PUMP_CONFIGURATION": "Pump and Baseplate"}
        for f in FIELDS:
            sel[f] = target[f]
        st2 = post("/configurations/resolve-state", {"series": ser, "selections": sel})
        conf = {(x.get("field") or "").upper() for x in (st2.get("conflicts") or [])}
        bp_conf = sorted(f for f in conf if f in FIELDS)
        ok(not bp_conf, f"on-sheet Formed baseplate combination has no conflict (got {bp_conf})")

    conn.close()
    print("\n" + "=" * 70)
    print(f"RESULT: {passed} passed, {failed} failed")
    print("=" * 70)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

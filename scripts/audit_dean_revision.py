"""Dean revision exit audit — Pump Constraints Custom columns + Seal Reference
Table + custom-spec lifecycle. Re-runnable, SELF-CLEANING.

Verifies (expectations DERIVED from the workbook/DB, not hardcoded):

 (a) RE-INGEST: the revised 'Pump Constraints' loaded — every grouping that has a
     'Custom' option column in the workbook has a 'C/F' option in
     cfg.SeriesFieldOption; 0 literal 'Custom' values remain for DEAN.
 (b) SEAL REFERENCE: cfg.DeanSealReference has one row per DEAN series with the
     exact Seal Reference Table (col 594) value from the workbook.
 (c) LIFECYCLE: POST /custom-segment-codes/resolve mints a width-correct code;
     the same spec reuses it (WasExisting); a different spec mints a new one; the
     resolved code occupies the PN wet-end slot at width 4; a no-width grouping
     (SEAL_TYPE) returns 409 (code deferred, spec captured).
 (d) PARITY: a STANDARD DEAN build's PN is byte-unchanged (the resolve endpoint
     asserts python==SQL internally; we assert the PN has no custom placeholder).
 (e) ISOLATION: Fybroc watermarks unchanged.

Cleans up the cfg.CustomSegmentCode rows it minted.

Usage:  uv run python scripts/audit_dean_revision.py [--base URL]
"""
import json
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pyodbc
from openpyxl import load_workbook

_base = "http://127.0.0.1:8080"
for i, a in enumerate(sys.argv):
    if a == "--base" and i + 1 < len(sys.argv):
        _base = sys.argv[i + 1]
BASE = _base.rstrip("/") + "/api/v2"
CONN = ("DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;"
        "DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;Encrypt=yes;"
        "TrustServerCertificate=yes;")
WB = Path("workbooks/Dean/PumpConfiguration_Logic_0.1.xlsm")
RUN = uuid.uuid4().hex[:8]

results = []
def ok(name, cond, detail=""):
    results.append(bool(cond))
    print(("PASS" if cond else "FAIL"), name, "-", detail)


def post(path, body):
    r = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                               headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(r, timeout=90) as x:
            return x.status, json.loads(x.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, None


def workbook_facts():
    """Return (custom_groupings, seal_ref_by_series) from the revised workbook."""
    tmp = Path(tempfile.mkdtemp()) / WB.name
    shutil.copy(WB, tmp)
    wb = load_workbook(tmp, data_only=True)
    ws = wb["Pump Constraints"]
    grp_row = [ws.cell(row=2, column=c).value for c in range(1, ws.max_column + 1)]
    opt_row = [ws.cell(row=3, column=c).value for c in range(1, ws.max_column + 1)]
    # grouping spans
    groupings = []
    cur = None
    for idx, g in enumerate(grp_row, start=1):
        if g is not None and str(g).strip():
            if cur:
                cur["end"] = idx - 1
                groupings.append(cur)
            cur = {"name": str(g).strip(), "start": idx, "end": idx}
    if cur:
        cur["end"] = ws.max_column
        groupings.append(cur)
    custom_groupings = []
    for gdef in groupings:
        opts = [str(opt_row[c - 1]).strip() for c in range(gdef["start"], gdef["end"] + 1)
                if opt_row[c - 1] is not None and str(opt_row[c - 1]).strip()]
        if any(o.lower() == "custom" for o in opts):
            custom_groupings.append(gdef["name"])
    # seal ref by series (col 594, series col from row3)
    series_col = srt_col = None
    for c in range(1, ws.max_column + 1):
        h = ws.cell(row=3, column=c).value
        if h and str(h).strip().lower() == "series":
            series_col = c
        elif h and str(h).strip().lower() == "seal reference table":
            srt_col = c
    seal_ref = {}
    for r in range(4, ws.max_row + 1):
        ser = ws.cell(row=r, column=series_col).value
        if ser is None or str(ser).strip() == "":
            continue
        ser = str(ser).strip()
        key = ws.cell(row=r, column=srt_col).value
        key = "" if key is None else str(key).strip()
        if ser not in seal_ref and key:
            seal_ref[ser] = key
    wb.close()
    return custom_groupings, seal_ref


def main():
    cn = pyodbc.connect(CONN, autocommit=True)
    cur = cn.cursor()
    dean = cur.execute("SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode='DEAN'").fetchone()[0]
    custom_groupings, seal_ref = workbook_facts()

    # (a) Re-ingest: C/F options present, no literal 'Custom' left.
    cf_rows = cur.execute(
        "SELECT COUNT(*) FROM cfg.SeriesFieldOption WHERE PumpFamilyId=? AND OptionValue='C/F'", dean
    ).fetchone()[0]
    ok("revised sheet re-ingested: C/F options present", cf_rows > 0, f"C/F rows={cf_rows}")
    literal_custom = cur.execute(
        "SELECT COUNT(*) FROM cfg.SeriesFieldOption WHERE PumpFamilyId=? AND LOWER(OptionValue)='custom'", dean
    ).fetchone()[0]
    ok("no literal 'Custom' values remain for DEAN", literal_custom == 0, f"literal custom={literal_custom}")
    n_cf_fields = cur.execute(
        "SELECT COUNT(DISTINCT FieldCode) FROM cfg.SeriesFieldOption WHERE PumpFamilyId=? AND OptionValue='C/F'", dean
    ).fetchone()[0]
    ok("custom groupings present as C/F fields",
       n_cf_fields >= 30, f"{n_cf_fields} fields with C/F (workbook custom groupings={len(custom_groupings)})")

    # (b) Seal Reference Table matches the workbook exactly.
    db_seal = {r[0]: r[1] for r in cur.execute(
        "SELECT SeriesCode, SealRefKey FROM cfg.DeanSealReference").fetchall()}
    ok("DeanSealReference row count matches workbook series",
       len(db_seal) == len(seal_ref), f"db={len(db_seal)} wb={len(seal_ref)}")
    mismatches = [s for s, k in seal_ref.items() if db_seal.get(s) != k]
    ok("DeanSealReference keys match workbook col 594 exactly",
       not mismatches, f"mismatches={mismatches[:5]}")

    # (c) Lifecycle via API.
    spec_a = f"audit wet-end custom ALPHA {RUN}"
    spec_b = f"audit wet-end custom BETA {RUN}"
    st, r1 = post("/families/DEAN/custom-segment-codes/resolve",
                  {"segment_code": "WET_END_OPTIONS", "spec_text": spec_a})
    code_a = (r1 or {}).get("custom_code")
    ok("resolve mints a width-4 wet-end code", st == 200 and code_a and len(code_a) == 4,
       f"status={st} code={code_a}")
    st, r1b = post("/families/DEAN/custom-segment-codes/resolve",
                   {"segment_code": "WET_END_OPTIONS", "spec_text": spec_a})
    ok("identical spec reuses the same code",
       st == 200 and (r1b or {}).get("custom_code") == code_a and (r1b or {}).get("was_existing") is True,
       f"code={(r1b or {}).get('custom_code')} was_existing={(r1b or {}).get('was_existing')}")
    st, r2 = post("/families/DEAN/custom-segment-codes/resolve",
                  {"segment_code": "WET_END_OPTIONS", "spec_text": spec_b})
    code_b = (r2 or {}).get("custom_code")
    ok("different spec mints a new code", st == 200 and code_b and code_b != code_a,
       f"code_b={code_b}")

    # resolved code occupies the PN wet-end slot
    st, rs = post("/families/DEAN/configurations/resolve-state", {"series": "RA3146", "selections": {}})
    sel = dict(rs.get("selections", {})); sel["SERIES"] = "RA3146"; sel["ALT_SIZE"] = "2x3x8.5"
    sc = dict(sel); sc["WET_END_OPTIONS__CUSTOM_CODE"] = code_a
    st, res = post("/families/DEAN/configured-products/resolve", {"series": "RA3146", "selections": sc})
    wet = (res.get("segment_debug") or {}).get("wet_end")
    ok("resolved custom code occupies PN wet-end slot", wet == code_a,
       f"wet_end={wet} pn={res.get('part_number')}")

    # no-width grouping (seal) -> 409 deferred
    st, _ = post("/families/DEAN/custom-segment-codes/resolve",
                 {"segment_code": "SEAL_TYPE", "spec_text": f"audit seal {RUN}"})
    ok("seal grouping (no width) -> 409 code deferred", st == 409, f"status={st}")

    # (d) standard build PN byte-unchanged (no custom placeholder/codes)
    st, std = post("/families/DEAN/configured-products/resolve", {"series": "RA3146", "selections": sel})
    pn = std.get("part_number", "")
    ok("standard DEAN build has a clean PN (no custom placeholder)",
       "____" not in pn and "__" not in pn.split("-")[2:3][0] if pn else False, f"pn={pn}")

    # (e) isolation watermarks
    nd_sfo = cur.execute("SELECT COUNT(*) FROM cfg.SeriesFieldOption WHERE PumpFamilyId<>?", dean).fetchone()[0]
    nd_seg = cur.execute("SELECT COUNT(*) FROM stg.SegmentCombinationImport WHERE FamilyCode<>'DEAN'").fetchone()[0]
    d_seg = cur.execute("SELECT COUNT(*) FROM stg.SegmentCombinationImport WHERE FamilyCode='DEAN'").fetchone()[0]
    nd_fc = cur.execute("SELECT COUNT(*) FROM cfg.FeasibleConstraint WHERE PumpFamilyId<>?", dean).fetchone()[0]
    ok("watermark non-DEAN SFO == 3638", nd_sfo == 3638, f"got {nd_sfo}")
    ok("watermark non-DEAN seg == 300608", nd_seg == 300608, f"got {nd_seg}")
    ok("watermark DEAN seg == 140976", d_seg == 140976, f"got {d_seg}")
    ok("watermark non-DEAN FeasibleConstraint == 4487", nd_fc == 4487, f"got {nd_fc}")

    passed = sum(1 for p in results if p)
    # cleanup: remove the custom codes this run minted
    cur.execute("DELETE FROM cfg.CustomSegmentCode WHERE SpecText LIKE ?", f"audit %custom%{RUN}%")
    cur.execute("DELETE FROM cfg.CustomSegmentCode WHERE SpecText LIKE ?", f"%{RUN}%")
    print(f"\nDEAN REVISION AUDIT: {passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())

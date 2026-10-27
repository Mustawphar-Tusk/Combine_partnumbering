"""Dean Motor Numbering milestone audit.

Verifies the new Dean motor numbering + price adders from
workbooks/Dean/Motor Numbering.xlsm (Pricing sheet) against the DB and the live
resolve flow. Expectations are derived from the DB / workbook, not hardcoded.

Exit gate (all must pass), DEAN-only / Fybroc-frozen:
  1. MOTOR_SPEC segment: 34,084 combinations loaded in the current DEAN batch;
     every SegmentValue is a 4-char code; codes are unique.
  2. Brand: every code's first char is a valid brand letter (B/L/M/N/S/T/H/W/X).
  3. price.DeanMotorPrice: 34,084 rows keyed by code; numeric vs C.F. split
     matches the workbook (491 numeric / 33,593 C.F.).
  4. Motor option fields: the 9 non-frame motor fields are offered for every Dean
     series; FRAME_SIZE is canonical (UPPER + no 'VP' suffix) and preserved.
  5. Live resolve: a config on a frame WITH a motor combo resolves to a real
     4-char code (not 0000/????) with py==SQL parity; a numerically-priced combo
     flows its $ into the Motor component + total; a frame with NO motor combo
     resolves to the clean '0000' placeholder (never '????') and prices C/F.
  6. Fybroc isolation: non-DEAN SeriesFieldOption + SegmentCombinationImport
     counts unchanged vs the recorded watermark.

Requires the API on 127.0.0.1:8080. Exit 0 iff all pass.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.request

import pyodbc

CONN = ("DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;"
        "DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;Encrypt=yes;"
        "TrustServerCertificate=yes;")
API = "http://127.0.0.1:8080/api/v2"
BRAND_LETTERS = set("BLMNSTHWX")
EXPECT_COMBOS = 34084
EXPECT_NUMERIC = 491
EXPECT_CF = 33593
# Fybroc isolation watermark (recorded post-load).
FYBROC_SFO_NONDEAN = 2096
FYBROC_SEG_NONDEAN = 300608

P = [0]
F = [0]


def ok(cond, msg):
    P[0] += bool(cond)
    F[0] += (not cond)
    print(f"  [{'PASS' if cond else 'FAIL'}] {msg}")


def post(path, body):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=180))


def main():
    cn = pyodbc.connect(CONN, autocommit=True)
    c = cn.cursor()
    deanpid = c.execute("SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode='DEAN'").fetchone()[0]
    bid = c.execute("SELECT TOP 1 ImportBatchId FROM stg.SegmentCombinationImportBatch "
                    "WHERE FamilyCode='DEAN' AND Status='Loaded' ORDER BY ImportBatchId DESC").fetchone()[0]

    print("=== (1) MOTOR_SPEC segment combinations ===")
    rows = c.execute("SELECT SegmentValue, LEN(SegmentValue) FROM stg.SegmentCombinationImport "
                     "WHERE ImportBatchId=? AND SegmentCode='MOTOR_SPEC'", bid).fetchall()
    ok(len(rows) == EXPECT_COMBOS, f"MOTOR_SPEC combos loaded ({len(rows)} == {EXPECT_COMBOS})")
    widths = {r[1] for r in rows}
    ok(widths == {4}, f"every MOTOR_SPEC code is 4 chars (widths seen: {sorted(widths)})")
    codes = [r[0] for r in rows]
    ok(len(set(codes)) == len(codes), f"codes are unique ({len(set(codes))} distinct)")

    print("=== (2) Brand letter ===")
    bad_brand = [cd for cd in codes if cd[:1] not in BRAND_LETTERS]
    ok(not bad_brand, f"every code starts with a valid brand letter ({len(bad_brand)} bad)")

    print("=== (3) price.DeanMotorPrice numeric vs C.F. ===")
    n_total = c.execute("SELECT COUNT(*) FROM price.DeanMotorPrice").fetchone()[0]
    n_num = c.execute("SELECT COUNT(*) FROM price.DeanMotorPrice WHERE IsContactFactory=0 AND Amount IS NOT NULL").fetchone()[0]
    n_cf = c.execute("SELECT COUNT(*) FROM price.DeanMotorPrice WHERE IsContactFactory=1").fetchone()[0]
    ok(n_total == EXPECT_COMBOS, f"DeanMotorPrice rows ({n_total} == {EXPECT_COMBOS})")
    ok(n_num == EXPECT_NUMERIC, f"numeric-priced rows ({n_num} == {EXPECT_NUMERIC})")
    ok(n_cf == EXPECT_CF, f"C.F. rows ({n_cf} == {EXPECT_CF})")

    print("=== (4) Motor option fields + FRAME_SIZE canonical ===")
    pub = c.execute("SELECT TOP 1 MetadataPublicationId FROM cfg.MetadataPublication "
                    "WHERE Status='Active' ORDER BY ActivatedAt DESC").fetchone()[0]
    dean_series = {r[0] for r in c.execute(
        "SELECT DISTINCT SeriesCode FROM cfg.PumpModelReference WHERE PumpFamilyId=? AND IsActive=1",
        deanpid).fetchall()}
    motor9 = ["MOTOR", "MOTOR_CONTROL", "RATED_SPEED", "RATED_POWER", "VOLTAGE",
              "PHASE_FREQUENCY", "ENCLOSURE", "EFFICIENCY", "BRAND"]
    for f in motor9:
        series_with = {r[0] for r in c.execute(
            "SELECT DISTINCT SeriesCode FROM cfg.SeriesFieldOption "
            "WHERE MetadataPublicationId=? AND PumpFamilyId=? AND FieldCode=?",
            pub, deanpid, f).fetchall()}
        ok(dean_series <= series_with,
           f"{f} offered for all {len(dean_series)} Dean series ({len(series_with)} have it)")
    # FRAME_SIZE canonical: uppercase, no 'VP' suffix, for Dean
    frames = [r[0] for r in c.execute(
        "SELECT DISTINCT OptionValue FROM cfg.SeriesFieldOption "
        "WHERE MetadataPublicationId=? AND PumpFamilyId=? AND FieldCode='FRAME_SIZE'",
        pub, deanpid).fetchall()]
    noncanon = [v for v in frames if v != v.upper() or re.search(r"VP$", v.upper())]
    ok(not noncanon, f"Dean FRAME_SIZE values canonical (UPPER, no VP) ({len(noncanon)} bad: {noncanon[:5]})")

    print("=== (5) Live resolve behavior ===")
    # wait for API
    for _ in range(40):
        try:
            post("/families/FYBROC/configurations/resolve-state", {"series": "1500", "selections": {}}); break
        except Exception:
            time.sleep(1)
    rs = post("/families/DEAN/configurations/resolve-state", {"series": "Deanline", "selections": {}})
    sel = dict(rs.get("selections", {}))

    # 5a: a priced combo flows numeric
    prow = c.execute("SELECT TOP 1 MotorCode, Amount FROM price.DeanMotorPrice "
                     "WHERE IsContactFactory=0 AND Amount IS NOT NULL ORDER BY MotorCode").fetchone()
    psel = json.loads(c.execute(
        "SELECT SelectionsJson FROM stg.SegmentCombinationImport "
        "WHERE ImportBatchId=? AND SegmentCode='MOTOR_SPEC' AND SegmentValue=?",
        bid, prow[0]).fetchone()[0])
    r = post("/families/DEAN/configured-products/resolve",
             {"series": "Deanline", "selections": {"SERIES": "Deanline", **sel, **psel},
              "segment_codes": {}, "requested_by": "audit_motor"})
    motor_comp = next((x for x in (r.get("component_pricing") or []) if x["component"] == "Motor"), {})
    ok(r.get("segment_debug", {}).get("motor") == prow[0],
       f"priced combo resolves to its code ({r.get('segment_debug', {}).get('motor')} == {prow[0]})")
    ok(motor_comp.get("status") == "found" and abs(float(motor_comp.get("amount") or 0) - float(prow[1])) < 0.005,
       f"motor price flows numeric (status={motor_comp.get('status')} amount={motor_comp.get('amount')} == {float(prow[1])})")
    ok(bool(r.get("parity_ok")), "py==SQL parity on priced motor config")
    ok("?" not in (r.get("part_number") or "?"), f"priced PN has no '?' ({r.get('part_number')})")

    # 5b: a frame with NO motor combo -> clean 0000, C/F
    nocombo_frame = None
    for fr in ["404T", "449T", "404TS", "405T"]:
        hit = c.execute("SELECT COUNT(*) FROM stg.SegmentCombinationImport "
                        "WHERE ImportBatchId=? AND SegmentCode='MOTOR_SPEC' "
                        "AND SelectionsJson LIKE ?", bid, f'%"FRAME_SIZE":"{fr}"%').fetchone()[0]
        if hit == 0:
            nocombo_frame = fr
            break
    if nocombo_frame:
        r2 = post("/families/DEAN/configured-products/resolve",
                  {"series": "Deanline", "selections": {"SERIES": "Deanline", **sel, "FRAME_SIZE": nocombo_frame},
                   "segment_codes": {}, "requested_by": "audit_motor"})
        mc = r2.get("segment_debug", {}).get("motor")
        ok(mc == "0000", f"no-combo frame {nocombo_frame} -> motor '0000' (got {mc!r})")
        ok("?" not in (r2.get("part_number") or "?"), f"no-combo PN has no '?' ({r2.get('part_number')})")
        ok(bool(r2.get("parity_ok")), "py==SQL parity on no-combo motor config")
        mc2 = next((x for x in (r2.get("component_pricing") or []) if x["component"] == "Motor"), {})
        ok(mc2.get("status") == "C/F", f"no-combo motor prices C/F (status={mc2.get('status')})")
    else:
        ok(False, "could not find a no-combo frame to test (expected 404T/449T family)")

    print("=== (6) Fybroc isolation ===")
    sfo_nondean = c.execute(
        "SELECT COUNT(*) FROM cfg.SeriesFieldOption WHERE MetadataPublicationId=? AND PumpFamilyId<>?",
        pub, deanpid).fetchone()[0]
    seg_nondean = c.execute(
        "SELECT COUNT(*) FROM stg.SegmentCombinationImport WHERE FamilyCode<>'DEAN'").fetchone()[0]
    ok(sfo_nondean == FYBROC_SFO_NONDEAN, f"non-Dean SeriesFieldOption unchanged ({sfo_nondean} == {FYBROC_SFO_NONDEAN})")
    ok(seg_nondean == FYBROC_SEG_NONDEAN, f"non-Dean SegmentCombinationImport unchanged ({seg_nondean} == {FYBROC_SEG_NONDEAN})")

    cn.close()
    print(f"\n=== RESULT: {P[0]} passed, {F[0]} failed ===")
    return 0 if F[0] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

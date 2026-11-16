"""Dean seal milestone audit (re-runnable; exit non-zero on any failure).

Expectations are derived from SealNumbering.xlsx and the DB, not hardcoded:
  A. Master options: every DEAN (series,size) carrying a replaced seal field has
     EXACTLY the Master contiguous-block options for it; no 'C/F' option remains;
     SEAL_CHAMBER_CONFIG and SEAL_OPTION were NOT replaced.
  B. cfg.DeanSealSpec row counts / price classes / code widths per sheet equal the
     workbook; every non-'X' DeanSealReference key has spec rows; Combined Table
     and Type sheets were not loaded.
  C. Resolver: a sample of spec rows per sheet resolves back to a code (lowest code
     on source-duplicate combos) with the right price class; not-Included -> '000';
     incomplete/C-F selection -> 'TBD'; series with ref 'X' -> 'TBD'.
  D. API: PN carries the seal code between power-frame and flush groups with
     python==SQL parity; Seal component priced / C/F as per price class.
  E. Isolation: non-DEAN SeriesFieldOption / FeasibleConstraint / ConstraintFieldMap
     unchanged (3638 / 4487 / 28).

Run (API on 127.0.0.1:8080):
  $env:PYTHONPATH="."; uv run python scripts/audit_dean_seal.py
"""
from __future__ import annotations

import json
import random
import re
import sys
import urllib.request
from collections import Counter

import pyodbc

sys.path.insert(0, ".")
sys.path.insert(0, "scripts")
import load_dean_seal_master as M  # noqa: E402
import load_dean_seal_spec as L  # noqa: E402
from src.api import dean_seal as S  # noqa: E402
from openpyxl import load_workbook  # noqa: E402
import shutil, tempfile  # noqa: E402
from pathlib import Path  # noqa: E402

BASE = "http://127.0.0.1:8080/api/v2/families/DEAN"
CS = ('DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=PumpConfiguratorDB;'
      'Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;')
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
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def main():
    cn = pyodbc.connect(CS)
    c = cn.cursor()
    dean = c.execute("SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode='DEAN'").fetchone()[0]
    domains = M.read_master()
    misc_series = {r[0] for r in c.execute(
        "SELECT SeriesCode FROM cfg.DeanSealReference WHERE SealRefKey='Misc.'")}

    print("A. Master options replace seal selection options")
    bad = []
    rows = c.execute("SELECT SeriesCode, SizeCode, FieldCode, OptionValue FROM cfg.SeriesFieldOption "
                     "WHERE PumpFamilyId=? AND FieldCode IN (%s)" % ",".join("?" * len(domains)),
                     dean, *domains).fetchall()
    got = {}
    for ser, sz, fc, v in rows:
        got.setdefault((ser, sz, fc), []).append(v)
    for (ser, sz, fc), vals in got.items():
        if sorted(vals) != sorted(domains[fc]):
            bad.append((ser, sz, fc))
    ok(not bad, f"all {len(got)} (series,size,field) option sets equal the Master block", str(bad[:3]))
    ok(not any(v == "C/F" for vs in got.values() for v in vs), "no 'C/F' option in replaced seal fields")
    gk = [k for k in got if k[2] == "GLAND_GASKET"]
    ok(gk and all(k[0] in misc_series for k in gk), f"GLAND_GASKET only for Misc. series ({len(gk)} sets)")
    sc = c.execute("SELECT COUNT(*), SUM(CASE WHEN OptionValue LIKE 'Large Taper%' OR OptionValue LIKE '%Jacketed%' THEN 1 ELSE 0 END) "
                   "FROM cfg.SeriesFieldOption WHERE PumpFamilyId=? AND FieldCode='SEAL_CHAMBER_CONFIG'", dean).fetchone()
    ok(sc[0] == 616 and sc[1] > 0, "SEAL_CHAMBER_CONFIG left untouched (616 rows, wet-end values intact)", str(tuple(sc)))
    so = c.execute("SELECT COUNT(*) FROM cfg.SeriesFieldOption WHERE PumpFamilyId=? AND FieldCode='SEAL_OPTION'", dean).fetchone()[0]
    ok(so == 365, "SEAL_OPTION left untouched (365 rows)", str(so))
    junk = {"Hastelloy C", "Tandem Component", "Standard Bore Jacketed"}
    ok(not any(v in junk for vs in got.values() for v in vs), "old-vocabulary / junk values absent from replaced fields")

    print("B. cfg.DeanSealSpec mirrors the workbook")
    tmp = Path(tempfile.mkdtemp()) / "s.xlsx"
    shutil.copy(L.SRC, tmp)
    wb = load_workbook(tmp, data_only=True, read_only=True)
    sheet_rows = {}
    for s in L.SHEETS:
        sheet_rows[s] = L.read_sheet(wb, s)
    sheetnames = set(wb.sheetnames)
    wb.close()
    for s, rws in sheet_rows.items():
        db = c.execute("SELECT COUNT(*), COUNT(DISTINCT SealCode), SUM(CASE WHEN PriceStatus='PRICED' THEN 1 ELSE 0 END), "
                       "SUM(CASE WHEN PriceStatus='CF' THEN 1 ELSE 0 END), SUM(CASE WHEN PriceStatus='TBD' THEN 1 ELSE 0 END) "
                       "FROM cfg.DeanSealSpec WHERE SealRefKey=?", s).fetchone()
        st = Counter(r[6] for r in rws)
        exp = (len(rws), len({r[1] for r in rws}), st["PRICED"], st["CF"], st["TBD"])
        ok(tuple(db) == exp, f"{s}: rows/codes/priced/CF/TBD = {exp}", f"db={tuple(db)}")
    refs = {r[0] for r in c.execute("SELECT DISTINCT SealRefKey FROM cfg.DeanSealReference WHERE SealRefKey<>'X'")}
    ok(refs <= set(L.SHEETS), f"every Seal Reference key has a loaded sheet {sorted(refs)}")
    ok({r[0] for r in c.execute("SELECT DISTINCT SealRefKey FROM cfg.DeanSealSpec")} == set(L.SHEETS),
       "DeanSealSpec holds exactly the 7 permutation sheets (no Combined Table / Type sheets)")
    tot = c.execute("SELECT COUNT(*) FROM cfg.DeanSealSpec").fetchone()[0]
    ok(tot == sum(len(v) for v in sheet_rows.values()), f"total spec rows == workbook coded rows ({tot})")

    print("C. Resolver round-trip")
    random.seed(7)
    for s, rws in sheet_rows.items():
        series = c.execute("SELECT TOP 1 SeriesCode FROM cfg.DeanSealReference WHERE SealRefKey=?", s).fetchone()[0]
        first = {}
        for r in rws:
            first.setdefault(r[3], r)            # lowest source row per combo hash (codes ascending in source)
        low = {}
        for h, r in first.items():
            pass
        by = {}
        for r in rws:
            by.setdefault(r[3], []).append(r)
        sample = random.sample(list(by.values()), 150)
        bad = 0
        fields = [f for f in S.SEAL_KEY_FIELDS if not (f == "GLAND_GASKET" and s not in S.GASKET_SHEETS)]
        for grp in sample:
            r = grp[0]
            sel = dict(zip(fields, r[2].split("*")))
            sel["SEAL_OPTION"] = "Included"
            res = S.resolve_seal_spec(c, series, sel)
            if res["status"] != "resolved" or res["code"] != min(g[1] for g in grp):
                bad += 1
        ok(bad == 0, f"{s}: 150 sampled permutations resolve to their code", f"bad={bad}")
    r1 = S.resolve_seal_spec(c, "RA2096", {"SEAL_OPTION": "Supplied by others, installed by Dean"})
    ok(r1["code"] == "000" and r1["status"] == "none", "seal not Included -> '000'")
    xs = c.execute("SELECT TOP 1 SeriesCode FROM cfg.DeanSealReference WHERE SealRefKey='X'").fetchone()[0]
    r2 = S.resolve_seal_spec(c, xs, {"SEAL_OPTION": "Included"})
    ok(r2["code"] == "TBD" and r2["status"] == "pending", "series with ref 'X' -> 'TBD' (engineering)")
    r3 = S.resolve_seal_spec(c, "DL200", {"SEAL_OPTION": "Included", "SEAL_TYPE": "C/F"})
    ok(r3["code"] == "TBD", "incomplete / C-F seal selection -> 'TBD'")

    print("D. API: PN slot, parity, pricing")
    n = 0
    for s in ['1.000" Shafts', "3.000" + '" Shafts', "Misc."]:
        series = c.execute("SELECT TOP 1 SeriesCode FROM cfg.DeanSealReference WHERE SealRefKey=?", s).fetchone()[0]
        rws = sheet_rows[s]
        for want in (("PRICED", "BLANK") if s == "Misc." else ("PRICED", "CF")):
            st = post("/configurations/resolve-state", {"series": series, "selections": {}})
            sel = dict(st.get("selections") or {})
            sel["SERIES"] = series
            cls = S.normalize_chamber(sel.get("SEAL_CHAMBER_CONFIG", "Standard Bore"))
            ci = S.SEAL_KEY_FIELDS.index("SEAL_CHAMBER_CONFIG") - (
                0 if s in S.GASKET_SHEETS else 0)
            r = next((x for x in rws if x[6] == want and x[0] == s
                      and x[2].split("*")[ci] == cls), None)
            if r is None:       # no row in the STD bore class (e.g. only 4 priced Misc. rows)
                r = next(x for x in rws if x[6] == want and x[0] == s)
                cls = r[2].split("*")[ci]
                sel["SEAL_CHAMBER_CONFIG"] = "Large Bore" if "large" in cls else "Standard Bore"
            fields = [f for f in S.SEAL_KEY_FIELDS if not (f == "GLAND_GASKET" and s not in S.GASKET_SHEETS)]
            vals = dict(zip(fields, r[2].split("*")))
            # restore Master casing for the values
            for f, v in vals.items():
                for mv in domains.get(f, []):
                    if S._n(mv) == v:
                        vals[f] = mv
            vals["SEAL_CHAMBER_CONFIG"] = sel.get("SEAL_CHAMBER_CONFIG", "Standard Bore")
            sel.update(vals)
            sel["SEAL_OPTION"] = "Included"
            res = post("/configured-products/resolve", {"series": series, "selections": sel, "requested_by": "seal-audit"})
            pn = res.get("part_number") or ""
            dbg = res.get("segment_debug") or {}
            spec = dbg.get("seal_spec") or {}
            slot = re.search(r"-%s-" % re.escape(dbg.get("seal_code", "?")), pn)
            comp = [c_ for c_ in (res.get("component_pricing") or []) if c_.get("component") == "Seal"]
            if spec.get("status") == "resolved":
                exp_ok = (spec.get("price_status") == want or (want == "CF" and spec.get("price_status") in ("CF",)))
                comp_ok = bool(comp) and (comp[0].get("amount") is not None) == (want == "PRICED")
                ok(bool(slot) and res.get("parity_ok") is True and exp_ok and comp_ok,
                   f"{s} {want}: PN {pn} parity ok, Seal component {'priced' if want=='PRICED' else 'C/F'}",
                   f"spec={spec} comp={comp}")
            else:
                ok(False, f"{s} {want}: seal did not resolve via API", f"spec={spec}")
            n += 1
    sel = dict((post("/configurations/resolve-state", {"series": "DL200", "selections": {}}).get("selections") or {}))
    sel["SERIES"] = "DL200"
    sel["SEAL_OPTION"] = "Supplied by others, installed by Dean"
    res = post("/configured-products/resolve", {"series": "DL200", "selections": sel, "requested_by": "seal-audit"})
    pn = res.get("part_number") or ""
    parts = pn.split("-")
    ok(len(parts) >= 5 and parts[4] == "000" and res.get("parity_ok") is True,
       f"not-Included seal -> '-000-' slot in PN ({pn})")

    print("E. Isolation (Fybroc / non-DEAN unchanged)")
    for t, exp in (("SeriesFieldOption", 3638), ("FeasibleConstraint", 4487), ("ConstraintFieldMap", 28)):
        v = c.execute(f"SELECT COUNT(*) FROM cfg.{t} WHERE PumpFamilyId<>?", dean).fetchone()[0]
        ok(v == exp, f"non-DEAN cfg.{t} == {exp}", str(v))
    stg = c.execute("SELECT COUNT(*) FROM stg.SegmentCombinationImport i JOIN stg.SegmentCombinationImportBatch b "
                    "ON b.ImportBatchId=i.ImportBatchId WHERE b.FamilyCode<>'DEAN'").fetchone()[0]
    ok(stg == 300608, "non-DEAN stg.SegmentCombinationImport == 300608", str(stg))

    print(f"\nRESULT: {passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

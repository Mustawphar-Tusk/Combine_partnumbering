"""Dean seal OPTION-COMPLETENESS audit: no selectable seal option is lost by accident.

For every Dean model (series x size) in Pump Constraints and every seal field, each
option Pump Constraints offers is traced to what the configurator actually offers
on a fresh configuration, and every omission is classified:

  OFFERED            selectable on a fresh configuration
  NOT_ON_MASTER      value has no SealNumbering 'Master' equivalent (e.g. 'Custom',
                     'Tandem Component'); excluded by the owner rule (Master is the
                     vocabulary authority)
  NO_SHEET           series has Seal Reference 'X' / no sheet: not narrowed, so this
                     cannot occur for a loaded value (checked)
  NARROWED_BY_STD    on the series' sheet, but not with the seeded Seal Configuration /
                     Seal Type STD (legitimate; selectable after changing them)
  NOT_ON_SHEET       Master value that never appears on the series' sheet (the sheet
                     has no permutation for it)
  SPELLING_MISMATCH  NOT_ON_SHEET, but the sheet carries a value that looks like the
                     same option spelled differently  -> FAIL (vocabulary bug)
  LOADER_LOSS        mapped to Master but missing from cfg.SeriesFieldOption -> FAIL

Also: Master values never offered by any model, and an API spot check that the
live resolve-state option lists equal this audit's computed lists.

Exit non-zero on any FAIL. Run (API on 127.0.0.1:8080 for the spot check):
  $env:PYTHONPATH="."; uv run python scripts/audit_dean_seal_options.py [--no-api]
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from collections import Counter, defaultdict

import pyodbc

sys.path.insert(0, ".")
sys.path.insert(0, "scripts")
import load_dean_seal_master as M  # noqa: E402
from src.api import dean_seal as S  # noqa: E402

CS = ('DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=PumpConfiguratorDB;'
      'Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;')
BASE = "http://127.0.0.1:8080/api/v2/families/DEAN"
FIELDS = S.CASCADE_FIELDS + ("SEAL_OPTION", "SEAL_MANUFACTURER")
_STOP = {"jc", "fas", "type", "seal", "psi"}


def _tokens(v):
    return {t for t in re.split(r"[^a-z0-9]+", S._n(v)) if t and t not in _STOP}


def looks_same(a, b):
    ta, tb = _tokens(a), _tokens(b)
    return bool(ta) and bool(tb) and (ta == tb or ta <= tb or tb <= ta)


def post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode())


def main():
    use_api = "--no-api" not in sys.argv
    c = pyodbc.connect(CS).cursor()
    dean = c.execute("SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode='DEAN'").fetchone()[0]
    domains = M.read_master()
    canon = {f: {S._n(v): v for v in vals} for f, vals in domains.items()}
    ref_of = dict(c.execute("SELECT SeriesCode, SealRefKey FROM cfg.DeanSealReference").fetchall())
    sfo = defaultdict(list)
    std = defaultdict(dict)
    for ser, size, fc, v, isstd in c.execute(
            "SELECT SeriesCode, SizeCode, FieldCode, OptionValue, IsStandard FROM cfg.SeriesFieldOption "
            "WHERE PumpFamilyId=? AND FieldCode IN (%s) ORDER BY SeriesFieldOptionId" % ",".join("?" * len(FIELDS)),
            dean, *FIELDS):
        sfo[(ser, size, fc)].append(v)
        if isstd:
            std[(ser, size)][fc] = v
    sheet_vals = {}
    for ref in S.SHEET_TABLE:
        fields, rows, _ = S._sheet_rows(c, ref)
        sheet_vals[ref] = {f: {r[i] for r in rows} for i, f in enumerate(fields)}

    models = M.read_pc_models()
    status = Counter()
    by_series = defaultdict(Counter)
    detail = defaultdict(set)          # (category, field, value) -> series
    computed = {}                      # (ser,size) -> {field: [options]}
    for m in models:
        ser, size = m["series"], m["size"]
        ref = ref_of.get(ser)
        seed = {f: v for f, v in std[(ser, size)].items() if f in S.CASCADE_FIELDS}
        S.prune_seed(c, ser, seed) if ref and ref != "X" else None
        allow = {f: list(sfo.get((ser, size, f), [])) for f in FIELDS}
        S.filter_options(c, ser, seed, allow, std=std[(ser, size)])
        computed[(ser, size)] = allow
        for f in FIELDS:
            for v, _mk in (m["cells"].get(f) or {}).items():
                if f in canon:
                    mv = M.to_master(f, v, canon)
                    if mv is None:
                        cat = "NOT_ON_MASTER"
                    elif mv not in sfo.get((ser, size, f), []):
                        cat = "LOADER_LOSS"
                    elif mv in allow[f]:
                        cat = "OFFERED"
                    elif not ref or ref == "X":
                        cat = "NO_SHEET"
                    else:
                        on_sheet = S.canon_value(f, mv) in sheet_vals[ref].get(f, set())
                        if on_sheet:
                            cat = "NARROWED_BY_STD"
                        else:
                            near = [w for w in sheet_vals[ref].get(f, set())
                                    if w not in {S._n(x) for x in domains[f]} and looks_same(w, mv)]
                            cat = "SPELLING_MISMATCH" if near else "NOT_ON_SHEET"
                            if near:
                                detail[("NEAR", f, mv)].update(near)
                else:   # SEAL_OPTION: not on Master, loaded from Pump Constraints as-is
                    cat = "OFFERED" if S._n(v) in {S._n(x) for x in allow[f]} else "LOADER_LOSS"
                status[cat] += 1
                by_series[ser][cat] += 1
                if cat != "OFFERED":
                    detail[(cat, f, mv if f in canon and cat != "NOT_ON_MASTER" else v)].add(ser)

    # Master values no model offers at all
    offered_any = defaultdict(set)
    for (ser, size, f), vals in sfo.items():
        offered_any[f].update(vals)
    never = {f: [v for v in vals if v not in offered_any[f]] for f, vals in domains.items()}

    print("=" * 96)
    print(f"DEAN SEAL OPTION-COMPLETENESS AUDIT - {len(models)} models, {len(FIELDS)} seal fields")
    print("=" * 96)
    print("Pump Constraints offered values by outcome:", dict(status))
    print("\nPer series (non-OFFERED outcomes):")
    for ser in sorted(by_series):
        cc = {k: v for k, v in by_series[ser].items() if k != "OFFERED"}
        print(f"  {ser:18} {ref_of.get(ser, '-'):14} offered={by_series[ser]['OFFERED']:4} {cc}")
    print("\nOmitted values (category, field, value -> series):")
    for (cat, f, v), sers in sorted(detail.items()):
        if cat == "NEAR":
            continue
        extra = ""
        if cat == "SPELLING_MISMATCH":
            extra = f"  sheet spelling: {sorted(detail[('NEAR', f, v)])}"
        print(f"  {cat:17} {f:34} {v!r:48} {len(sers):2} series{extra}")
    print("\nMaster values no Dean model offers:")
    for f, vs in never.items():
        if vs:
            print(f"  {f}: {vs}")

    print("\nSheet values with no Master spelling (their permutations cannot be selected):")
    for ref in S.SHEET_TABLE:
        fields, rows, _ = S._sheet_rows(c, ref)
        for i, f in enumerate(fields):
            if f not in canon:
                continue
            extra = Counter(r[i] for r in rows if r[i] not in canon[f])
            for v, n in sorted(extra.items()):
                print(f"  {ref:14} {f:34} {v!r:34} {n:6} permutations")

    failed = 0
    for cat in ("SPELLING_MISMATCH", "LOADER_LOSS"):
        n = status[cat]
        print(f"\n[{'PASS' if n == 0 else 'FAIL'}] no {cat} ({n})")
        failed += n > 0
    nos = status["NO_SHEET"]
    print(f"[{'PASS' if nos == 0 else 'FAIL'}] series without a sheet are never narrowed ({nos})")
    failed += nos > 0

    if use_api:
        bad = []
        sample = ["DL200", "CNV206", "PH2140", "R4240", "RA2096", "RTA3146", "RWA4166", "RS", "M300 (FRAME III)"]
        for ser in sample:
            st = post("/configurations/resolve-state", {"series": ser, "selections": {}})
            sel = st.get("selections") or {}
            sz = str(sel.get("ALT_SIZE") or sel.get("SIZE") or "").lower()
            key = next((k for k in computed if k[0] == ser and str(k[1]).lower() == sz), None)
            if key is None:
                bad.append((ser, "size not found"))
                continue
            api = st.get("allowable_options") or {}
            for f in FIELDS:
                if f in api and sorted(api[f]) != sorted(computed[key][f]):
                    bad.append((ser, f, sorted(set(api[f]) ^ set(computed[key][f]))[:3]))
        ok = not bad
        print(f"[{'PASS' if ok else 'FAIL'}] API resolve-state seal option lists == audit lists ({len(sample)} series)"
              + ("" if ok else f" {bad[:4]}"))
        failed += not ok
        st = post("/configurations/resolve-state", {"series": "DL200", "selections": {}})
        has = "JC Type 8BITH/8-1T" in (st.get("allowable_options") or {}).get("SEAL_TYPE", [])
        print(f"[{'PASS' if has else 'FAIL'}] DL200 offers 'JC Type 8BITH/8-1T' (owner report)")
        failed += not has

    print(f"\nRESULT: {'FAIL' if failed else 'PASS'} ({failed} failing checks)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

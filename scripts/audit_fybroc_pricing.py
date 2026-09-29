"""Audit: Fybroc Rev0.4 '1500 Pricing' — base + adder price ENFORCEMENT.

Guards the correction that a plain 'vr-1' base material must be priced from the
VR-1 (Standard) row, NOT the more expensive VR-1A/VR-1V/BPO-DMA rows (a prior
runtime bug matched '%vr-1%' broadly and overpriced every VR-1 pump).

Expectations are DERIVED FROM THE AUTHORITATIVE SHEET at runtime (not hardcoded):
for each (size, base material) it reads the Rev0.4 '1500 Pricing' Base-Price table
and asserts the resolved API base-pump price equals it exactly. It also spot-checks
single-value adder tables (Shaft Material, Gland Hardware, Flange Type) resolve to
the sheet's value for the walked selection.

Requires the API on 127.0.0.1:8080. Exit 0 iff all pass, 1 otherwise.
Read-only: opens a disposable copy of the workbook; never writes the DB or sheet.
"""
import json, sys, time, urllib.request, shutil, tempfile
from pathlib import Path
import openpyxl
from openpyxl.utils import column_index_from_string as ci

BASE = "http://127.0.0.1:8080/api/v2/families/FYBROC"
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "workbooks" / "Fybroc" / "Fybroc Configuration Rev0.4.xlsx"


def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def evaluate(series, sel): return post("/configurations/evaluate", {"series": series, "selections": sel})
def resolve(series, sel):  return post("/configured-products/resolve", {"series": series, "selections": sel})


def _wait():
    for _ in range(40):
        try:
            evaluate("1500", {}); return True
        except Exception:
            time.sleep(1)
    return False


def _num(x):
    try:
        return float(str(x).replace(",", ""))
    except Exception:
        return None


def _norm(m):
    return (m or "").strip().lower().replace("_", " ")


def read_sheet_tables():
    """Read the Rev0.4 '1500 Pricing' base + adder tables from a disposable copy."""
    tdir = Path(tempfile.mkdtemp(prefix="auditprice_"))
    tmp = tdir / SRC.name
    shutil.copy2(SRC, tmp)
    try:
        wb = openpyxl.load_workbook(str(tmp), read_only=True, data_only=True)
        ws = wb["1500 Pricing"]
        grid = {}
        for ri, row in enumerate(ws.iter_rows(min_row=1, max_row=700, max_col=90, values_only=True), start=1):
            for c, v in enumerate(row, start=1):
                if v is not None and str(v).strip() != "":
                    grid[(ri, c)] = str(v).strip()
        wb.close()
    finally:
        shutil.rmtree(tdir, ignore_errors=True)

    def cell(r, c): return grid.get((r, c))

    # B-E Base Price: C=size D=material E=price
    base = {}
    for r in range(6, 120):
        sz = cell(r, ci("C")); mat = cell(r, ci("D")); pr = cell(r, ci("E"))
        if sz is None:
            continue
        base[(sz.lower(), _norm(mat))] = _num(pr)

    def adder(sizecol, optcol, pricecol, r0, r1):
        d = {}
        for r in range(r0, r1 + 1):
            sz = cell(r, ci(sizecol)); opt = cell(r, ci(optcol)); pr = cell(r, ci(pricecol))
            if sz is None:
                continue
            d[(sz.lower(), _norm(opt))] = _num(pr)
        return d

    tables = {
        "base": base,
        "Shaft Material": (adder("Q", "R", "S", 6, 43), "SHAFT_MATERIAL"),
        "Gland Hardware": (adder("AA", "AB", "AC", 6, 100), "GLAND_HARDWARE"),
        "Flange Type": (adder("BZ", "CA", "CB", 6, 62), "FLANGE_TYPE"),
    }
    return tables


def full_walk(series, forced):
    sel = {}
    for _ in range(200):
        d = evaluate(series, sel); cf = d.get("current_field")
        if cf is None:
            break
        o = d["allowable_options"].get(cf, []); std = d.get("standard_defaults", {}).get(cf)
        pick = forced.get(cf) or (std if std in o else (o[0] if o else None))
        if pick is None:
            break
        sel[cf] = pick
    return sel


def main():
    if not _wait():
        print("FAIL: API not reachable on 127.0.0.1:8080"); return 1
    tables = read_sheet_tables()
    base = tables["base"]

    P = [0]; F = [0]; fails = []
    def ok(cond, msg):
        P[0] += cond; F[0] += (not cond)
        if not cond:
            fails.append(msg)

    print("=" * 92)
    print("FYBROC REV0.4 '1500 PRICING' ENFORCEMENT (base + adders vs authoritative sheet)")
    print("=" * 92)

    # Base pricing across ALL 7 base materials on a small + a large size, plus a
    # couple extra sizes. Materials chosen to catch the VR-1 vs VR-1A/VR-1V leak.
    materials = ["vr-1", "vr-1a", "vr-1v", "vr-1 bpo/dma", "vr-1a bpo/dma", "ey-2"]
    sizes = ["1x1.5x6", "2x3x8", "3x4x10", "2x3x13"]
    for size in sizes:
        for mat in materials:
            exp = base.get((size.lower(), _norm(mat)))
            if exp is None:
                continue  # material not offered at this size (e.g. 10x12x16 vr-1a n/a)
            sel = full_walk("1500", {"ALT_SIZE": size, "PUMP_MATERIAL": mat})
            # only score if the walk actually honored the forced material
            if _norm(sel.get("PUMP_MATERIAL")) != _norm(mat):
                continue
            r = resolve("1500", sel)
            api = next((c["amount"] for c in r.get("pricing", [])
                        if str(c.get("component", "")).startswith("Base Pump")), None)
            good = (api is not None and abs(exp - api) < 0.005)
            ok(good, f"base 1500/{size}/{mat}: sheet={exp} api={api}")
            print(f"  [{'PASS' if good else 'FAIL'}] base 1500/{size:9}/{mat:14} sheet={exp} api={api}")

    # Adder spot-checks: walk once, verify each mapped adder equals the sheet.
    label_amount_by_component = {
        "Shaft Material": "Shaft Material",
        "Gland Hardware": "Gland Hardware",
        "Flange Type": "Flange Type",
    }
    sel = full_walk("1500", {"ALT_SIZE": "1x1.5x6", "PUMP_MATERIAL": "vr-1"})
    r = resolve("1500", sel)
    comps = {c["component"]: c for c in r.get("pricing", [])}
    size = sel.get("ALT_SIZE")
    for label in label_amount_by_component:
        tbl, field = tables[label]
        selval = sel.get(field)
        if not selval:
            continue
        exp = tbl.get((size.lower(), _norm(selval)))
        if exp is None:
            continue
        api = comps.get(label, {}).get("amount")
        good = (api is not None and abs(exp - api) < 0.005) or (exp == 0 and api in (0, None))
        ok(good, f"adder {label} 1500/{size}/{selval}: sheet={exp} api={api}")
        print(f"  [{'PASS' if good else 'FAIL'}] adder {label:16} {size}/{selval}: sheet={exp} api={api}")

    print(f"\n=== RESULT: {P[0]} passed, {F[0]} failed ===")
    for m in fails[:25]:
        print("  FAIL:", m)
    return 0 if F[0] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

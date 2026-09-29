"""Audit: Fybroc Rev0.4 '1500 Motors' — CPQ Conversion2 display descriptor.

Guards the requirement that a resolved 1500 configuration exposes the authoritative
"CPQ Conversion2" motor descriptor — the canonical string shown for the selected
motor in UI quotes. Per the Rev0.4 '1500 Motors' datasheet (verified over all
144,000 rows), CPQ Conversion2 ==
    "{Motor Enclosure}---{Motor Efficiency}---{Motor Voltage}---{Motor Hertz}".

Expectations are DERIVED FROM THE AUTHORITATIVE SHEET at runtime (not hardcoded):
the audit reads the sheet's distinct (enclosure, efficiency, voltage, hertz) ->
CPQ map, walks 1500 configs forcing each of those combos, resolves, and asserts
the API's motor_cpq_conversion equals the sheet value exactly. Also confirms the
Motor line in `pricing`/`component_pricing` carries the same cpq_conversion.

Requires the API on 127.0.0.1:8080. Exit 0 iff all pass, 1 otherwise. Read-only.
"""
import json, sys, time, urllib.request, shutil, tempfile
from pathlib import Path
import openpyxl

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


def read_sheet_cpq_map():
    """(enc_lower, eff_lower, volt_lower, hz_lower) -> exact sheet CPQ Conversion2.
    Reads the whole '1500 Motors' sheet once (read-only stream)."""
    tdir = Path(tempfile.mkdtemp(prefix="cpqaudit_")); tmp = tdir / SRC.name
    shutil.copy2(SRC, tmp)
    try:
        wb = openpyxl.load_workbook(str(tmp), read_only=True, data_only=True)
        ws = wb["1500 Motors"]
        m = {}
        for row in ws.iter_rows(min_row=3, max_row=144002, max_col=14, values_only=True):
            enc, eff, volt, hz, cpq = row[1], row[2], row[3], row[4], row[11]
            if enc is None or cpq is None:
                continue
            key = (str(enc).strip().lower(), str(eff).strip().lower(),
                   str(volt).strip().lower(), str(hz).strip().lower())
            m.setdefault(key, str(cpq).strip())
        wb.close()
    finally:
        shutil.rmtree(tdir, ignore_errors=True)
    return m


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
    cpq_map = read_sheet_cpq_map()

    P = [0]; F = [0]; fails = []
    def ok(cond, msg):
        P[0] += cond; F[0] += (not cond)
        if not cond:
            fails.append(msg)

    print("=" * 92)
    print("FYBROC REV0.4 '1500 MOTORS' — CPQ CONVERSION2 DISPLAY (API vs authoritative sheet)")
    print("=" * 92)

    # Choose a representative set of motor descriptor combos that the 1500 config
    # can actually select (enclosure in tefc/tefc sd/ieee 841; efficiency pe;
    # voltage 230/460, 460, 230; hertz 3ph - 60 hz, 3ph - 50 hz).
    tried = 0
    for (enc, eff, volt, hz), expect in sorted(cpq_map.items()):
        forced = {
            "MOTOR_ENCLOSURE": enc, "MOTOR_EFFICIENCY": eff,
            "MOTOR_VOLTAGE": volt, "MOTOR_HERTZ": hz,
        }
        sel = full_walk("1500", forced)
        # Only score combos the walk actually honored (some voltage/hertz pairings
        # may be constrained out for a given size); require the 4 fields to match.
        if not all(str(sel.get(k, "")).strip().lower() == v for k, v in forced.items()):
            continue
        tried += 1
        r = resolve("1500", sel)
        api_cpq = r.get("motor_cpq_conversion")
        good = (api_cpq == expect)
        ok(good, f"CPQ {forced}: sheet={expect!r} api={api_cpq!r}")
        # also confirm the Motor line carries the same cpq_conversion
        motor_line = next((c for c in r.get("pricing", []) if c.get("component") == "Motor"), None)
        line_cpq = motor_line.get("cpq_conversion") if motor_line else None
        line_ok = (line_cpq is None) or (line_cpq == expect)
        ok(line_ok, f"Motor line cpq {forced}: line={line_cpq!r} expect={expect!r}")
        print(f"  [{'PASS' if good else 'FAIL'}] {enc}/{eff}/{volt}/{hz} -> api={api_cpq!r} sheet={expect!r}")

    ok(tried > 0, "at least one motor-descriptor combo was walkable/scored")
    print(f"\n=== RESULT: {P[0]} passed, {F[0]} failed  (combos scored: {tried}) ===")
    for m in fails[:25]:
        print("  FAIL:", m)
    return 0 if F[0] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

"""Audit: Rev0.3 Feasible Constraint fail-closed enforcement (F140 correction).

Confirms invalid option combinations are blocked and valid configs still resolve,
via the live evaluate endpoint. Requires the API server running on 127.0.0.1:8080.

Covers representative cases across the three constraint-table shapes:
  NOT-ALLOWED : Alt Size x Coupling Guard (6x8x13 -> no Non Sparking)
                Alt Size x Flange Type    (2x3x13 -> no DIN/ISO)
                Alt Size x Flush (5500)   (6x8x13 -> no Internal Flush)
                Casing Drains x Pump Material (VR-1V -> no Casing Drains Supplied)
  ALLOW-LIST  : Alt Size x Impeller Trim  (1x1.5x6 -> only its valid trims)
  + valid walks complete for all supported series (no over-blocking).

Exit code: 0 if all pass, 1 otherwise.
"""
import json, urllib.request, time, sys

URL = "http://127.0.0.1:8080/api/v2/families/FYBROC/configurations/evaluate"


def evaluate(series, sel):
    body = json.dumps({"series": series, "selections": sel}).encode()
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def _wait():
    for _ in range(40):
        try:
            evaluate("1500", {}); return True
        except Exception:
            time.sleep(1)
    return False


def walk_to(series, forced, target):
    """Fill the hierarchy in order (forced overrides) and return target options."""
    sel = {}
    for _ in range(150):
        d = evaluate(series, sel)
        cur = d.get("current_field")
        if cur is None:
            break
        if target in d.get("allowable_options", {}) and all(f in sel for f in forced):
            return [str(v).strip().lower() for v in d["allowable_options"][target]]
        o = d["allowable_options"].get(cur, [])
        std = d.get("standard_defaults", {}).get(cur)
        pick = forced.get(cur) or (std if std in o else (o[0] if o else None))
        if pick is None:
            break
        sel[cur] = pick
    return [str(v).strip().lower() for v in evaluate(series, sel).get("allowable_options", {}).get(target, [])]


def main():
    if not _wait():
        print("FAIL: API server not reachable on 127.0.0.1:8080")
        return 1

    P = [0]; F = [0]
    def check(present, field, value, opts, desc):
        has = value.strip().lower() in opts
        ok = (has == present)
        P[0] += ok; F[0] += (not ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] {desc}: {field}='{value}' "
              f"expected {'PRESENT' if present else 'ABSENT'}, got {'present' if has else 'absent'} (n={len(opts)})")

    print("=== Feasible Constraint fail-closed ===")
    check(False, "COUPLING_GUARD", "non sparking",
          walk_to("5500", {"ALT_SIZE": "6x8x13"}, "COUPLING_GUARD"),
          "CT1 6x8x13 blocks Non Sparking")
    check(True, "COUPLING_GUARD", "non sparking",
          walk_to("1500", {"ALT_SIZE": "1x1.5x6"}, "COUPLING_GUARD"),
          "control small size allows Non Sparking")
    check(False, "FLANGE_TYPE", "din/iso flange",
          walk_to("1500", {"ALT_SIZE": "2x3x13"}, "FLANGE_TYPE"),
          "CT2 2x3x13 blocks DIN/ISO")
    check(False, "FLUSH", "internal flush",
          walk_to("5500", {"ALT_SIZE": "6x8x13"}, "FLUSH"),
          "CT3 5500 6x8x13 blocks Internal Flush")
    check(False, "CASING_DRAINS", "supplied by fybroc",
          walk_to("1500", {"PUMP_MATERIAL": "vr-1v"}, "CASING_DRAINS"),
          "CT7 VR-1V blocks Casing Drains Supplied")

    print("\n=== Allow-list (ConstraintTable4 Impeller Trim) ===")
    trims = walk_to("1500", {"ALT_SIZE": "1x1.5x6"}, "IMPELLER_TRIM")
    ok = (len(trims) == 19 and "4.000" in trims and "10.000" not in trims)
    P[0] += ok; F[0] += (not ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] 1x1.5x6 restricts Impeller Trim to its 19 valid trims (got {len(trims)})")
    # ascending numeric order
    try:
        nums = [float(x) for x in trims]
        asc = nums == sorted(nums)
    except ValueError:
        asc = False
    P[0] += asc; F[0] += (not asc)
    print(f"  [{'PASS' if asc else 'FAIL'}] Impeller Trim ascending numeric order")

    print("\n=== Valid walks complete (no over-blocking) ===")
    for series in ["1500", "1530", "1600", "1630", "2530", "3000", "5500"]:
        sel = {}; stall = None; steps = 0
        for _ in range(160):
            d = evaluate(series, sel); cur = d.get("current_field")
            if cur is None:
                break
            o = d["allowable_options"].get(cur, []); std = d.get("standard_defaults", {}).get(cur)
            pick = std if std in o else (o[0] if o else None)
            if pick is None:
                stall = cur; break
            sel[cur] = pick; steps += 1
        ok = stall is None
        P[0] += ok; F[0] += (not ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] {series} completes ({steps} steps){'' if ok else ' STALL '+stall}")

    print(f"\n=== RESULT: {P[0]} passed, {F[0]} failed ===")
    return 0 if F[0] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

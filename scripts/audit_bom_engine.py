"""Audit: U130 Reusable BOM Engine.

For a representative matrix of full configurations, resolves each via the API and
asserts the BOM engine invariants (grounded, deterministic, reusable identity):

  - a BOM is generated (non-empty: >= the structural lines)
  - bom_parity_ok is True (Python-computed BOM signature == SQL's)
  - deterministic: a second identical resolve returns the SAME bom_signature
  - reuse: the second resolve reports existing_bom = True (no duplicate BOM)
  - BOM <-> PN is 1:1 across the matrix: no PN maps to >1 BOM signature and no
    BOM signature maps to >1 PN  (this is the "same BOM = same PN" invariant)

Requires the API server on 127.0.0.1:8080. Exit code 0 if all pass, 1 otherwise.
"""
import json, urllib.request, urllib.error, time, sys

BASE = "http://127.0.0.1:8080/api/v2/families/FYBROC"

CASES = ["1500", "1530", "1600", "2530", "3000", "5500"]


def post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def _wait():
    for _ in range(40):
        try:
            post("/configurations/evaluate", {"series": "1500", "selections": {}}); return True
        except Exception:
            time.sleep(1)
    return False


def build_full_config(series):
    sel = {}
    for _ in range(160):
        d = post("/configurations/evaluate", {"series": series, "selections": sel})
        cur = d.get("current_field")
        if cur is None:
            break
        o = d["allowable_options"].get(cur, [])
        std = d.get("standard_defaults", {}).get(cur)
        pick = std if std in o else (o[0] if o else None)
        if pick is None:
            break
        sel[cur] = pick
    return sel


def main():
    if not _wait():
        print("FAIL: API server not reachable on 127.0.0.1:8080")
        return 1

    P = [0]; F = [0]
    def ok(cond, msg):
        P[0] += cond; F[0] += (not cond)
        print(f"  [{'PASS' if cond else 'FAIL'}] {msg}")

    pn_to_sigs, sig_to_pns = {}, {}
    print("=== U130 BOM engine ===")
    for series in CASES:
        sel = build_full_config(series)
        payload = {"series": series, "selections": {"SERIES": series, **sel},
                   "segment_codes": {}, "requested_by": "audit_bom_engine"}
        try:
            r1 = post("/configured-products/resolve", payload)
            r2 = post("/configured-products/resolve", payload)
        except urllib.error.HTTPError as e:
            ok(False, f"{series}: resolve HTTP {e.code}")
            continue

        pn = r1.get("part_number")
        b1 = r1.get("bom"); b2 = r2.get("bom")
        ok(bool(b1), f"{series}: BOM present in response")
        if not b1:
            continue
        sig = b1.get("bom_signature") or ""
        ok(b1.get("line_count", 0) >= 6, f"{series}: BOM has structural lines (line_count={b1.get('line_count')})")
        ok(len(sig) == 64, f"{series}: BOM signature is 64-hex")
        ok(b1.get("bom_parity_ok") is True, f"{series}: bom_parity_ok=True (python==sql BOM signature)")
        ok(bool(b2) and b2.get("bom_signature") == sig,
           f"{series}: deterministic (2nd resolve same BOM signature)")
        ok(bool(b2) and b2.get("existing_bom") is True,
           f"{series}: BOM reused on 2nd resolve (existing_bom=True)")
        pn_to_sigs.setdefault(pn, set()).add(sig)
        sig_to_pns.setdefault(sig, set()).add(pn)

    # same BOM = same PN : 1:1 both directions.
    ok(all(len(s) == 1 for s in pn_to_sigs.values()),
       f"no PN maps to >1 BOM signature ({sum(len(s) > 1 for s in pn_to_sigs.values())} violations)")
    ok(all(len(p) == 1 for p in sig_to_pns.values()),
       f"no BOM signature maps to >1 PN ({sum(len(p) > 1 for p in sig_to_pns.values())} violations)")

    print(f"\n=== RESULT: {P[0]} passed, {F[0]} failed ===")
    return 0 if F[0] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

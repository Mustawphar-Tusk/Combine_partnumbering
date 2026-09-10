"""Audit: F150 SQL Identifier Authority parity (Option B).

For a representative matrix of full configurations, resolves each via the API
and asserts:
  - identity_authority == 'sql'            (SQL owns identity, not Python)
  - parity_ok == True                      (Python assembly == SQL assembly)
  - part_number and sku are non-empty
  - configuration_signature is a 64-char hex SHA-256
  - reuse works: a second identical resolve returns existing_configuration=True
    with the SAME part_number / sku / signature (deterministic + persisted)

Requires the API server on 127.0.0.1:8080. Exit code 0 if all pass, 1 otherwise.
"""
import json, urllib.request, urllib.error, time, sys, re, hashlib

BASE = "http://127.0.0.1:8080/api/v2/families/FYBROC"
HEX64 = re.compile(r"^[0-9A-Fa-f]{64}$")

# Representative configs: horizontal + vertical series, varied size/material.
CASES = [
    ("1500", {}),
    ("1530", {}),
    ("1600", {}),
    ("2530", {}),
    ("3000", {}),
    ("5500", {}),
]


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
    """Walk the hierarchy picking STD/first option to produce a complete config."""
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

    pn_sku_pairs = []
    print("=== F150 identifier-authority parity ===")
    for series, extra in CASES:
        sel = build_full_config(series)
        sel.update(extra)
        payload = {"series": series, "selections": {"SERIES": series, **sel},
                   "segment_codes": {}, "requested_by": "audit_identifier_parity"}
        try:
            r1 = post("/configured-products/resolve", payload)
        except urllib.error.HTTPError as e:
            ok(False, f"{series}: resolve HTTP {e.code} {e.read().decode()[:120]}")
            continue

        pn = r1.get("part_number"); sku = r1.get("sku")
        sig = r1.get("configuration_signature") or ""
        ok(r1.get("identity_authority") == "sql", f"{series}: identity_authority=sql (got {r1.get('identity_authority')})")
        ok(r1.get("parity_ok") is True, f"{series}: parity_ok=True (python==sql PN)")
        ok(bool(pn) and "?" not in pn, f"{series}: part_number present + no '?' ({pn})")
        ok(bool(sku), f"{series}: sku present ({sku})")
        ok(bool(HEX64.match(sig)), f"{series}: signature is 64-hex")
        # SKU is derived from the PN (SKU<->PN 1:1): token = first 8 hex of SHA-256(PN).
        expected_token = hashlib.sha256(pn.encode()).hexdigest().upper()[:8] if pn else ""
        ok(r1.get("sku_pn_ok") is True and expected_token in (sku or ""),
           f"{series}: SKU derived from PN (token {expected_token} in {sku})")
        pn_sku_pairs.append((pn, sku))

        # reuse
        try:
            r2 = post("/configured-products/resolve", payload)
            reuse_ok = (r2.get("existing_configuration") is True
                        and r2.get("part_number") == pn
                        and r2.get("sku") == sku
                        and r2.get("configuration_signature") == sig)
            ok(reuse_ok, f"{series}: reuse deterministic (existing=True, same PN/SKU/sig)")
        except urllib.error.HTTPError as e:
            ok(False, f"{series}: reuse resolve HTTP {e.code}")

    # SKU <-> PN must be strictly 1:1 across every resolve this run:
    # no PN with two SKUs, no SKU with two PNs.
    pn_to_skus, sku_to_pns = {}, {}
    for pn, sku in pn_sku_pairs:
        pn_to_skus.setdefault(pn, set()).add(sku)
        sku_to_pns.setdefault(sku, set()).add(pn)
    ok(all(len(s) == 1 for s in pn_to_skus.values()),
       f"no PN maps to >1 SKU ({sum(len(s) > 1 for s in pn_to_skus.values())} violations)")
    ok(all(len(p) == 1 for p in sku_to_pns.values()),
       f"no SKU maps to >1 PN ({sum(len(p) > 1 for p in sku_to_pns.values())} violations)")

    print(f"\n=== RESULT: {P[0]} passed, {F[0]} failed ===")
    return 0 if F[0] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

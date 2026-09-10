"""Audit: U140 Quote Engine.

Creates a quote, adds lines from resolved Fybroc configurations, and asserts the
U140 exit gate: a complete quote is REPRODUCIBLY PERSISTED AND RENDERED.

Per line, the persisted quote must carry: configured product, family, site,
Part Number, SKU, BOM link (signature), quantity, unit price, extended price
(= qty * unit), pricing status, and publication lineage. The rendered document
must be reproducible (same quote -> identical rendered text on re-fetch).

Requires the API server on 127.0.0.1:8080. Exit 0 if all pass, 1 otherwise.
"""
import json, urllib.request, urllib.error, time, sys

BASE = "http://127.0.0.1:8080/api/v2/families/FYBROC"

CASES = ["1500", "1530", "5500"]  # horizontal + vertical representatives


def post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=90) as r:
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

    print("=== U140 quote engine ===")

    # 1) Create a quote.
    try:
        q = post("/quotes", {"site_code": "TEL", "customer_name": "Audit Co",
                             "created_by": "audit_quote_engine"})
    except urllib.error.HTTPError as e:
        print(f"FAIL: create quote HTTP {e.code}: {e.read().decode()[:160]}")
        return 1
    qid = q.get("quote_header_id")
    ok(bool(qid), f"quote created ({q.get('quote_number')})")
    ok(q.get("site_code") == "TEL", "quote site persisted (TEL)")

    # 2) Add a line per representative config.
    expected_lines = 0
    for series in CASES:
        sel = build_full_config(series)
        try:
            line = post(f"/quotes/{qid}/lines",
                        {"series": series, "selections": {"SERIES": series, **sel},
                         "quantity": 2, "requested_by": "audit_quote_engine"})
        except urllib.error.HTTPError as e:
            ok(False, f"{series}: add line HTTP {e.code}: {e.read().decode()[:160]}")
            continue
        expected_lines += 1
        pn = line.get("part_number"); sku = line.get("sku")
        ok(bool(pn) and "?" not in pn, f"{series}: line PN present ({pn})")
        ok(bool(sku), f"{series}: line SKU present ({sku})")
        ok(bool(line.get("bom_signature")), f"{series}: line linked to a BOM (signature present)")
        up = float(line.get("unit_price") or 0.0); ep = float(line.get("extended_price") or 0.0)
        ok(abs(ep - up * 2) < 0.005, f"{series}: extended = qty*unit ({ep} == {up}*2)")
        ok(line.get("pricing_status") in ("found", "partial", "call_for_price"),
           f"{series}: honest pricing status ({line.get('pricing_status')})")

    # 3) Fetch + render, and assert completeness + reproducibility.
    try:
        doc1 = get(f"/quotes/{qid}")
        doc2 = get(f"/quotes/{qid}")
    except urllib.error.HTTPError as e:
        ok(False, f"get quote HTTP {e.code}"); print(f"\n=== RESULT: {P[0]} passed, {F[0]} failed ==="); return 1

    ok(doc1.get("line_count") == expected_lines,
       f"quote has all lines ({doc1.get('line_count')} == {expected_lines})")
    ok(bool(doc1.get("rendered_text")), "quote renders (rendered_text present)")
    # every line persisted the required fields
    fields_ok = all(
        l.get("part_number") and l.get("sku") and l.get("bom_signature")
        and l.get("publication_version") is not None
        and l.get("quantity") and l.get("unit_price") is not None
        and l.get("extended_price") is not None and l.get("pricing_status")
        for l in doc1.get("lines", [])
    )
    ok(fields_ok, "every line persisted PN/SKU/BOM/qty/price/status/publication lineage")
    # total = sum of extended
    total = sum(float(l.get("extended_price") or 0) for l in doc1.get("lines", []))
    ok(abs(total - float(doc1.get("total_price") or 0)) < 0.005, "quote total = sum of extended prices")
    # reproducible render
    ok(doc1.get("rendered_text") == doc2.get("rendered_text"),
       "rendered document is reproducible (identical on re-fetch)")

    print(f"\n=== RESULT: {P[0]} passed, {F[0]} failed ===")
    if F[0] == 0 and doc1.get("rendered_text"):
        print("\n--- sample rendered quote ---")
        print(doc1["rendered_text"])
    return 0 if F[0] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

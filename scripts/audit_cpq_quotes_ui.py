"""Phase C (CPQ Quotes UI) milestone audit.

Verifies the Quotes-page backing: the NEW list endpoint
GET /api/v2/families/{family}/quotes and its correctness against the
authoritative per-quote document (GET .../quotes/{id}), plus a full
create -> add-line (both families) -> list -> open round-trip.

Exit gate (all must pass):
  1. Create a quote (site persisted).
  2. Add a Fybroc line AND a Dean line from fully-resolved STD configs; each
     line persists PN/SKU/qty/extended=qty*unit/honest status.
  3. The list endpoint returns the quote with line_count == 2 and
     total_price == sum of the two lines' extended prices (== get-quote total).
  4. The list endpoint's (count, total) for the quote EXACTLY matches the
     authoritative get-quote document for that quote.
  5. Round-trip: the created quote appears in the list.

Requires the API on 127.0.0.1:8080. Exit 0 if all pass, 1 otherwise.
"""
import json
import sys
import time
import urllib.error
import urllib.request

API = "http://127.0.0.1:8080/api/v2"


def _req(method, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


def _wait():
    for _ in range(40):
        try:
            _req("POST", "/families/FYBROC/configurations/resolve-state",
                 {"series": "1500", "selections": {}})
            return True
        except Exception:
            time.sleep(1)
    return False


def std_selections(family, series):
    """Resolve-state once, then echo its STD-seeded selections back (the state
    the UI holds) so the add-line resolve has a complete config."""
    r = _req("POST", f"/families/{family}/configurations/resolve-state",
             {"series": series, "selections": {}})
    return r.get("selections", {})


def main():
    if not _wait():
        print("FAIL: API not reachable on 127.0.0.1:8080")
        return 1

    P = [0]
    F = [0]

    def ok(cond, msg):
        P[0] += bool(cond)
        F[0] += (not cond)
        print(f"  [{'PASS' if cond else 'FAIL'}] {msg}")

    print("=== Phase C: CPQ Quotes UI audit ===")

    # 1) Create a quote.
    q = _req("POST", "/families/DEAN/quotes",
             {"site_code": "TEL", "customer_name": "Phase C Audit",
              "customer_account": "PCQ-1", "created_by": "audit_cpq_quotes_ui"})
    qid = q.get("quote_header_id")
    ok(bool(qid), f"quote created ({q.get('quote_number')})")
    ok(q.get("site_code") == "TEL", "quote site persisted (TEL)")

    # 2) Add a Fybroc line AND a Dean line.
    cases = [("FYBROC", "1500"), ("DEAN", "Deanline")]
    expected_total = 0.0
    added = 0
    for fam, series in cases:
        sel = std_selections(fam, series)
        try:
            line = _req("POST", f"/families/{fam}/quotes/{qid}/lines",
                        {"series": series, "selections": {"SERIES": series, **sel},
                         "quantity": 2, "requested_by": "audit_cpq_quotes_ui"})
        except urllib.error.HTTPError as e:
            ok(False, f"{fam} {series}: add line HTTP {e.code}: {e.read().decode()[:160]}")
            continue
        up = float(line.get("unit_price") or 0.0)
        ep = float(line.get("extended_price") or 0.0)
        ok(bool(line.get("part_number")), f"{fam} {series}: line PN present ({line.get('part_number')})")
        ok(bool(line.get("sku")), f"{fam} {series}: line SKU present")
        ok(abs(ep - up * 2) < 0.005, f"{fam} {series}: extended == qty*unit ({ep} == {up}*2)")
        ok(line.get("pricing_status") in ("found", "partial", "call_for_price"),
           f"{fam} {series}: honest pricing status ({line.get('pricing_status')})")
        expected_total += ep
        added += 1

    # 3+4) List endpoint: find our quote; assert count + total match get-quote.
    lst = _req("GET", "/families/DEAN/quotes")
    quotes = lst.get("quotes", [])
    ours = next((x for x in quotes if x.get("quote_header_id") == qid), None)
    ok(ours is not None, "created quote appears in the list endpoint")

    doc = _req("GET", f"/families/DEAN/quotes/{qid}")
    if ours is not None:
        ok(ours.get("line_count") == added,
           f"list line_count == lines added ({ours.get('line_count')} == {added})")
        ok(abs(float(ours.get("total_price") or 0) - expected_total) < 0.005,
           f"list total == sum of extended prices ({ours.get('total_price')} == {expected_total})")
        ok(abs(float(ours.get("total_price") or 0) - float(doc.get("total_price") or 0)) < 0.005,
           f"list total == get-quote total ({ours.get('total_price')} == {doc.get('total_price')})")
        ok(ours.get("line_count") == doc.get("line_count"),
           f"list line_count == get-quote line_count ({ours.get('line_count')} == {doc.get('line_count')})")

    # 5) The list `count` is consistent (>= the quotes returned, and our quote in it).
    ok(lst.get("count") == len(quotes), f"list count matches returned rows ({lst.get('count')})")

    print(f"\n=== RESULT: {P[0]} passed, {F[0]} failed ===")
    return 0 if F[0] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

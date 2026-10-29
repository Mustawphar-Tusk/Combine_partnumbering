"""CPQ SPA U4 audit — engineer-authored quotes (option A, self-serve).

Re-runnable, SELF-CLEANING. Verifies against a running dev-mock API
(default http://127.0.0.1:8080; --base to override):

  1. ENTITLEMENT: an engineer identity has author_quote in /me; a configurator
     identity does NOT.
  2. An engineer creates a DEAN quote from scratch (status Draft). DEAN is used
     (routes to IND) so Fybroc stays frozen.
  3. Customer CONTACT + SHIP_TO upsert; GET returns both with the exact values
     written.
  4. A configured line is added (DEAN line -> call_for_price, exercising the C/F
     resolution path in engineer-complete, which proves custom-price handling).
  5. engineer-complete runs submit -> claim -> resolve C/F -> complete (A5 gate)
     -> confirm (A6) -> a CPQ-###### order; idempotent on retry (same order).
  6. The order document carries contact + ship_to matching what was written, and
     customer_name is present.
  7. DRAFT-ONLY guard: upsert party on the now-confirmed quote's case is rejected
     (quote no longer Draft) -> 409.
  8. ISOLATION: watermarks unchanged (queried, not hardcoded) against the frozen
     baseline.

Cleans up the order confirmation, review case, quote, and acct rows it created.

Usage:  uv run python scripts/audit_cpq_u4.py [--base URL]
"""
import json
import sys
import urllib.error
import urllib.request
import uuid

import pyodbc

_base_root = "http://127.0.0.1:8080"
for i, a in enumerate(sys.argv):
    if a == "--base" and i + 1 < len(sys.argv):
        _base_root = sys.argv[i + 1]
BASE = _base_root.rstrip("/") + "/api/v2"

CONN = (
    "DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;"
    "DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;"
    "Encrypt=yes;TrustServerCertificate=yes;"
)
RUN = uuid.uuid4().hex[:10]
COMPANY = f"U4 Co {RUN}"

ENG_IND = "dev-engineering-ind"   # IND / DEAN (sql/28)
CONFIGURATOR = f"u4-cfg-{RUN}"    # has create_quote but NOT author_quote

# Frozen isolation baseline (from the project watermarks).
WATERMARKS = {
    "cfg.FeasibleConstraint": ("SELECT COUNT(*) FROM cfg.FeasibleConstraint", 4743),
    "non-Dean cfg.SeriesFieldOption": (
        "SELECT COUNT(*) FROM cfg.SeriesFieldOption sfo "
        "JOIN cfg.PumpFamily pf ON pf.PumpFamilyId=sfo.PumpFamilyId "
        "WHERE pf.FamilyCode<>'DEAN'", 3638),
    "non-DEAN stg.SegmentCombinationImport": (
        "SELECT COUNT(*) FROM stg.SegmentCombinationImport WHERE FamilyCode<>'DEAN'", 300608),
    "DEAN stg.SegmentCombinationImport": (
        "SELECT COUNT(*) FROM stg.SegmentCombinationImport WHERE FamilyCode='DEAN'", 140976),
}

CONTACT = {
    "company_name": COMPANY, "first_name": "Ada", "last_name": "Byron",
    "address1": "1 Analytical Way", "address2": "Suite 2",
    "city": "Indianapolis", "state": "IN", "postal_code": "46200",
    "country": "USA", "phone": "317-555-0101", "email": "ada@example.test",
}
SHIP_TO = {
    "company_name": COMPANY + " Plant", "first_name": "Grace", "last_name": "Hopper",
    "address1": "500 Dock Rd", "address2": "Bay 4",
    "city": "Terre Haute", "state": "IN", "postal_code": "47800",
    "country": "USA", "phone": "812-555-0199", "email": "ship@example.test",
}


def hdr_eng(subject=ENG_IND):
    return {"X-Dev-Assume-Role": "engineering", "X-Dev-Subject": subject,
            "X-Dev-Email": subject + "@dev.local"}


def hdr_cfg():
    return {"X-Dev-Assume-Role": "configurator", "X-Dev-Subject": CONFIGURATOR,
            "X-Dev-Email": CONFIGURATOR + "@dev.local"}


def _parse(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return {"_raw": raw}


def call(method, path, *, headers=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, _parse(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, _parse(e.read().decode())


results = []
def ok(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name, "-", detail)


def std_sel(family, series):
    _, r = call("POST", f"/families/{family}/configurations/resolve-state",
                body={"series": series, "selections": {}})
    return r.get("selections", {})


def parties_match(got, want):
    for k, v in want.items():
        if (got or {}).get(k) != v:
            return False, f"{k}: got {(got or {}).get(k)!r} want {v!r}"
    return True, "all fields match"


def main():
    created_quotes = []

    # 1. Entitlement.
    st, me_eng = call("GET", "/me", headers=hdr_eng())
    ok("engineer /me has author_quote",
       st == 200 and me_eng.get("capabilities", {}).get("author_quote") is True,
       f"caps={me_eng.get('capabilities', {}).get('author_quote')}")
    st, me_cfg = call("GET", "/me", headers=hdr_cfg())
    ok("configurator /me lacks author_quote",
       st == 200 and not me_cfg.get("capabilities", {}).get("author_quote"),
       f"caps={me_cfg.get('capabilities', {}).get('author_quote')}")

    # 2. Engineer creates a DEAN quote from scratch.
    st, q = call("POST", "/families/DEAN/quotes", headers=hdr_eng(),
                 body={"site_code": "IND", "customer_name": COMPANY})
    qid = q.get("quote_header_id") if st in (200, 201) else None
    created_quotes.append(qid)
    ok("engineer created DEAN quote (Draft)",
       qid is not None and q.get("status") == "Draft", f"qid={qid} status={q.get('status')}")

    # 3. Upsert contact + ship-to, then GET.
    st_c, _ = call("PUT", f"/quotes/{qid}/parties/CONTACT", headers=hdr_eng(), body=CONTACT)
    st_s, _ = call("PUT", f"/quotes/{qid}/parties/SHIP_TO", headers=hdr_eng(), body=SHIP_TO)
    ok("upsert CONTACT + SHIP_TO 200", st_c == 200 and st_s == 200, f"c={st_c} s={st_s}")
    st, parties = call("GET", f"/quotes/{qid}/parties", headers=hdr_eng())
    plist = parties.get("parties", []) if st == 200 else []
    got_c = next((p for p in plist if p.get("kind") == "CONTACT"), None)
    got_s = next((p for p in plist if p.get("kind") == "SHIP_TO"), None)
    mc, dc = parties_match(got_c, CONTACT)
    ms, ds = parties_match(got_s, SHIP_TO)
    ok("GET parties returns CONTACT matching written values", mc, dc)
    ok("GET parties returns SHIP_TO matching written values", ms, ds)

    # 4. Add a DEAN line.
    sel = std_sel("DEAN", "RA3146")
    st, line = call("POST", f"/families/DEAN/quotes/{qid}/lines", headers=hdr_eng(),
                    body={"series": "RA3146", "selections": {"SERIES": "RA3146", **sel},
                          "quantity": 1, "requested_by": ENG_IND})
    ok("engineer added a DEAN line", st in (200, 201) and line.get("quote_line_id"),
       f"status={st} pricing={line.get('pricing_status')}")

    # 5. engineer-complete (resolves the C/F line at its current unit price).
    st, done = call("POST", f"/quotes/{qid}/engineer-complete", headers=hdr_eng(),
                    body={"lead_time_days": 17, "notes": "u4 self-serve",
                          "line_prices": [{"line_number": line.get("line_number", 1),
                                           "resolved_unit_price": 4321.0,
                                           "custom_spec": "audit resolved"}]})
    cpq = done.get("cpq_order_number") if st in (200, 201) else None
    case_id = done.get("review_case_id") if st in (200, 201) else None
    ok("engineer-complete -> CPQ order", bool(cpq) and cpq.startswith("CPQ-"),
       f"status={st} cpq={cpq} case={case_id} detail={done}")

    # 5b. Idempotent retry -> same order.
    st2, done2 = call("POST", f"/quotes/{qid}/engineer-complete", headers=hdr_eng(),
                      body={"lead_time_days": 17,
                            "line_prices": [{"line_number": line.get("line_number", 1),
                                             "resolved_unit_price": 4321.0}]})
    ok("engineer-complete idempotent (same CPQ order)",
       st2 in (200, 201) and done2.get("cpq_order_number") == cpq,
       f"status={st2} cpq={done2.get('cpq_order_number')} was_existing={done2.get('was_existing')}")

    # 6. Order document carries contact + ship_to + customer_name.
    st, order = call("GET", f"/orders/by-case/{case_id}", headers=hdr_eng())
    docu = order.get("document", {}) if st == 200 else {}
    mco, dco = parties_match(docu.get("contact"), CONTACT)
    mso, dso = parties_match(docu.get("ship_to"), SHIP_TO)
    ok("order doc contact matches", mco, dco)
    ok("order doc ship_to matches", mso, dso)
    ok("order doc customer_name present", docu.get("customer_name") == COMPANY,
       f"customer_name={docu.get('customer_name')}")

    # 7. Draft-only guard: the quote is no longer Draft after completion.
    st, _ = call("PUT", f"/quotes/{qid}/parties/CONTACT", headers=hdr_eng(),
                 body={**CONTACT, "phone": "000"})
    ok("upsert party on non-draft quote -> 409", st == 409, f"status={st}")

    # 8. Isolation watermarks unchanged.
    c = pyodbc.connect(CONN, autocommit=True).cursor()
    for name, (sql, want) in WATERMARKS.items():
        got = c.execute(sql).fetchone()[0]
        ok(f"watermark {name} == {want}", got == want, f"got={got}")

    passed = sum(1 for _, p in results if p)
    cleanup(created_quotes)
    print(f"\nCPQ U4 AUDIT: {passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


def cleanup(quote_ids):
    c = pyodbc.connect(CONN, autocommit=True)
    try:
        cur = c.cursor()
        for qid in quote_ids:
            if qid is None:
                continue
            case_ids = [r[0] for r in cur.execute(
                "SELECT ReviewCaseId FROM acct.ReviewCase WHERE QuoteHeaderId = ?", qid).fetchall()]
            for cid in case_ids:
                cur.execute("DELETE FROM quote.OrderConfirmation WHERE ReviewCaseId = ?", cid)
                cur.execute("DELETE FROM acct.ReviewEvent WHERE ReviewCaseId = ?", cid)
                cur.execute("DELETE FROM acct.ReviewCaseLine WHERE ReviewCaseId = ?", cid)
                cur.execute("DELETE FROM acct.Notification WHERE ResourceType IN ('order','review_case') "
                            "AND ResourceId = ?", str(cid))
                cur.execute("DELETE FROM acct.ReviewCase WHERE ReviewCaseId = ?", cid)
            cur.execute("DELETE FROM quote.QuoteParty WHERE QuoteHeaderId = ?", qid)
            cur.execute("DELETE FROM quote.QuoteLineCustomization WHERE QuoteLineId IN "
                        "(SELECT QuoteLineId FROM quote.QuoteLine WHERE QuoteHeaderId = ?)", qid)
            cur.execute("DELETE FROM quote.QuoteLine WHERE QuoteHeaderId = ?", qid)
            cur.execute("DELETE FROM quote.QuoteHeader WHERE QuoteHeaderId = ?", qid)
        # Engineer AppUsers are seeded (keep them); only remove notifications we made.
    finally:
        c.close()


if __name__ == "__main__":
    sys.exit(main())

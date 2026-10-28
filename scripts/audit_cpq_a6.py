"""CPQ Adjustment A6 audit - Confirm Order + identical doc + retry-safe. Self-cleaning.

  1. Submit Fybroc quote -> TEL engineer claims + completes (lead time).
  2. Distributor confirms order (201) -> CpqOrderNumber minted, was_existing False.
  3. Retry-safe: confirm again -> SAME order number, was_existing True, no duplicate.
  4. Both parties read the SAME document: distributor GET /orders/by-case and the
     responsible TEL engineer GET /orders/by-case return byte-identical document JSON.
  5. Isolation: the IND engineer (wrong site) gets 404 on the order.
"""
import json, sys, urllib.error, urllib.request, uuid
import pyodbc

_base = "http://127.0.0.1:8080"
for i, a in enumerate(sys.argv):
    if a == "--base" and i + 1 < len(sys.argv):
        _base = sys.argv[i + 1]
BASE = _base.rstrip("/") + "/api/v2"
CONN = ("DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;"
        "DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;")
RUN = uuid.uuid4().hex[:10]
DIST = f"a6-dist-{RUN}"
IDEM = f"a6-idem-{RUN}"
COMPANY = f"A6 Co {RUN}"
ENG_IND, ENG_TEL = "dev-engineering-ind", "dev-engineering-tel"


def hdr_dist(sub=DIST):
    return {"X-Dev-Assume-Role": "distributor", "X-Dev-Subject": sub, "X-Dev-Email": sub + "@dev.local"}


def hdr_eng(sub):
    return {"X-Dev-Assume-Role": "engineering", "X-Dev-Subject": sub, "X-Dev-Email": sub + "@dev.local"}


def call(method, path, *, headers=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        return e.code, (json.loads(raw) if raw.strip() else None)


results = []
def ok(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name, "-", detail)


def main():
    call("GET", "/me", headers=hdr_dist())
    _, sub = call("POST", "/distributor/applications", headers=hdr_dist(),
                  body={"idempotency_key": IDEM, "company_name": COMPANY,
                        "contact": {"address1": "1", "city": "X", "postal_code": "1", "country": "USA"},
                        "ship_to": {"address1": "1", "city": "X", "postal_code": "1", "country": "USA"}})
    call("POST", f"/admin/applications/{sub['application_id']}/review",
         body={"outcome": "APPROVED", "loyalty_tier_code": "loyalty15"})

    _, se = call("POST", "/families/FYBROC/configurations/resolve-state",
                 body={"series": "1500", "selections": {}})
    sel = se.get("selections", {})
    _, q = call("POST", "/families/FYBROC/quotes", headers=hdr_dist(),
                body={"site_code": "TEL", "customer_name": COMPANY, "created_by": DIST})
    qid = q["quote_header_id"]
    call("POST", f"/families/FYBROC/quotes/{qid}/lines", headers=hdr_dist(),
         body={"series": "1500", "selections": {"SERIES": "1500", **sel}, "quantity": 2, "requested_by": DIST})
    _, case = call("POST", f"/quotes/{qid}/submit-for-review", headers=hdr_dist())
    cid = case["review_case_id"]
    call("POST", f"/engineering/cases/{cid}/claim", headers=hdr_eng(ENG_TEL))
    call("POST", f"/engineering/cases/{cid}/complete", headers=hdr_eng(ENG_TEL), body={"lead_time_days": 28})

    # Confirm.
    st_c, conf = call("POST", f"/distributor/review-cases/{cid}/confirm-order", headers=hdr_dist())
    ok("confirm order 201", st_c == 201, f"status={st_c}")
    ok("cpq order number minted", bool(conf and conf.get("cpq_order_number")), str(conf and conf.get("cpq_order_number")))
    ok("first confirm not existing", conf and conf.get("was_existing") is False)
    order_no = conf.get("cpq_order_number")

    # Retry-safe.
    st_c2, conf2 = call("POST", f"/distributor/review-cases/{cid}/confirm-order", headers=hdr_dist())
    ok("retry confirm same order number", conf2 and conf2.get("cpq_order_number") == order_no,
       f"{conf2.get('cpq_order_number')}")
    ok("retry flagged existing", conf2 and conf2.get("was_existing") is True)

    # Both parties read the SAME document.
    st_d, dist_doc = call("GET", f"/orders/by-case/{cid}", headers=hdr_dist())
    st_e, eng_doc = call("GET", f"/orders/by-case/{cid}", headers=hdr_eng(ENG_TEL))
    ok("distributor reads order 200", st_d == 200, f"status={st_d}")
    ok("responsible engineer reads order 200", st_e == 200, f"status={st_e}")
    ok("both documents identical",
       dist_doc and eng_doc and json.dumps(dist_doc["document"], sort_keys=True) ==
       json.dumps(eng_doc["document"], sort_keys=True))
    ok("order carries loyalty15 discount",
       dist_doc and dist_doc["document"]["discount_rate_bp"] == 1500,
       f"bp={dist_doc['document']['discount_rate_bp'] if dist_doc else '?'}")
    ok("order carries lead time 28",
       dist_doc and dist_doc["document"]["lead_time_days"] == 28)

    # Wrong-site engineer -> 404.
    st_wrong, _ = call("GET", f"/orders/by-case/{cid}", headers=hdr_eng(ENG_IND))
    ok("wrong-site engineer -> 404", st_wrong == 404, f"status={st_wrong}")

    cleanup([qid])
    passed = sum(1 for _, c in results if c)
    print(f"\nCPQ A6 AUDIT: {passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


def cleanup(qids):
    c = pyodbc.connect(CONN, autocommit=True)
    try:
        cur = c.cursor()
        for qid in qids:
            if qid is None:
                continue
            cur.execute("DELETE FROM quote.OrderConfirmation WHERE QuoteHeaderId = ?", qid)
            cids = [r[0] for r in cur.execute("SELECT ReviewCaseId FROM acct.ReviewCase WHERE QuoteHeaderId = ?", qid).fetchall()]
            for cid in cids:
                cur.execute("DELETE FROM acct.ReviewEvent WHERE ReviewCaseId = ?", cid)
                cur.execute("DELETE FROM acct.ReviewCaseLine WHERE ReviewCaseId = ?", cid)
                cur.execute("DELETE FROM acct.ReviewCase WHERE ReviewCaseId = ?", cid)
            cur.execute("DELETE FROM quote.QuoteLineCustomization WHERE QuoteLineId IN (SELECT QuoteLineId FROM quote.QuoteLine WHERE QuoteHeaderId = ?)", qid)
            cur.execute("DELETE FROM quote.QuoteLine WHERE QuoteHeaderId = ?", qid)
            cur.execute("DELETE FROM quote.QuoteHeader WHERE QuoteHeaderId = ?", qid)
        uids = [r[0] for r in cur.execute("SELECT AppUserId FROM acct.AppUser WHERE IdpSubject = ?", DIST).fetchall()]
        aids = [r[0] for r in cur.execute("SELECT DistributorAccountId FROM acct.DistributorAccount WHERE CompanyName = ?", COMPANY).fetchall()]
        if uids:
            uq = ",".join("?" for _ in uids)
            cur.execute(f"DELETE FROM acct.Notification WHERE RecipientAppUserId IN ({uq})", *uids)
        cur.execute("DELETE FROM acct.Notification WHERE ResourceType IN ('order','review_case') AND ResourceId NOT IN "
                    "(SELECT CAST(ReviewCaseId AS VARCHAR(64)) FROM acct.ReviewCase)")
        if aids:
            aq = ",".join("?" for _ in aids)
            cur.execute(f"DELETE FROM acct.Address WHERE ApplicationId IN (SELECT ApplicationId FROM acct.AccountApplication WHERE DistributorAccountId IN ({aq}))", *aids)
            cur.execute(f"DELETE FROM acct.LoyaltyAssignment WHERE DistributorAccountId IN ({aq})", *aids)
            cur.execute(f"DELETE FROM acct.AccountApplication WHERE DistributorAccountId IN ({aq})", *aids)
            cur.execute(f"DELETE FROM acct.AccountMembership WHERE DistributorAccountId IN ({aq})", *aids)
            cur.execute(f"DELETE FROM acct.DistributorAccount WHERE DistributorAccountId IN ({aq})", *aids)
        if uids:
            uq = ",".join("?" for _ in uids)
            cur.execute(f"DELETE FROM acct.AppUser WHERE AppUserId IN ({uq})", *uids)
    finally:
        c.close()


if __name__ == "__main__":
    sys.exit(main())

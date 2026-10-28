"""CPQ Adjustment A5 audit - completion gate + reviewed-revision return + further review.
Self-cleaning. Uses the seeded dev engineers (sql/28): IND/DEAN, TEL/FYBROC.

  1. Submit a Fybroc quote (priced 'found' line) for review; TEL engineer claims.
  2. Completion GATE: complete with NO lead time -> 409 (lead time required).
  3. Complete with lead time -> 200 (the found line needs no resolved price).
  4. Distributor views the reviewed revision (owner-scoped); non-owner -> 404.
  5. Request Further Review -> case back to CHANGES_REQUESTED, revision bumped,
     engineering re-notified; non-owner cannot.
  6. C/F gate: a Dean (partial) case cannot be completed until the C/F line has a
     resolved price (even with lead time).
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
DIST = f"a5-dist-{RUN}"
IDEM = f"a5-idem-{RUN}"
COMPANY = f"A5 Co {RUN}"
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


def std_sel(family, series):
    _, r = call("POST", f"/families/{family}/configurations/resolve-state",
                body={"series": series, "selections": {}})
    return r.get("selections", {})


def make_case(family, series, site, eng):
    _, q = call("POST", f"/families/{family}/quotes", headers=hdr_dist(),
                body={"site_code": site, "customer_name": COMPANY, "created_by": DIST})
    qid = q["quote_header_id"]
    sel = std_sel(family, series)
    call("POST", f"/families/{family}/quotes/{qid}/lines", headers=hdr_dist(),
         body={"series": series, "selections": {"SERIES": series, **sel}, "quantity": 1, "requested_by": DIST})
    _, case = call("POST", f"/quotes/{qid}/submit-for-review", headers=hdr_dist())
    cid = case["review_case_id"]
    call("POST", f"/engineering/cases/{cid}/claim", headers=hdr_eng(eng))
    return qid, cid


def main():
    # Approve the distributor so it can create quotes.
    call("GET", "/me", headers=hdr_dist())
    _, sub = call("POST", "/distributor/applications", headers=hdr_dist(),
                  body={"idempotency_key": IDEM, "company_name": COMPANY,
                        "contact": {"address1": "1", "city": "X", "postal_code": "1", "country": "USA"},
                        "ship_to": {"address1": "1", "city": "X", "postal_code": "1", "country": "USA"}})
    call("POST", f"/admin/applications/{sub['application_id']}/review",
         body={"outcome": "APPROVED", "loyalty_tier_code": "standard"})

    # Fybroc found-line case, claimed by TEL.
    fq, fcid = make_case("FYBROC", "1500", "TEL", ENG_TEL)

    # 2. Gate: complete without lead time -> 409.
    st_nolt, _ = call("POST", f"/engineering/cases/{fcid}/complete", headers=hdr_eng(ENG_TEL), body={})
    ok("complete without lead time -> 409", st_nolt == 409, f"status={st_nolt}")

    # 3. Complete with lead time -> 200.
    st_c, comp = call("POST", f"/engineering/cases/{fcid}/complete", headers=hdr_eng(ENG_TEL),
                      body={"lead_time_days": 14})
    ok("complete with lead time -> 200", st_c == 200 and comp.get("status") == "COMPLETED",
       f"status={st_c}")

    # 4. Distributor views the reviewed revision; non-owner 404.
    st_v, view = call("GET", f"/distributor/review-cases/{fcid}", headers=hdr_dist())
    ok("owner views reviewed revision", st_v == 200 and view["case"]["Status"] == "COMPLETED",
       f"status={st_v}")
    ok("reviewed revision shows lead time", view and view["case"].get("LeadTimeDays") == 14,
       f"lt={view['case'].get('LeadTimeDays') if view else '?'}")
    st_no, _ = call("GET", f"/distributor/review-cases/{fcid}", headers=hdr_dist("a5-other-" + RUN))
    ok("non-owner cannot view case -> 404", st_no == 404, f"status={st_no}")

    # 5. Request Further Review -> back to CHANGES_REQUESTED, rev bumped.
    st_fr, fr = call("POST", f"/distributor/review-cases/{fcid}/request-further-review",
                     headers=hdr_dist(), body={"notes": "please add witnessed test"})
    ok("request further review -> 200", st_fr == 200, f"status={st_fr}")
    ok("status back to CHANGES_REQUESTED", fr and fr.get("status") == "CHANGES_REQUESTED", str(fr))
    ok("revision bumped to 2", fr and fr.get("revision_no") == 2, f"rev={fr.get('revision_no')}")
    st_nono, _ = call("POST", f"/distributor/review-cases/{fcid}/request-further-review",
                      headers=hdr_dist("a5-other-" + RUN), body={"notes": "x"})
    ok("non-owner cannot request further review -> 404", st_nono == 404, f"status={st_nono}")

    # 6. C/F gate: Dean partial case can't complete until C/F line resolved.
    dq, dcid = make_case("DEAN", "RA3146", "IND", ENG_IND)
    st_cf, _ = call("POST", f"/engineering/cases/{dcid}/complete", headers=hdr_eng(ENG_IND),
                    body={"lead_time_days": 30})
    ok("complete with unresolved C/F line -> 409", st_cf == 409, f"status={st_cf}")
    # Resolve the C/F line, then completion succeeds.
    _, det = call("GET", f"/engineering/cases/{dcid}", headers=hdr_eng(ENG_IND))
    lines = det.get("lines", [])
    for ln in lines:
        if (ln.get("PricingStatus") or "") != "found":
            call("POST", f"/engineering/cases/{dcid}/lines/{ln['ReviewCaseLineId']}/resolve",
                 headers=hdr_eng(ENG_IND), body={"resolved_unit_price": 5000.0, "custom_spec": "resolved"})
    st_ok, _ = call("POST", f"/engineering/cases/{dcid}/complete", headers=hdr_eng(ENG_IND),
                    body={"lead_time_days": 30})
    ok("complete after resolving C/F -> 200", st_ok == 200, f"status={st_ok}")

    cleanup([fq, dq])
    passed = sum(1 for _, c in results if c)
    print(f"\nCPQ A5 AUDIT: {passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


def cleanup(qids):
    c = pyodbc.connect(CONN, autocommit=True)
    try:
        cur = c.cursor()
        for qid in qids:
            if qid is None:
                continue
            cids = [r[0] for r in cur.execute("SELECT ReviewCaseId FROM acct.ReviewCase WHERE QuoteHeaderId = ?", qid).fetchall()]
            for cid in cids:
                cur.execute("DELETE FROM acct.ReviewEvent WHERE ReviewCaseId = ?", cid)
                cur.execute("DELETE FROM acct.ReviewCaseLine WHERE ReviewCaseId = ?", cid)
                cur.execute("DELETE FROM acct.ReviewCase WHERE ReviewCaseId = ?", cid)
            cur.execute("DELETE FROM quote.QuoteLineCustomization WHERE QuoteLineId IN (SELECT QuoteLineId FROM quote.QuoteLine WHERE QuoteHeaderId = ?)", qid)
            cur.execute("DELETE FROM quote.QuoteLine WHERE QuoteHeaderId = ?", qid)
            cur.execute("DELETE FROM quote.QuoteHeader WHERE QuoteHeaderId = ?", qid)
        # acct rows for the run distributor + notifications.
        uids = [r[0] for r in cur.execute("SELECT AppUserId FROM acct.AppUser WHERE IdpSubject LIKE ?", f"a5-%{RUN}%").fetchall()]
        cur.execute("SELECT AppUserId FROM acct.AppUser WHERE IdpSubject = ?", DIST)
        uids += [r[0] for r in cur.fetchall()]
        aids = [r[0] for r in cur.execute("SELECT DistributorAccountId FROM acct.DistributorAccount WHERE CompanyName = ?", COMPANY).fetchall()]
        if uids:
            uq = ",".join("?" for _ in uids)
            cur.execute(f"DELETE FROM acct.Notification WHERE RecipientAppUserId IN ({uq})", *uids)
        cur.execute("DELETE FROM acct.Notification WHERE ResourceType='review_case' AND ResourceId NOT IN (SELECT CAST(ReviewCaseId AS VARCHAR(64)) FROM acct.ReviewCase)")
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

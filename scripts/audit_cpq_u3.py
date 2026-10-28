"""CPQ SPA U3 exit audit - engineering review queue + brand/site isolation.

Re-runnable, SELF-CLEANING. Verifies (handoff §4) against a running dev-mock API
(default http://127.0.0.1:8080; --base to override):

  1. A DEAN quote submitted for review lands in the IND/DEAN queue.
  2. A FYBROC quote submitted for review lands in the TEL/FYBROC queue.
  3. Brand is derived server-side from the persisted quote lines (not a client
     param): the case brand/site matches the ordered brand.
  4. ISOLATION: the IND/DEAN engineer canNOT read/claim the Fybroc case by id
     (404), and the TEL/FYBROC engineer canNOT read the Dean case (404).
  5. Flow: the right engineer claims -> resolves a line -> completes with a lead
     time; the submitting distributor is notified (review_completed).
  6. Admin oversight lists cases across BOTH sites.

Cleans up all review cases/events/lines, quotes, and acct rows it created.

Usage:  uv run python scripts/audit_cpq_u3.py [--base URL]
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
DIST = f"u3-dist-{RUN}"
IDEM = f"u3-idem-{RUN}"
COMPANY = f"U3 Co {RUN}"

# Seeded dev engineer subjects (sql/28): IND/DEAN and TEL/FYBROC.
ENG_IND = "dev-engineering-ind"
ENG_TEL = "dev-engineering-tel"


def hdr_dist():
    return {"X-Dev-Assume-Role": "distributor", "X-Dev-Subject": DIST,
            "X-Dev-Email": DIST + "@dev.local"}


def hdr_eng(subject):
    return {"X-Dev-Assume-Role": "engineering", "X-Dev-Subject": subject,
            "X-Dev-Email": subject + "@dev.local"}


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


def make_quote_with_line(family, series, site):
    _, q = call("POST", f"/families/{family}/quotes", headers=hdr_dist(),
                body={"site_code": site, "customer_name": COMPANY, "created_by": DIST})
    qid = q.get("quote_header_id")
    sel = std_sel(family, series)
    call("POST", f"/families/{family}/quotes/{qid}/lines", headers=hdr_dist(),
         body={"series": series, "selections": {"SERIES": series, **sel},
               "quantity": 1, "requested_by": DIST})
    return qid


def main():
    created_quotes = []

    # Approve the distributor so it can create quotes (configure/create_quote).
    call("GET", "/me", headers=hdr_dist())
    _, sub = call("POST", "/distributor/applications", headers=hdr_dist(),
                  body={"idempotency_key": IDEM, "company_name": COMPANY,
                        "contact": {"address1": "1 A St", "city": "X", "postal_code": "1", "country": "USA"},
                        "ship_to": {"address1": "1 A St", "city": "X", "postal_code": "1", "country": "USA"}})
    app_id = sub.get("application_id")
    call("POST", f"/admin/applications/{app_id}/review",
         body={"outcome": "APPROVED", "loyalty_tier_code": "standard"})

    # DEAN quote + FYBROC quote.
    dean_q = make_quote_with_line("DEAN", "RA3146", "IND")
    fyb_q = make_quote_with_line("FYBROC", "1500", "TEL")
    created_quotes += [dean_q, fyb_q]
    ok("dean quote created", dean_q is not None, f"qid={dean_q}")
    ok("fybroc quote created", fyb_q is not None, f"qid={fyb_q}")

    # Submit both for review.
    st, dcase = call("POST", f"/quotes/{dean_q}/submit-for-review", headers=hdr_dist())
    ok("dean submit 201", st == 201, f"status={st}")
    ok("dean routed to IND/DEAN",
       dcase.get("brand") == "DEAN" and dcase.get("responsible_site_code") == "IND",
       f"brand={dcase.get('brand')} site={dcase.get('responsible_site_code')}")
    dean_case_id = dcase.get("review_case_id")

    st, fcase = call("POST", f"/quotes/{fyb_q}/submit-for-review", headers=hdr_dist())
    ok("fybroc submit 201", st == 201, f"status={st}")
    ok("fybroc routed to TEL/FYBROC",
       fcase.get("brand") == "FYBROC" and fcase.get("responsible_site_code") == "TEL",
       f"brand={fcase.get('brand')} site={fcase.get('responsible_site_code')}")
    fyb_case_id = fcase.get("review_case_id")

    # Each engineer sees only their own queue.
    st, ind_list = call("GET", "/engineering/cases", headers=hdr_eng(ENG_IND))
    ind_ids = [c["ReviewCaseId"] for c in ind_list.get("cases", [])]
    ok("IND engineer sees dean case", dean_case_id in ind_ids)
    ok("IND engineer does NOT see fybroc case", fyb_case_id not in ind_ids)
    ok("IND authorized sites = [IND]", ind_list.get("authorized_sites") == ["IND"],
       str(ind_list.get("authorized_sites")))

    st, tel_list = call("GET", "/engineering/cases", headers=hdr_eng(ENG_TEL))
    tel_ids = [c["ReviewCaseId"] for c in tel_list.get("cases", [])]
    ok("TEL engineer sees fybroc case", fyb_case_id in tel_ids)
    ok("TEL engineer does NOT see dean case", dean_case_id not in tel_ids)

    # ISOLATION by direct id: cross-team reads -> 404.
    st, _ = call("GET", f"/engineering/cases/{fyb_case_id}", headers=hdr_eng(ENG_IND))
    ok("IND engineer GET fybroc case -> 404", st == 404, f"status={st}")
    st, _ = call("GET", f"/engineering/cases/{dean_case_id}", headers=hdr_eng(ENG_TEL))
    ok("TEL engineer GET dean case -> 404", st == 404, f"status={st}")

    # ISOLATION on claim: IND cannot claim fybroc case.
    st, _ = call("POST", f"/engineering/cases/{fyb_case_id}/claim", headers=hdr_eng(ENG_IND))
    ok("IND engineer claim fybroc -> 404", st == 404, f"status={st}")

    # Flow: TEL engineer claims the fybroc case, resolves a line, completes.
    st, _ = call("POST", f"/engineering/cases/{fyb_case_id}/claim", headers=hdr_eng(ENG_TEL))
    ok("TEL claim fybroc 200", st == 200, f"status={st}")
    st, detail = call("GET", f"/engineering/cases/{fyb_case_id}", headers=hdr_eng(ENG_TEL))
    lines = detail.get("lines", [])
    ok("fybroc case has line(s)", len(lines) >= 1, f"n={len(lines)}")
    if lines:
        lid = lines[0]["ReviewCaseLineId"]
        st, _ = call("POST", f"/engineering/cases/{fyb_case_id}/lines/{lid}/resolve",
                     headers=hdr_eng(ENG_TEL),
                     body={"resolved_unit_price": 1234.56, "custom_spec": "audit spec",
                           "engineer_note": "ok"})
        ok("TEL resolve line 200", st == 200, f"status={st}")
    st, comp = call("POST", f"/engineering/cases/{fyb_case_id}/complete",
                    headers=hdr_eng(ENG_TEL), body={"lead_time_days": 21, "notes": "done"})
    ok("TEL complete 200 + lead time", st == 200 and comp.get("lead_time_days") == 21,
       f"status={st} lt={comp.get('lead_time_days')}")

    # Distributor notified of completion.
    st, notifs = call("GET", "/notifications", headers=hdr_dist())
    evs = [n.get("EventType") for n in notifs.get("notifications", [])]
    ok("distributor notified review_completed", "review_completed" in evs, str(evs))

    # Admin oversight sees both.
    st, admin_list = call("GET", "/admin/engineering/cases")
    aids = [c["ReviewCaseId"] for c in admin_list.get("cases", [])]
    ok("admin oversight sees both cases", dean_case_id in aids and fyb_case_id in aids)

    cleanup(created_quotes)
    passed = sum(1 for _, c in results if c)
    print(f"\nCPQ U3 AUDIT: {passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


def cleanup(quote_ids):
    c = pyodbc.connect(CONN, autocommit=True)
    try:
        cur = c.cursor()
        # Review cases for these quotes (events, lines, case).
        for qid in quote_ids:
            if qid is None:
                continue
            case_ids = [r[0] for r in cur.execute(
                "SELECT ReviewCaseId FROM acct.ReviewCase WHERE QuoteHeaderId = ?", qid).fetchall()]
            for cid in case_ids:
                cur.execute("DELETE FROM acct.ReviewEvent WHERE ReviewCaseId = ?", cid)
                cur.execute("DELETE FROM acct.ReviewCaseLine WHERE ReviewCaseId = ?", cid)
                cur.execute("DELETE FROM acct.ReviewCase WHERE ReviewCaseId = ?", cid)
            cur.execute("DELETE FROM quote.QuoteLine WHERE QuoteHeaderId = ?", qid)
            cur.execute("DELETE FROM quote.QuoteHeader WHERE QuoteHeaderId = ?", qid)
        # Notifications + acct rows for the run's distributor.
        cur.execute("SELECT AppUserId FROM acct.AppUser WHERE IdpSubject = ?", DIST)
        uids = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT DistributorAccountId FROM acct.DistributorAccount WHERE CompanyName = ?", COMPANY)
        aids = [r[0] for r in cur.fetchall()]
        if uids:
            uq = ",".join("?" for _ in uids)
            cur.execute(f"DELETE FROM acct.Notification WHERE RecipientAppUserId IN ({uq})", *uids)
        # Role-scoped engineering notifications created for the run's cases.
        cur.execute("DELETE FROM acct.Notification WHERE EventType IN "
                    "('review_submitted','review_completed','review_changes_requested') "
                    "AND ResourceType = 'review_case' AND ResourceId NOT IN "
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

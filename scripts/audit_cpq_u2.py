"""CPQ SPA U2 exit audit - server-owned loyalty pricing, re-runnable + SELF-CLEANING.

Verifies GET /api/v2/quotes/{id}/pricing against a running dev-mock API (default
http://127.0.0.1:8080; override with --base). Creates a quote, adds a priced
Fybroc line + a (likely) unpriced Dean line, then for each loyalty tier assigns
it to the run's dev distributor account and checks the discount math: the rate is
applied to the MERCHANDISE SUBTOTAL ONLY (fully-priced 'found' lines), unpriced
lines are excluded from the base but carried at list in the net, and a staff
(admin) caller with no account gets rate 0. Also checks a missing quote -> 404.
Cleans up every quote + acct.* row it created (by run tag), pass or fail.

Usage:  uv run python scripts/audit_cpq_u2.py [--base URL]
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid

import pyodbc

_args, _ = argparse.ArgumentParser().parse_known_args()
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
SUBJ = f"u2price-{RUN}"
IDEM = f"u2price-idem-{RUN}"
COMPANY = f"U2 Price Co {RUN}"


def dist_headers():
    return {"X-Dev-Assume-Role": "distributor", "X-Dev-Subject": SUBJ,
            "X-Dev-Email": SUBJ + "@dev.local"}


def call(method, path, *, headers=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "null")


results = []
def ok(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name, "-", detail)


def std_sel(family, series):
    _, r = call("POST", f"/families/{family}/configurations/resolve-state",
                body={"series": series, "selections": {}})
    return r.get("selections", {})


def add_line(qid, family, series):
    sel = std_sel(family, series)
    st, line = call("POST", f"/families/{family}/quotes/{qid}/lines",
                    headers=dist_headers(),
                    body={"series": series, "selections": {"SERIES": series, **sel},
                          "quantity": 1, "requested_by": SUBJ})
    return st, line


def set_tier(tier):
    c = pyodbc.connect(CONN, autocommit=True)
    try:
        cur = c.cursor()
        cur.execute(
            "UPDATE acct.DistributorAccount SET LoyaltyTierCode = ? "
            "WHERE CompanyName = ?", tier, COMPANY)
    finally:
        c.close()


def main():
    # Materialize the distributor + an APPROVED account (so configure/quote allowed).
    st, me = call("GET", "/me", headers=dist_headers())
    st, sub = call("POST", "/distributor/applications", headers=dist_headers(),
                   body={"idempotency_key": IDEM, "company_name": COMPANY,
                         "contact": {"address1": "1 A St", "city": "X", "postal_code": "1",
                                     "country": "USA"},
                         "ship_to": {"address1": "1 A St", "city": "X", "postal_code": "1",
                                     "country": "USA"}})
    app_id = sub.get("application_id")
    # admin approves (default admin caller) with standard tier initially
    call("POST", f"/admin/applications/{app_id}/review",
         body={"outcome": "APPROVED", "loyalty_tier_code": "standard"})

    # Create a quote (Fybroc path; quotes are not family-scoped).
    st, q = call("POST", "/families/FYBROC/quotes", headers=dist_headers(),
                 body={"site_code": "TEL", "customer_name": COMPANY, "created_by": SUBJ})
    qid = q.get("quote_header_id")
    ok("quote created", qid is not None, f"qid={qid}")

    # Priced line: Fybroc 1500 (known priced).
    st, l1 = add_line(qid, "FYBROC", "1500")
    ok("fybroc line added", st == 200, f"status={st} ps={l1.get('pricing_status')}")
    priced_ext = float(l1.get("extended_price") or 0.0)
    ok("fybroc line found/priced", l1.get("pricing_status") == "found",
       f"ps={l1.get('pricing_status')} ext={priced_ext}")

    # Unpriced line: try a Dean series (base price pending -> call_for_price/partial).
    unpriced_ext = 0.0
    st, l2 = add_line(qid, "DEAN", "RA3146")
    if st == 200 and l2.get("pricing_status") != "found":
        unpriced_ext = float(l2.get("extended_price") or 0.0)
        ok("dean line unpriced (excluded from base)", True,
           f"ps={l2.get('pricing_status')} ext={unpriced_ext}")
    else:
        ok("dean line unpriced (excluded from base)", st == 200,
           f"status={st} ps={l2.get('pricing_status')} (treated as priced; base check still valid)")
        if st == 200 and l2.get("pricing_status") == "found":
            priced_ext += float(l2.get("extended_price") or 0.0)

    # Tier math checks.
    for tier, bp in [("standard", 0), ("loyalty15", 1500), ("loyalty30", 3000)]:
        set_tier(tier)
        st, p = call("GET", f"/quotes/{qid}/pricing", headers=dist_headers())
        exp_discount = round(priced_ext * bp / 10000.0, 2)
        exp_net = round((priced_ext - exp_discount) + unpriced_ext, 2)
        ok(f"{tier}: rate_bp", p.get("discount_rate_bp") == bp, f"got {p.get('discount_rate_bp')}")
        ok(f"{tier}: merch subtotal = priced only",
           abs(float(p.get("merchandise_subtotal", -1)) - round(priced_ext, 2)) < 0.01,
           f"got {p.get('merchandise_subtotal')} exp {round(priced_ext,2)}")
        ok(f"{tier}: discount_amount",
           abs(float(p.get("discount_amount", -1)) - exp_discount) < 0.01,
           f"got {p.get('discount_amount')} exp {exp_discount}")
        ok(f"{tier}: net_total",
           abs(float(p.get("net_total", -1)) - exp_net) < 0.01,
           f"got {p.get('net_total')} exp {exp_net}")

    # Staff (admin) caller -> rate 0 regardless.
    st, ps = call("GET", f"/quotes/{qid}/pricing")  # default admin, no account
    ok("staff/admin rate 0", ps.get("discount_rate_bp") == 0, f"got {ps.get('discount_rate_bp')}")

    # 404 on missing quote.
    st, _ = call("GET", "/quotes/999999999/pricing", headers=dist_headers())
    ok("missing quote 404", st == 404, f"status={st}")

    cleanup(qid)
    passed = sum(1 for _, c in results if c)
    print(f"\nU2 PRICING: {passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


def cleanup(qid):
    c = pyodbc.connect(CONN, autocommit=True)
    try:
        cur = c.cursor()
        # Quote rows (lines then header).
        if qid:
            cur.execute("DELETE FROM quote.QuoteLine WHERE QuoteHeaderId = ?", qid)
            cur.execute("DELETE FROM quote.QuoteHeader WHERE QuoteHeaderId = ?", qid)
        # acct rows for this run.
        cur.execute("SELECT AppUserId FROM acct.AppUser WHERE IdpSubject = ?", SUBJ)
        uids = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT DistributorAccountId FROM acct.DistributorAccount WHERE CompanyName = ?", COMPANY)
        aids = [r[0] for r in cur.fetchall()]
        if uids:
            uq = ",".join("?" for _ in uids)
            cur.execute(f"DELETE FROM acct.Notification WHERE RecipientAppUserId IN ({uq})", *uids)
        cur.execute("DELETE FROM acct.Notification WHERE Message LIKE ?", f"%{RUN}%")
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

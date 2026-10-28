"""CPQ SPA U1 exit audit - re-runnable, SELF-CLEANING.

Verifies the U1 acceptance slice end-to-end against a running dev-mock API
(default http://127.0.0.1:8080), then deletes every acct.* row it created so
the database returns to its pre-run baseline. Exits non-zero on any failed
check OR if cleanup leaves residue.

Acceptance (handoff ss18 subset / U1 design ss6):
  1. /me resolves identity + capabilities for admin and distributor.
  2. A pending distributor is denied configure/create_quote (server entitlement).
  3. Distributor submits an application with BOTH address sets; a duplicate
     submit (same idempotency key) collapses to ONE application.
  4. Admin lists the application and sees both address snapshots.
  5. Admin approves with loyalty15 -> account APPROVED, applicant notified,
     configure/create_quote unlocked.
  6. Account A cannot read account B's notification by id (API ownership).
  7. A second review of an approved application is rejected (409).

Usage:  python scripts/audit_cpq_u1.py  [--base URL]  [--keep]
        (--keep skips cleanup; for debugging only)

The script uses a unique run tag so repeated runs never collide, and cleans up
by run tag whether or not the checks pass.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid

import pyodbc

CONN = (
    "DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;"
    "DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;"
    "Encrypt=yes;TrustServerCertificate=yes;"
)

RUN = uuid.uuid4().hex[:10]
SUBJ_A = f"audit-distA-{RUN}"
SUBJ_B = f"audit-distB-{RUN}"
IDEM = f"audit-idem-{RUN}"
COMPANY = f"Audit Co {RUN}"


def _dist(subject: str) -> dict[str, str]:
    return {
        "X-Dev-Assume-Role": "distributor",
        "X-Dev-Subject": subject,
        "X-Dev-Email": f"{subject}@dev.local",
    }


class Client:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/") + "/api/v2"

    def call(self, method, path, *, headers=None, body=None):
        url = self.base + path
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, json.loads(resp.read().decode() or "null")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode() or "null")


class Audit:
    def __init__(self) -> None:
        self.results: list[tuple[str, bool, str]] = []

    def check(self, name, cond, detail=""):
        self.results.append((name, bool(cond), str(detail)))
        print(("PASS" if cond else "FAIL"), name, "-", detail)

    @property
    def passed(self) -> int:
        return sum(1 for _, c, _ in self.results if c)

    @property
    def total(self) -> int:
        return len(self.results)


def run_checks(c: Client, a: Audit) -> None:
    # 1. admin /me
    st, me_admin = c.call("GET", "/me")
    a.check("admin /me 200", st == 200, f"status={st}")
    a.check("admin is_admin", me_admin and me_admin["capabilities"]["is_admin"] is True)

    # 2. distributor /me before application
    st, me_d = c.call("GET", "/me", headers=_dist(SUBJ_A))
    caps = (me_d or {}).get("capabilities", {})
    a.check("distA /me 200", st == 200, f"status={st}")
    a.check("distA is_distributor", caps.get("is_distributor") is True)
    a.check("distA denied configure pre-approval", caps.get("configure") is False)
    a.check("distA denied create_quote pre-approval", caps.get("create_quote") is False)
    a.check("distA has no account yet", (me_d or {}).get("account") is None)

    # 3. submit + idempotent duplicate
    body = {
        "idempotency_key": IDEM,
        "company_name": COMPANY,
        "contact": {"first_name": "Ava", "last_name": "Contact", "address1": "1 Main St",
                    "city": "Houston", "state": "TX", "postal_code": "77001",
                    "country": "USA", "phone": "713-555-0100"},
        "ship_to": {"first_name": "Sam", "last_name": "Ship", "address1": "99 Dock Rd",
                    "city": "Houston", "state": "TX", "postal_code": "77002",
                    "country": "USA", "phone": "713-555-0199"},
    }
    st, sub1 = c.call("POST", "/distributor/applications", headers=_dist(SUBJ_A), body=body)
    a.check("submit 201", st == 201, f"status={st} body={sub1}")
    app_id = (sub1 or {}).get("application_id")
    a.check("submit not duplicate", sub1 and sub1.get("was_duplicate") is False)
    st, sub2 = c.call("POST", "/distributor/applications", headers=_dist(SUBJ_A), body=body)
    a.check("duplicate -> same application id", sub2 and sub2.get("application_id") == app_id)
    a.check("duplicate flagged", sub2 and sub2.get("was_duplicate") is True)

    # 4. admin queue + detail
    st, lst = c.call("GET", "/admin/applications?status=PENDING_APPROVAL")
    ids = [x["ApplicationId"] for x in (lst or {}).get("applications", [])]
    a.check("admin sees application", app_id in ids)
    st, det = c.call("GET", f"/admin/applications/{app_id}")
    kinds = {x["Kind"] for x in (det or {}).get("addresses", [])}
    a.check("detail has both addresses", kinds == {"CONTACT", "SHIP_TO"}, str(kinds))

    # 5. approve loyalty15 -> unlock + notify
    st, rev = c.call("POST", f"/admin/applications/{app_id}/review",
                     body={"outcome": "APPROVED", "reason": "audit", "loyalty_tier_code": "loyalty15"})
    a.check("approve 200", st == 200, f"status={st}")
    a.check("approved tier loyalty15", rev and rev.get("loyalty_tier_code") == "loyalty15")
    st, me_d2 = c.call("GET", "/me", headers=_dist(SUBJ_A))
    caps2 = (me_d2 or {}).get("capabilities", {})
    a.check("account APPROVED after review", (me_d2.get("account") or {}).get("Status") == "APPROVED")
    a.check("configure unlocked after approval", caps2.get("configure") is True)
    a.check("create_quote unlocked after approval", caps2.get("create_quote") is True)
    st, notifs = c.call("GET", "/notifications", headers=_dist(SUBJ_A))
    nlist = (notifs or {}).get("notifications", [])
    a.check("applicant notified of approval",
            any("approved" in (n.get("EventType") or "") for n in nlist))

    # 6. ownership: B cannot read A's notification
    notif_id = nlist[0]["NotificationId"] if nlist else None
    c.call("GET", "/me", headers=_dist(SUBJ_B))  # materialize B
    st_b, _ = c.call("POST", f"/notifications/{notif_id}/read", headers=_dist(SUBJ_B))
    a.check("B cannot read A notification (404)", st_b == 404, f"status={st_b}")

    # 7. re-review blocked
    st, _ = c.call("POST", f"/admin/applications/{app_id}/review",
                   body={"outcome": "APPROVED", "loyalty_tier_code": "loyalty30"})
    a.check("re-approve blocked (409)", st == 409, f"status={st}")


def cleanup() -> int:
    """Delete everything created by this run (by run tag). Returns residue count."""
    conn = pyodbc.connect(CONN, autocommit=True)
    try:
        cur = conn.cursor()
        # Resolve the two app users + their account(s) by the run-tagged subjects.
        cur.execute(
            "SELECT AppUserId FROM acct.AppUser WHERE IdpSubject IN (?, ?)",
            SUBJ_A, SUBJ_B,
        )
        user_ids = [r[0] for r in cur.fetchall()]
        acct_ids = []
        if user_ids:
            q = ",".join("?" for _ in user_ids)
            cur.execute(
                f"SELECT DISTINCT DistributorAccountId FROM acct.AccountMembership "
                f"WHERE AppUserId IN ({q})",
                *user_ids,
            )
            acct_ids = [r[0] for r in cur.fetchall()]

        # Delete children first (FK order), scoped by run tag / resolved ids.
        # Notifications: by recipient user OR the run-tagged company message.
        if user_ids:
            uq = ",".join("?" for _ in user_ids)
            cur.execute(f"DELETE FROM acct.Notification WHERE RecipientAppUserId IN ({uq})", *user_ids)
        cur.execute("DELETE FROM acct.Notification WHERE Message LIKE ?", f"%{RUN}%")

        if acct_ids:
            aq = ",".join("?" for _ in acct_ids)
            cur.execute(
                f"DELETE FROM acct.Address WHERE ApplicationId IN "
                f"(SELECT ApplicationId FROM acct.AccountApplication WHERE DistributorAccountId IN ({aq}))",
                *acct_ids,
            )
            cur.execute(f"DELETE FROM acct.LoyaltyAssignment WHERE DistributorAccountId IN ({aq})", *acct_ids)
            cur.execute(f"DELETE FROM acct.AccountApplication WHERE DistributorAccountId IN ({aq})", *acct_ids)
            cur.execute(f"DELETE FROM acct.AccountMembership WHERE DistributorAccountId IN ({aq})", *acct_ids)
            cur.execute(f"DELETE FROM acct.DistributorAccount WHERE DistributorAccountId IN ({aq})", *acct_ids)

        if user_ids:
            uq = ",".join("?" for _ in user_ids)
            cur.execute(f"DELETE FROM acct.AppUser WHERE AppUserId IN ({uq})", *user_ids)

        # Residue check
        residue = cur.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM acct.AppUser WHERE IdpSubject IN (?,?)) + "
            "(SELECT COUNT(*) FROM acct.DistributorAccount WHERE CompanyName = ?) + "
            "(SELECT COUNT(*) FROM acct.Notification WHERE Message LIKE ?)",
            SUBJ_A, SUBJ_B, COMPANY, f"%{RUN}%",
        ).fetchval()
        return int(residue)
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8080")
    ap.add_argument("--keep", action="store_true", help="skip cleanup (debug)")
    args = ap.parse_args()

    c = Client(args.base)
    a = Audit()

    # Wait briefly for server readiness.
    for _ in range(10):
        st, _ = c.call("GET", "/me")
        if st == 200:
            break
        time.sleep(1)

    print(f"=== CPQ U1 AUDIT (run {RUN}) ===")
    try:
        run_checks(c, a)
    finally:
        if not args.keep:
            residue = cleanup()
            a.check("self-clean: no residue", residue == 0, f"residue={residue}")
        else:
            print("(--keep) cleanup skipped")

    print(f"\nCPQ U1 AUDIT: {a.passed}/{a.total} checks passed")
    return 0 if a.passed == a.total else 1


if __name__ == "__main__":
    sys.exit(main())

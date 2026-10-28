"""CPQ SPA U1 - Account / Identity routes (schema: acct).

Additive router mounted alongside the existing v2 router. Provides the identity,
distributor onboarding, admin approval, and notification endpoints that drive the
new SPA. Authorization is enforced HERE (not just in the UI):

  - Every caller is resolved to an acct.AppUser (resolve-or-create by issuer+subject).
  - Distributor endpoints are scoped to the caller's OWN account (ownership check),
    so account A can never read account B.
  - Admin endpoints require the admin role.
  - configure / create_quote entitlements are server-owned and only granted when the
    caller's distributor account is APPROVED (surfaced via /me; later phases enforce
    the actual config/quote endpoints against the same rule).

Nothing here touches cfg / price / quote config data. Fybroc is unaffected.
"""
from __future__ import annotations

from typing import Any

import pyodbc
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.api.auth import (
    AuthenticatedUser,
    ROLE_ADMIN,
    ROLE_DISTRIBUTOR,
    ROLE_ENGINEERING,
    get_current_user,
    idp_identity,
)

router_acct = APIRouter(prefix="/api/v2", tags=["acct"])


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _conn(request: Request) -> pyodbc.Connection:
    conn_str = request.app.state.settings.connection_string
    return pyodbc.connect(conn_str, autocommit=True)


def _rows_as_dicts(cursor) -> list[dict[str, Any]]:
    # A proc that RETURNs without selecting leaves cursor.description = None.
    if cursor.description is None:
        return []
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def _one(cursor) -> dict[str, Any] | None:
    # No result set (e.g. a scope-blocked proc that RETURNed early).
    if cursor.description is None:
        return None
    cols = [c[0] for c in cursor.description]
    row = cursor.fetchone()
    return dict(zip(cols, row)) if row else None


def _resolve_app_user(request: Request, user: AuthenticatedUser) -> dict[str, Any]:
    """Resolve-or-create the acct.AppUser for the current identity."""
    issuer, subject = idp_identity(user)
    conn = _conn(request)
    try:
        cur = conn.cursor()
        cur.execute(
            "{CALL acct.usp_UpsertAppUser (?, ?, ?, ?)}",
            issuer, subject, user.email or None, user.display_name or None,
        )
        row = _one(cur)
        if row is None:  # pragma: no cover - MERGE always returns the row
            raise HTTPException(status_code=500, detail="Failed to resolve identity.")
        return row
    finally:
        conn.close()


def _get_my_account(request: Request, app_user_id: int) -> dict[str, Any] | None:
    conn = _conn(request)
    try:
        cur = conn.cursor()
        cur.execute("{CALL acct.usp_GetMyAccount (?)}", app_user_id)
        return _one(cur)
    finally:
        conn.close()


def _is_admin(user: AuthenticatedUser) -> bool:
    return user.has_role(ROLE_ADMIN)


def _is_distributor(user: AuthenticatedUser) -> bool:
    return ROLE_DISTRIBUTOR in user.roles or _is_admin(user)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class AddressIn(BaseModel):
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    address1: str = Field(min_length=1, max_length=200)
    address2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    postal_code: str = Field(min_length=1, max_length=40)
    country: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=60)


class SubmitApplicationIn(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=100)
    company_name: str = Field(min_length=1, max_length=200)
    contact: AddressIn
    ship_to: AddressIn


class ReviewIn(BaseModel):
    outcome: str = Field(pattern="^(APPROVED|CHANGES_REQUESTED|REJECTED)$")
    reason: str | None = Field(default=None, max_length=1000)
    loyalty_tier_code: str | None = Field(default=None, max_length=20)


# ---------------------------------------------------------------------------
# Capability computation (server-owned entitlements)
# ---------------------------------------------------------------------------

def _capabilities(user: AuthenticatedUser, account: dict[str, Any] | None) -> dict[str, Any]:
    """Compute the SPA-facing capability flags for the current identity.

    Staff roles (admin/configurator/pricing/engineering) keep their existing
    permissions. A distributor can configure/quote ONLY when their account is
    APPROVED - this is the server entitlement the UI must obey (and later phases
    enforce on the config/quote endpoints themselves).
    """
    is_admin = _is_admin(user)
    is_distributor = ROLE_DISTRIBUTOR in user.roles
    account_status = (account or {}).get("Status")
    approved = account_status == "APPROVED"

    staff_can_configure = user.has_permission("configure")
    staff_can_quote = user.has_permission("create_quote")

    return {
        "is_admin": is_admin,
        "is_distributor": is_distributor,
        "submit_application": user.has_permission("submit_application") or is_distributor,
        "view_own_account": user.has_permission("view_own_account") or is_distributor,
        "review_applications": is_admin,
        # configure/quote: staff keep their permission; distributor gated on APPROVED.
        "configure": staff_can_configure or (is_distributor and approved),
        "create_quote": staff_can_quote or (is_distributor and approved),
        "account_status": account_status,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router_acct.get("/me")
async def get_me(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Current identity + capabilities + account status. Drives SPA routing."""
    app_user = _resolve_app_user(request, user)
    account = _get_my_account(request, app_user["AppUserId"])
    return {
        "user": {
            "app_user_id": app_user["AppUserId"],
            "email": user.email,
            "display_name": user.display_name,
            "roles": user.roles,
        },
        "capabilities": _capabilities(user, account),
        "account": account,
    }


@router_acct.post("/distributor/applications", status_code=201)
async def submit_application(
    request: Request,
    body: SubmitApplicationIn,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Submit a distributor onboarding application (idempotent)."""
    if not _is_distributor(user):
        raise HTTPException(status_code=403, detail="Distributor role required.")

    app_user = _resolve_app_user(request, user)
    c, s = body.contact, body.ship_to
    conn = _conn(request)
    try:
        cur = conn.cursor()
        cur.execute(
            "{CALL acct.usp_SubmitApplication "
            "(?, ?, ?, ?,?,?,?,?,?,?,?,?, ?,?,?,?,?,?,?,?,?)}",
            app_user["AppUserId"], body.idempotency_key, body.company_name,
            c.first_name, c.last_name, c.address1, c.address2, c.city, c.state,
            c.postal_code, c.country, c.phone,
            s.first_name, s.last_name, s.address1, s.address2, s.city, s.state,
            s.postal_code, s.country, s.phone,
        )
        row = _one(cur)
        return {
            "application_id": row["ApplicationId"],
            "distributor_account_id": row["DistributorAccountId"],
            "status": row["Status"],
            "was_duplicate": bool(row.get("WasDuplicate", 0)),
        }
    finally:
        conn.close()


@router_acct.get("/distributor/account")
async def get_my_distributor_account(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """The caller's OWN distributor account + latest application status."""
    if not _is_distributor(user):
        raise HTTPException(status_code=403, detail="Distributor role required.")
    app_user = _resolve_app_user(request, user)
    account = _get_my_account(request, app_user["AppUserId"])
    if account is None:
        raise HTTPException(status_code=404, detail="No distributor account for this user.")
    return account


@router_acct.get("/admin/applications")
async def list_applications(
    request: Request,
    status: str | None = None,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Admin: list onboarding applications (optional status filter)."""
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin role required.")
    conn = _conn(request)
    try:
        cur = conn.cursor()
        cur.execute("{CALL acct.usp_ListApplications (?)}", status)
        return {"applications": _rows_as_dicts(cur)}
    finally:
        conn.close()


@router_acct.get("/admin/applications/{application_id}")
async def get_application(
    request: Request,
    application_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Admin: full application detail including both address snapshots."""
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin role required.")
    conn = _conn(request)
    try:
        cur = conn.cursor()
        cur.execute("{CALL acct.usp_GetApplication (?)}", application_id)
        header = _one(cur)
        if header is None:
            raise HTTPException(status_code=404, detail="Application not found.")
        addresses = _rows_as_dicts(cur) if cur.nextset() else []
        return {"application": header, "addresses": addresses}
    finally:
        conn.close()


@router_acct.post("/admin/applications/{application_id}/review")
async def review_application(
    request: Request,
    application_id: int,
    body: ReviewIn,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Admin: approve (with loyalty tier) / request changes / reject."""
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin role required.")
    reviewer = _resolve_app_user(request, user)
    conn = _conn(request)
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                "{CALL acct.usp_ReviewApplication (?, ?, ?, ?, ?)}",
                application_id, reviewer["AppUserId"], body.outcome,
                body.reason, body.loyalty_tier_code,
            )
            row = _one(cur)
        except pyodbc.Error as exc:
            # Proc RAISERROR (not found / already approved / bad outcome).
            raise HTTPException(status_code=409, detail=str(exc.args[-1])) from exc
        if row is None:
            raise HTTPException(status_code=404, detail="Application not found.")
        return {
            "application_id": row["ApplicationId"],
            "distributor_account_id": row["DistributorAccountId"],
            "status": row["Status"],
            "loyalty_tier_code": row.get("LoyaltyTierCode"),
        }
    finally:
        conn.close()


@router_acct.get("/notifications")
async def list_notifications(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Notifications for the caller (admins also see the role-scoped admin queue)."""
    app_user = _resolve_app_user(request, user)
    include_role = "admin" if _is_admin(user) else None
    conn = _conn(request)
    try:
        cur = conn.cursor()
        cur.execute(
            "{CALL acct.usp_ListNotifications (?, ?)}",
            app_user["AppUserId"], include_role,
        )
        return {"notifications": _rows_as_dicts(cur)}
    finally:
        conn.close()


@router_acct.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    request: Request,
    notification_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Mark a notification read. Scope-checked so A cannot read B's notifications."""
    app_user = _resolve_app_user(request, user)
    include_role = "admin" if _is_admin(user) else None
    conn = _conn(request)
    try:
        cur = conn.cursor()
        cur.execute(
            "{CALL acct.usp_MarkNotificationRead (?, ?, ?)}",
            notification_id, app_user["AppUserId"], include_role,
        )
        row = _one(cur)
        updated = int(row["Updated"]) if row else 0
        if updated == 0:
            # Either not found or not owned by caller - do not leak which.
            raise HTTPException(status_code=404, detail="Notification not found.")
        return {"notification_id": notification_id, "read": True}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# U2 — Quote pricing with server-owned loyalty discount
# ---------------------------------------------------------------------------
# Additive, read-only. Computes a quote's loyalty-adjusted totals SERVER-SIDE so
# the discount rate is never owned by the UI (decision D4). It reads the caller's
# assigned loyalty tier (acct.DistributorAccount -> acct.LoyaltyTier.RateBp) and
# the persisted quote (existing quote.usp_GetQuote), and applies the rate to the
# MERCHANDISE SUBTOTAL ONLY: the sum of fully-priced lines (pricing_status
# 'found'). Partial / call_for_price lines are reported but excluded from the
# discountable base. Staff/admin callers (no distributor account) get rate 0
# (list pricing). No v2 route or DB object is changed by this endpoint.


def _loyalty_rate_bp_for_account(cur, account: dict[str, Any] | None) -> tuple[int, str | None]:
    """Return (rate_bp, tier_code) for the caller's account. No account or no
    assigned tier -> (0, tier_code_or_None): list pricing."""
    if not account:
        return 0, None
    tier_code = account.get("LoyaltyTierCode")
    if not tier_code:
        return 0, None
    row = cur.execute(
        "SELECT RateBp FROM acct.LoyaltyTier WHERE LoyaltyTierCode = ? AND IsActive = 1",
        tier_code,
    ).fetchone()
    return (int(row[0]) if row else 0), tier_code


def _fetch_quote_header_and_lines(cur, quote_header_id: int):
    """Read a quote via the existing quote.usp_GetQuote (header set, then lines
    set), returning (header_dict | None, [line_dict]). Mirrors v2_routes._fetch_quote
    but kept local so the acct router has no import dependency on v2_routes.

    quote.usp_GetQuote RAISERRORs 'Quote not found' for a missing id (rather than
    returning an empty set); that surfaces as a pyodbc error. We translate it to a
    clean 404 here so a missing quote does not become a 503 via the global pyodbc
    exception handler."""
    try:
        cur.execute("EXEC quote.usp_GetQuote @QuoteHeaderId=?;", quote_header_id)
        hcols = [c[0] for c in cur.description]
        hrow = cur.fetchone()
    except pyodbc.Error as exc:
        if "not found" in str(exc).lower():
            raise HTTPException(status_code=404, detail="Quote not found.") from exc
        raise
    if hrow is None:
        return None, []
    header = dict(zip(hcols, hrow))
    cur.nextset()
    lcols = [c[0] for c in cur.description]
    lines = [dict(zip(lcols, r)) for r in cur.fetchall()]
    return header, lines


@router_acct.get("/quotes/{quote_header_id}/pricing")
async def get_quote_pricing(
    request: Request,
    quote_header_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Loyalty-adjusted totals for a quote (server-owned discount rate, D4).

    - list_total           : sum of ALL line ExtendedPrice (unchanged list pricing)
    - merchandise_subtotal : sum of ExtendedPrice for pricing_status='found' lines
                             (the discountable base; D4 "merchandise subtotal only")
    - discount_rate_bp     : the caller account's loyalty rate in basis points
    - discount_amount      : merchandise_subtotal * rate
    - net_total            : merchandise_subtotal - discount_amount, PLUS the
                             unpriced-line list amount carried through at list
                             (so the figure is honest about what is/ isn't priced)
    - unpriced_line_count  : lines not 'found' (partial / call_for_price)
    """
    app_user = _resolve_app_user(request, user)
    conn = _conn(request)
    try:
        cur = conn.cursor()
        header, lines = _fetch_quote_header_and_lines(cur, quote_header_id)
        if header is None:
            raise HTTPException(status_code=404, detail="Quote not found.")

        account = _get_my_account(request, app_user["AppUserId"])
        rate_bp, tier_code = _loyalty_rate_bp_for_account(cur, account)

        currency = header.get("CurrencyCode") or "USD"
        list_total = 0.0
        merch_subtotal = 0.0
        unpriced_total = 0.0
        unpriced_count = 0
        for ln in lines:
            ext = float(ln.get("ExtendedPrice") or 0.0)
            list_total += ext
            if (ln.get("PricingStatus") or "") == "found":
                merch_subtotal += ext
            else:
                unpriced_total += ext
                unpriced_count += 1

        discount_amount = round(merch_subtotal * rate_bp / 10000.0, 2)
        net_priced = merch_subtotal - discount_amount
        net_total = round(net_priced + unpriced_total, 2)

        return {
            "quote_header_id": quote_header_id,
            "currency": currency,
            "loyalty_tier_code": tier_code,
            "discount_rate_bp": rate_bp,
            "list_total": round(list_total, 2),
            "merchandise_subtotal": round(merch_subtotal, 2),
            "discount_amount": discount_amount,
            "net_total": net_total,
            "unpriced_line_count": unpriced_count,
            "unpriced_line_total": round(unpriced_total, 2),
            "line_count": len(lines),
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# U3 — Engineering review queue with REQUIRED brand/site routing
# ---------------------------------------------------------------------------
# Brand/site isolation is enforced HERE and in the stored procs (handoff §4):
#   - A case's brand is derived SERVER-SIDE from the persisted quote lines
#     (usp_SubmitQuoteForReview); never from a client-supplied family/site.
#   - Every engineer action is scoped to the caller's acct.EngineerMembership
#     (brand, site) set, passed to the procs as @SiteCsv. An engineer for one
#     site cannot read/claim/edit another site's case by id -> treated as not
#     found (404). Admin oversight is read-only across both queues.


class SubmitForReviewIn(BaseModel):
    pass  # no body needed; brand is derived from the persisted quote


class ResolveLineIn(BaseModel):
    resolved_unit_price: float | None = None
    custom_spec: str | None = Field(default=None, max_length=1000)
    engineer_note: str | None = Field(default=None, max_length=1000)


class ReviewNotesIn(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)


class CompleteReviewIn(BaseModel):
    lead_time_days: int | None = None
    notes: str | None = Field(default=None, max_length=2000)


def _engineer_sites(request: Request, app_user_id: int) -> list[str]:
    """The sites the caller is authorized to act on, from acct.EngineerMembership.
    Empty list => not an engineer for any site."""
    conn = _conn(request)
    try:
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT DISTINCT SiteCode FROM acct.EngineerMembership WHERE AppUserId = ?",
            app_user_id,
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def _require_engineer_sites(request: Request, user: AuthenticatedUser) -> tuple[dict, list[str]]:
    """Resolve the engineer AppUser + their authorized sites, or 403 if none.
    Admins without a membership do NOT get engineer edit scope (handoff §4)."""
    if ROLE_ENGINEERING not in user.roles and not user.has_role(ROLE_ADMIN):
        raise HTTPException(status_code=403, detail="Engineering role required.")
    app_user = _resolve_app_user(request, user)
    sites = _engineer_sites(request, app_user["AppUserId"])
    if not sites:
        raise HTTPException(
            status_code=403,
            detail="No engineering brand/site membership for this user.",
        )
    return app_user, sites


# --- Distributor: submit a quote for engineering review -------------------

@router_acct.post("/quotes/{quote_header_id}/submit-for-review", status_code=201)
async def submit_quote_for_review(
    request: Request,
    quote_header_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Submit a quote for engineering review. The server derives the brand from
    the persisted quote lines and routes to the responsible site queue."""
    app_user = _resolve_app_user(request, user)
    conn = _conn(request)
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                "{CALL acct.usp_SubmitQuoteForReview (?, ?)}",
                quote_header_id, app_user["AppUserId"],
            )
            row = _one(cur)
        except pyodbc.Error as exc:
            if "not found" in str(exc).lower():
                raise HTTPException(status_code=404, detail="Quote not found.") from exc
            raise
        if row is None:
            raise HTTPException(status_code=500, detail="Review submission failed.")
        return {
            "review_case_id": row["ReviewCaseId"],
            "quote_header_id": row["QuoteHeaderId"],
            "brand": row["Brand"],
            "responsible_site_code": row["ResponsibleSiteCode"],
            "status": row["Status"],
            "routing_exception": bool(row.get("RoutingException", 0)),
            "was_existing": bool(row.get("WasExisting", 0)),
        }
    finally:
        conn.close()


# --- Engineer: brand/site-scoped queue ------------------------------------

@router_acct.get("/engineering/cases")
async def list_review_cases(
    request: Request,
    status: str | None = None,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """The caller's authorized review queue (scoped to their membership sites)."""
    _app_user, sites = _require_engineer_sites(request, user)
    conn = _conn(request)
    try:
        cur = conn.cursor()
        cur.execute(
            "{CALL acct.usp_ListReviewCases (?, ?, ?)}",
            ",".join(sites), status, 0,
        )
        return {"cases": _rows_as_dicts(cur), "authorized_sites": sites}
    finally:
        conn.close()


@router_acct.get("/engineering/cases/{review_case_id}")
async def get_review_case(
    request: Request,
    review_case_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Case + lines, scope-checked. A case outside the caller's sites -> 404."""
    _app_user, sites = _require_engineer_sites(request, user)
    conn = _conn(request)
    try:
        cur = conn.cursor()
        cur.execute(
            "{CALL acct.usp_GetReviewCase (?, ?, ?)}",
            review_case_id, ",".join(sites), 0,
        )
        header = _one(cur)
        if header is None:
            # Not authorized for this site OR nonexistent: do not leak which.
            raise HTTPException(status_code=404, detail="Review case not found.")
        lines = _rows_as_dicts(cur) if cur.nextset() else []
        return {"case": header, "lines": lines}
    finally:
        conn.close()


def _engineer_case_action(request, user, proc_call, params):
    """Run a scope-checked engineer proc; translate the proc's authorization
    RAISERROR into 403 and 'not found' into 404."""
    _app_user, sites = _require_engineer_sites(request, user)
    conn = _conn(request)
    try:
        cur = conn.cursor()
        try:
            cur.execute(proc_call, *params(_app_user["AppUserId"], ",".join(sites)))
            return _one(cur)
        except pyodbc.Error as exc:
            msg = str(exc).lower()
            if "not authorized" in msg:
                raise HTTPException(status_code=404, detail="Review case not found.") from exc
            if "not found" in msg:
                raise HTTPException(status_code=404, detail="Review case not found.") from exc
            raise HTTPException(status_code=409, detail=str(exc.args[-1])) from exc
    finally:
        conn.close()


@router_acct.post("/engineering/cases/{review_case_id}/claim")
async def claim_review_case(
    request: Request,
    review_case_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    row = _engineer_case_action(
        request, user,
        "{CALL acct.usp_ClaimReviewCase (?, ?, ?)}",
        lambda uid, csv: (review_case_id, uid, csv),
    )
    return {"review_case_id": review_case_id, "status": (row or {}).get("Status", "CLAIMED")}


@router_acct.post("/engineering/cases/{review_case_id}/lines/{review_case_line_id}/resolve")
async def resolve_review_case_line(
    request: Request,
    review_case_id: int,
    review_case_line_id: int,
    body: ResolveLineIn,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    row = _engineer_case_action(
        request, user,
        "{CALL acct.usp_ResolveReviewCaseLine (?, ?, ?, ?, ?, ?, ?)}",
        lambda uid, csv: (
            review_case_id, review_case_line_id, uid, csv,
            body.resolved_unit_price, body.custom_spec, body.engineer_note,
        ),
    )
    return {"review_case_line_id": review_case_line_id, "result": (row or {}).get("Result", "resolved")}


@router_acct.post("/engineering/cases/{review_case_id}/request-changes")
async def request_review_changes(
    request: Request,
    review_case_id: int,
    body: ReviewNotesIn,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    row = _engineer_case_action(
        request, user,
        "{CALL acct.usp_RequestReviewChanges (?, ?, ?, ?)}",
        lambda uid, csv: (review_case_id, uid, csv, body.notes),
    )
    return {"review_case_id": review_case_id, "status": (row or {}).get("Status", "CHANGES_REQUESTED")}


@router_acct.post("/engineering/cases/{review_case_id}/complete")
async def complete_review_case(
    request: Request,
    review_case_id: int,
    body: CompleteReviewIn,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    row = _engineer_case_action(
        request, user,
        "{CALL acct.usp_CompleteReviewCase (?, ?, ?, ?, ?)}",
        lambda uid, csv: (review_case_id, uid, csv, body.lead_time_days, body.notes),
    )
    return {
        "review_case_id": review_case_id,
        "status": (row or {}).get("Status", "COMPLETED"),
        "lead_time_days": (row or {}).get("LeadTimeDays"),
    }


# --- Admin: read-only oversight across both queues ------------------------

@router_acct.get("/admin/engineering/cases")
async def admin_list_review_cases(
    request: Request,
    status: str | None = None,
    user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Admin oversight: list review cases across ALL sites (read-only)."""
    if not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin role required.")
    conn = _conn(request)
    try:
        cur = conn.cursor()
        cur.execute("{CALL acct.usp_ListReviewCases (?, ?, ?)}", None, status, 1)
        return {"cases": _rows_as_dicts(cur)}
    finally:
        conn.close()

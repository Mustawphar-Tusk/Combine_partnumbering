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
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def _one(cursor) -> dict[str, Any] | None:
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

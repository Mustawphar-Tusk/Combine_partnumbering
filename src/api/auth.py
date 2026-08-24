"""U170 - Microsoft Entra ID (Azure AD) Authentication & Authorization.

Roles:
  - engineering: publish metadata, manage configurations
  - pricing: manage price rules and publications
  - configurator: configure products, create quotes (sales users)
  - admin: all permissions

When APP_ENVIRONMENT=development, auth is bypassed and a mock user is injected.
In production, Bearer tokens from Entra ID are validated and role-checked.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


# Roles
ROLE_ENGINEERING = "engineering"
ROLE_PRICING = "pricing"
ROLE_CONFIGURATOR = "configurator"
ROLE_ADMIN = "admin"

# Role hierarchy: admin has all permissions
ROLE_PERMISSIONS = {
    ROLE_ADMIN: {"publish_metadata", "manage_pricing", "configure", "create_quote", "audit"},
    ROLE_ENGINEERING: {"publish_metadata", "configure", "audit"},
    ROLE_PRICING: {"manage_pricing", "configure", "create_quote"},
    ROLE_CONFIGURATOR: {"configure", "create_quote"},
}


@dataclass
class AuthenticatedUser:
    """Represents the authenticated user from Entra ID token."""
    user_id: str
    display_name: str
    email: str
    roles: list[str]
    tenant_id: str | None = None

    def has_permission(self, permission: str) -> bool:
        for role in self.roles:
            if permission in ROLE_PERMISSIONS.get(role, set()):
                return True
        return False

    def has_role(self, role: str) -> bool:
        return role in self.roles or ROLE_ADMIN in self.roles


# Development mock user
_DEV_USER = AuthenticatedUser(
    user_id="dev-user-001",
    display_name="Development User",
    email="dev@tuskind.com",
    roles=[ROLE_ADMIN],
    tenant_id="dev-tenant",
)


_bearer_scheme = HTTPBearer(auto_error=False)


def _is_development() -> bool:
    return os.getenv("APP_ENVIRONMENT", "development").lower() == "development"


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> AuthenticatedUser:
    """
    Dependency that resolves the current authenticated user.
    
    In development: returns a mock admin user (no token required).
    In production: validates the Entra ID Bearer token and extracts claims.
    """
    if _is_development():
        return _DEV_USER

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide a Bearer token from Microsoft Entra ID.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # In production, validate the JWT against Entra ID
    # This requires: tenant_id, client_id, and the JWKS endpoint
    user = await _validate_entra_token(token)
    return user


async def _validate_entra_token(token: str) -> AuthenticatedUser:
    """
    Validate a Microsoft Entra ID JWT token.
    
    In a real implementation:
    1. Fetch JWKS from https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys
    2. Decode and verify the JWT signature
    3. Validate issuer, audience, expiry
    4. Extract claims (name, email, roles)
    
    Entra ID app registration must define appRoles matching our role names.
    """
    # Placeholder for production implementation
    # TODO: Install python-jose or authlib for JWT validation
    # TODO: Configure ENTRA_TENANT_ID and ENTRA_CLIENT_ID in .env
    raise HTTPException(
        status_code=501,
        detail="Production Entra ID validation not yet configured. Set APP_ENVIRONMENT=development for dev mode.",
    )


def require_permission(permission: str):
    """Dependency factory that checks a specific permission."""
    async def _check(user: AuthenticatedUser = Depends(get_current_user)):
        if not user.has_permission(permission):
            raise HTTPException(
                status_code=403,
                detail=f"Permission '{permission}' required. Your roles: {user.roles}",
            )
        return user
    return _check


def require_role(role: str):
    """Dependency factory that checks a specific role."""
    async def _check(user: AuthenticatedUser = Depends(get_current_user)):
        if not user.has_role(role):
            raise HTTPException(
                status_code=403,
                detail=f"Role '{role}' required. Your roles: {user.roles}",
            )
        return user
    return _check


# Convenience dependencies
require_engineering = require_role(ROLE_ENGINEERING)
require_pricing = require_role(ROLE_PRICING)
require_configurator = require_role(ROLE_CONFIGURATOR)

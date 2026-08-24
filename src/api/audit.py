"""U170 - Audit logging for configuration operations.

Records all significant operations (configure, resolve, publish, quote)
to the audit table for traceability and compliance.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pyodbc

from src.api.auth import AuthenticatedUser


def log_audit_event(
    *,
    connection_string: str,
    user: AuthenticatedUser,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict | None = None,
) -> None:
    """
    Record an audit event to the database.
    
    Actions: configure, resolve, publish_metadata, publish_pricing,
             create_quote, add_quote_line, activate_publication
    """
    conn = pyodbc.connect(connection_string, autocommit=True)
    try:
        conn.cursor().execute(
            """
            INSERT INTO cfg.AuditLog
            (UserId, DisplayName, Email, Action, ResourceType, ResourceId, DetailsJson, EventAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            user.user_id,
            user.display_name,
            user.email,
            action,
            resource_type,
            resource_id,
            json.dumps(details) if details else None,
            datetime.now(timezone.utc),
        )
    except pyodbc.Error:
        # Audit failure should not break the main operation
        pass
    finally:
        conn.close()

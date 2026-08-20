"""F120.0 - Extract current SQL metadata for Fybroc (read-only).

Roadmap anchor
--------------
docs/PROJECT_MASTER_ROADMAP.md, Section 6, Milestone F120
("Fybroc Rev0.3 Configuration Model") - the "Compare against current SQL
metadata" requirement, specifically:
  cfg.AttributeValue
  cfg.SeriesFieldOption
  cfg.FieldOptionDependency

This is the SQL-side half of F120's required comparison. The Rev0.3-side
half (Items, Constraints, Hierarchy, Combine Variables, Selections,
Constraint Index, Feasible Constraints, Motor Constraints) is separate
work already in progress against the workbook directly.

This script is STRICTLY READ-ONLY. It issues only SELECT statements,
using the exact same connection pattern and table/column names already
established in src/config/settings.py and
src/configuration_engine/{resolvers,series_projection,
dependency_projection,active_publication}.py - reused, not reinvented.
It makes NO changes to any table, procedure, or publication status.

Connection reuses your existing .env-driven Settings (same as the
running application) rather than a new hardcoded connection string, so
this connects to whatever your app already considers "the database" -
no separate credentials to manage.

Scope: FYBROC family only, current ACTIVE metadata publication only
(same publication the running application would use right now).

Output:
  docs/evidence/F120/FYBROC_SQL_METADATA_SNAPSHOT.json

Nothing is written back to SQL. Nothing outside this one JSON file is
written to disk.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import pyodbc
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "pyodbc is required (it's already a pinned project dependency - "
        "run this with the project's own .venv interpreter)."
    ) from exc

STEP = "F120.0"
ROADMAP_VERSION = "1.0"
MILESTONE = "F120"
FAMILY_CODE = "FYBROC"


def build_connection_string(repo_root: Path) -> str:
    """Reuses the exact Settings fields from src/config/settings.py rather
    than hardcoding a new connection string. Imports the real project
    module, so this only works run from the repo root with the project's
    own .venv (same requirement as every other script so far)."""
    sys.path.insert(0, str(repo_root))
    from src.config.settings import get_settings  # noqa: E402

    s = get_settings()
    parts = [
        f"DRIVER={{{s.sql_driver}}}",
        f"SERVER={s.sql_server}",
        f"DATABASE={s.sql_database}",
        f"Encrypt={'yes' if s.sql_encrypt else 'no'}",
        f"TrustServerCertificate={'yes' if s.sql_trust_server_certificate else 'no'}",
        f"Connection Timeout={s.sql_connection_timeout}",
    ]
    if s.sql_trusted_connection:
        parts.append("Trusted_Connection=yes")
    else:
        if not s.sql_username or s.sql_password is None:
            raise SystemExit(
                "SQL_TRUSTED_CONNECTION=no in your .env, but SQL_USERNAME/"
                "SQL_PASSWORD are not both set. Check your .env file."
            )
        parts.extend([f"UID={s.sql_username}", f"PWD={s.sql_password}"])
    return ";".join(parts)


def get_active_publication_id(cursor):
    """Verified against sql/12_Create_Metadata_Publication_And_Attributes.sql -
    VersionCode/Description/CreatedAt/ActivatedAt are the real columns.
    (PublishedAt does not exist on this table - an earlier version of this
    script incorrectly assumed it did.)"""
    row = cursor.execute(
        """
        SELECT TOP (1) MetadataPublicationId, VersionCode, Description, CreatedAt, ActivatedAt
        FROM cfg.MetadataPublication
        WHERE Status = 'Active'
        ORDER BY ActivatedAt DESC, MetadataPublicationId DESC;
        """
    ).fetchone()
    if row is None:
        raise SystemExit("No active metadata publication exists - nothing to compare against.")
    return row


def get_pump_family_id(cursor, family_code: str) -> int:
    row = cursor.execute(
        "SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode = ?;",
        family_code,
    ).fetchone()
    if row is None:
        raise SystemExit(f"No cfg.PumpFamily row found for FamilyCode = {family_code!r}.")
    return int(row[0])


def fetch_attribute_values(cursor, pump_family_id: int, publication_id: int) -> list[dict[str, Any]]:
    """WorkbookName/WorksheetName verified against
    sql/12_Create_Metadata_Publication_And_Attributes.sql - shows exactly
    which source workbook each row was compiled from."""
    rows = cursor.execute(
        """
        SELECT
            av.AttributeValueId,
            av.FieldCode,
            av.DisplayValue,
            av.IdentifierCode,
            av.IsActive,
            av.WorkbookName,
            av.WorksheetName
        FROM cfg.AttributeValue AS av
        WHERE av.PumpFamilyId = ?
          AND av.MetadataPublicationId = ?
        ORDER BY av.FieldCode, av.DisplayValue;
        """,
        pump_family_id, publication_id,
    ).fetchall()
    return [
        {
            "attribute_value_id": r.AttributeValueId,
            "field_code": r.FieldCode,
            "display_value": r.DisplayValue,
            "identifier_code": r.IdentifierCode,
            "is_active": bool(r.IsActive),
            "source_workbook": r.WorkbookName,
            "source_worksheet": r.WorksheetName,
        }
        for r in rows
    ]


def fetch_series_field_options(cursor, pump_family_id: int, publication_id: int) -> list[dict[str, Any]]:
    """WorkbookName/WorksheetName/SourceRow verified against
    sql/14_Create_Series_Field_Option_Metadata.sql."""
    rows = cursor.execute(
        """
        SELECT DISTINCT
            sfo.FieldCode,
            sfo.OptionValue,
            sfo.SeriesCode,
            sfo.WorkbookName,
            sfo.WorksheetName
        FROM cfg.SeriesFieldOption AS sfo
        WHERE sfo.PumpFamilyId = ?
          AND sfo.MetadataPublicationId = ?
          AND sfo.IsActive = 1
        ORDER BY sfo.SeriesCode, sfo.FieldCode, sfo.OptionValue;
        """,
        pump_family_id, publication_id,
    ).fetchall()
    return [
        {
            "field_code": r.FieldCode, "option_value": r.OptionValue, "series_code": r.SeriesCode,
            "source_workbook": r.WorkbookName, "source_worksheet": r.WorksheetName,
        }
        for r in rows
    ]


def fetch_field_option_dependencies(cursor, pump_family_id: int, publication_id: int) -> list[dict[str, Any]]:
    """SourceWorkbook/SourceWorksheet/SourceReference verified against
    sql/15_Create_Field_Option_Dependency_Metadata.sql."""
    rows = cursor.execute(
        """
        SELECT
            dependency.TargetFieldCode,
            dependency.TargetDisplayValue,
            dependency.TargetIdentifierCode,
            dependency.SeriesCode,
            dependency.ContextJson,
            dependency.IsActive,
            dependency.SourceWorkbook,
            dependency.SourceWorksheet,
            dependency.SourceReference
        FROM cfg.FieldOptionDependency AS dependency
        WHERE dependency.PumpFamilyId = ?
          AND dependency.MetadataPublicationId = ?
          AND dependency.IsActive = 1
        ORDER BY dependency.TargetFieldCode, dependency.SeriesCode;
        """,
        pump_family_id, publication_id,
    ).fetchall()
    return [
        {
            "target_field_code": r.TargetFieldCode,
            "target_display_value": r.TargetDisplayValue,
            "target_identifier_code": r.TargetIdentifierCode,
            "series_code": r.SeriesCode,
            "context_json": r.ContextJson,
            "is_active": bool(r.IsActive),
            "source_workbook": r.SourceWorkbook,
            "source_worksheet": r.SourceWorksheet,
            "source_reference": r.SourceReference,
        }
        for r in rows
    ]


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    evidence_dir = repo_root / "docs" / "evidence" / "F120"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    connection_string = build_connection_string(repo_root)
    connection = pyodbc.connect(connection_string, autocommit=True)
    try:
        cursor = connection.cursor()

        pub_row = get_active_publication_id(cursor)
        publication_id = int(pub_row[0])
        pump_family_id = get_pump_family_id(cursor, FAMILY_CODE)

        attribute_values = fetch_attribute_values(cursor, pump_family_id, publication_id)
        series_field_options = fetch_series_field_options(cursor, pump_family_id, publication_id)
        field_option_dependencies = fetch_field_option_dependencies(cursor, pump_family_id, publication_id)

    finally:
        connection.close()

    result = {
        "artifact": "FYBROC_SQL_METADATA_SNAPSHOT",
        "step": STEP,
        "roadmap_version": ROADMAP_VERSION,
        "milestone": MILESTONE,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "family_code": FAMILY_CODE,
        "pump_family_id": pump_family_id,
        "active_metadata_publication_id": publication_id,
        "active_publication_version_code": pub_row[1],
        "active_publication_description": pub_row[2],
        "active_publication_created_at": str(pub_row[3]) if pub_row[3] else None,
        "active_publication_activated_at": str(pub_row[4]) if pub_row[4] else None,
        "counts": {
            "attribute_values": len(attribute_values),
            "series_field_options": len(series_field_options),
            "field_option_dependencies": len(field_option_dependencies),
        },
        "attribute_values": attribute_values,
        "series_field_options": series_field_options,
        "field_option_dependencies": field_option_dependencies,
    }

    output_path = evidence_dir / "FYBROC_SQL_METADATA_SNAPSHOT.json"
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print(json.dumps({
        "step": STEP,
        "output_path": str(output_path),
        "active_metadata_publication_id": publication_id,
        "counts": result["counts"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

import pyodbc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--file",
        type=Path,
        default=Path(
            "exports/fybroc_dependency_candidates.csv"
        ),
    )
    parser.add_argument("--publication-id", type=int, required=True)
    parser.add_argument(
        "--server",
        default=os.getenv("DB_SERVER", "localhost"),
    )
    parser.add_argument(
        "--database",
        default=os.getenv(
            "DB_DATABASE",
            "PumpConfiguratorDB",
        ),
    )
    parser.add_argument(
        "--driver",
        default=os.getenv(
            "DB_DRIVER",
            "ODBC Driver 18 for SQL Server",
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_file = args.file.resolve()

    with source_file.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        raise SystemExit("Dependency candidate file has no rows.")

    connection_string = (
        f"DRIVER={{{args.driver}}};"
        f"SERVER={args.server};"
        f"DATABASE={args.database};"
        "Trusted_Connection=yes;"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
    )

    connection = pyodbc.connect(
        connection_string,
        autocommit=False,
    )

    try:
        cursor = connection.cursor()

        family_row = cursor.execute(
            """
            SELECT PumpFamilyId
            FROM cfg.PumpFamily
            WHERE FamilyCode = 'FYBROC';
            """
        ).fetchone()

        if family_row is None:
            raise RuntimeError("FYBROC pump family was not found.")

        family_id = int(family_row[0])

        publication = cursor.execute(
            """
            SELECT MetadataPublicationId
            FROM cfg.MetadataPublication
            WHERE MetadataPublicationId = ?;
            """,
            args.publication_id,
        ).fetchone()

        if publication is None:
            raise RuntimeError("Metadata publication was not found.")

        batch_id = int(
            cursor.execute(
                """
                INSERT INTO stg.FieldOptionDependencyImportBatch
                (
                    FamilyCode,
                    SourceFile,
                    ExpectedRowCount,
                    Status
                )
                OUTPUT INSERTED.FieldOptionDependencyImportBatchId
                VALUES ('FYBROC', ?, ?, 'Loading');
                """,
                str(source_file),
                len(rows),
            ).fetchone()[0]
        )
        connection.commit()

        insert_sql = """
        INSERT INTO stg.FieldOptionDependencyImport
        (
            FieldOptionDependencyImportBatchId,
            FamilyCode,
            DependencyCode,
            TargetFieldCode,
            TargetDisplayValue,
            TargetIdentifierCode,
            SeriesCode,
            ContextJson,
            SourceWorkbook,
            SourceWorksheet,
            SourceReference
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """

        payload = [
            (
                batch_id,
                row["family_code"],
                row["dependency_code"],
                row["target_field_code"],
                row["target_display_value"],
                row["target_identifier_code"] or None,
                row["series_code"] or None,
                row["context_json"],
                row["source_workbook"],
                row["source_worksheet"],
                row["source_reference"],
            )
            for row in rows
        ]

        cursor.fast_executemany = True
        cursor.executemany(insert_sql, payload)

        cursor.execute(
            """
            UPDATE stg.FieldOptionDependencyImportBatch
            SET LoadedRowCount = ?,
                Status = 'Loaded',
                CompletedAt = SYSUTCDATETIME()
            WHERE FieldOptionDependencyImportBatchId = ?;
            """,
            len(payload),
            batch_id,
        )

        cursor.execute(
            """
            DELETE FROM cfg.FieldOptionDependency
            WHERE MetadataPublicationId = ?
              AND PumpFamilyId = ?;
            """,
            args.publication_id,
            family_id,
        )

        cursor.execute(
            """
            INSERT INTO cfg.FieldOptionDependency
            (
                MetadataPublicationId,
                PumpFamilyId,
                DependencyCode,
                TargetFieldCode,
                TargetDisplayValue,
                TargetIdentifierCode,
                SeriesCode,
                ContextJson,
                SourceWorkbook,
                SourceWorksheet,
                SourceReference
            )
            SELECT
                ?, ?,
                DependencyCode,
                TargetFieldCode,
                TargetDisplayValue,
                TargetIdentifierCode,
                SeriesCode,
                ContextJson,
                SourceWorkbook,
                SourceWorksheet,
                SourceReference
            FROM stg.FieldOptionDependencyImport
            WHERE FieldOptionDependencyImportBatchId = ?;
            """,
            args.publication_id,
            family_id,
            batch_id,
        )

        connection.commit()

        print(f"Dependency batch: {batch_id}")
        print(f"Relations loaded: {len(payload):,}")
        print(
            "Published to metadata publication: "
            f"{args.publication_id}"
        )

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()

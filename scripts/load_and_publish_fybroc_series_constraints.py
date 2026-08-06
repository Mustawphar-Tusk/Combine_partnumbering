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
            "exports/fybroc_series_constraint_candidates.csv"
        ),
    )
    parser.add_argument(
        "--publication-id",
        type=int,
        required=True,
    )
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

    if not source_file.exists():
        raise SystemExit(
            f"Candidate file not found: {source_file}"
        )

    with source_file.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        raise SystemExit(
            "Constraint candidate file has no rows."
        )

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

        publication = cursor.execute(
            """
            SELECT Status
            FROM cfg.MetadataPublication
            WHERE MetadataPublicationId = ?;
            """,
            args.publication_id,
        ).fetchone()

        if publication is None:
            raise RuntimeError(
                "Metadata publication was not found."
            )

        family = cursor.execute(
            """
            SELECT PumpFamilyId
            FROM cfg.PumpFamily
            WHERE FamilyCode = 'FYBROC';
            """
        ).fetchone()

        if family is None:
            raise RuntimeError(
                "FYBROC pump family was not found."
            )

        pump_family_id = int(family[0])

        batch_id = int(
            cursor.execute(
                """
                INSERT INTO stg.SeriesFieldOptionImportBatch
                (
                    FamilyCode,
                    SourceFile,
                    ExpectedRowCount,
                    Status
                )
                OUTPUT INSERTED.SeriesFieldOptionImportBatchId
                VALUES ('FYBROC', ?, ?, 'Loading');
                """,
                str(source_file),
                len(rows),
            ).fetchone()[0]
        )
        connection.commit()

        stage_sql = """
        INSERT INTO stg.SeriesFieldOptionImport
        (
            SeriesFieldOptionImportBatchId,
            FamilyCode,
            SourceFieldCode,
            FieldCode,
            OptionValue,
            SeriesCode,
            WorkbookName,
            WorksheetName,
            SourceRow,
            SourceFieldCell,
            SourceValueCell,
            SourceSeriesCell,
            SourceProfile
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """

        payload = [
            (
                batch_id,
                row["family_code"],
                row["source_field_code"],
                row["field_code"],
                row["option_value"],
                row["series_code"],
                row["workbook_name"],
                row["worksheet_name"],
                int(row["source_row"]),
                row["source_field_cell"],
                row["source_value_cell"],
                row["source_series_cell"],
                row["source_profile"],
            )
            for row in rows
        ]

        cursor.fast_executemany = True
        cursor.executemany(
            stage_sql,
            payload,
        )

        cursor.execute(
            """
            UPDATE stg.SeriesFieldOptionImportBatch
            SET LoadedRowCount = ?,
                Status = 'Loaded',
                CompletedAt = SYSUTCDATETIME()
            WHERE SeriesFieldOptionImportBatchId = ?;
            """,
            len(payload),
            batch_id,
        )

        cursor.execute(
            """
            DELETE FROM cfg.SeriesFieldOption
            WHERE MetadataPublicationId = ?
              AND PumpFamilyId = ?;
            """,
            args.publication_id,
            pump_family_id,
        )

        cursor.execute(
            """
            INSERT INTO cfg.SeriesFieldOption
            (
                MetadataPublicationId,
                PumpFamilyId,
                SourceFieldCode,
                FieldCode,
                OptionValue,
                SeriesCode,
                WorkbookName,
                WorksheetName,
                SourceRow,
                SourceFieldCell,
                SourceValueCell,
                SourceSeriesCell
            )
            SELECT
                ?,
                ?,
                SourceFieldCode,
                FieldCode,
                OptionValue,
                SeriesCode,
                WorkbookName,
                WorksheetName,
                SourceRow,
                SourceFieldCell,
                SourceValueCell,
                SourceSeriesCell
            FROM stg.SeriesFieldOptionImport
            WHERE SeriesFieldOptionImportBatchId = ?;
            """,
            args.publication_id,
            pump_family_id,
            batch_id,
        )

        connection.commit()

        print(f"Import batch: {batch_id}")
        print(f"Relations loaded: {len(payload)}")
        print(
            f"Published to metadata publication: "
            f"{args.publication_id}"
        )

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()

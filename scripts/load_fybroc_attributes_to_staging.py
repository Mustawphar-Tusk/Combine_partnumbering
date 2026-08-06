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
        default=Path("exports/fybroc_attribute_candidates.csv"),
    )
    parser.add_argument("--server", default=os.getenv("DB_SERVER", "localhost"))
    parser.add_argument(
        "--database",
        default=os.getenv("DB_DATABASE", "PumpConfiguratorDB"),
    )
    parser.add_argument(
        "--driver",
        default=os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server"),
    )
    return parser.parse_args()


def connection_string(args: argparse.Namespace) -> str:
    return (
        f"DRIVER={{{args.driver}}};SERVER={args.server};"
        f"DATABASE={args.database};Trusted_Connection=yes;"
        "Encrypt=yes;TrustServerCertificate=yes;"
    )


def main() -> None:
    args = parse_args()
    source_file = args.file.resolve()

    if not source_file.exists():
        raise SystemExit(f"File not found: {source_file}")

    with source_file.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        raise SystemExit("Attribute candidate file has no rows.")

    family_codes = {row["family_code"] for row in rows}
    if family_codes != {"FYBROC"}:
        raise SystemExit(
            f"Expected only FYBROC rows; found {sorted(family_codes)}."
        )

    connection = pyodbc.connect(
        connection_string(args),
        autocommit=False,
    )

    try:
        cursor = connection.cursor()

        output = cursor.execute(
            """
            DECLARE @BatchId bigint;
            EXEC stg.usp_CreateAttributeImportBatch
                @FamilyCode = ?,
                @SourceFile = ?,
                @ExpectedRowCount = ?,
                @AttributeValueImportBatchId = @BatchId OUTPUT;
            SELECT @BatchId;
            """,
            "FYBROC",
            str(source_file),
            len(rows),
        ).fetchone()

        batch_id = int(output[0])
        connection.commit()

        insert_sql = """
        INSERT INTO stg.AttributeValueImport
        (
            AttributeValueImportBatchId,
            FamilyCode,
            WorkbookRole,
            WorkbookName,
            WorksheetName,
            FieldCode,
            FieldName,
            DisplayValue,
            IdentifierCode,
            DisplayOrder,
            SourceDisplayCell,
            SourceCodeCell,
            SourceProfile
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """

        payload = [
            (
                batch_id,
                row["family_code"],
                row["workbook_role"],
                row["workbook_name"],
                row["worksheet_name"],
                row["field_code"],
                row["field_name"],
                row["display_value"],
                row["identifier_code"],
                int(row["display_order"]),
                row["source_display_cell"],
                row["source_code_cell"],
                row["source_profile"],
            )
            for row in rows
        ]

        cursor.fast_executemany = True
        cursor.executemany(insert_sql, payload)

        cursor.execute(
            """
            EXEC stg.usp_CompleteAttributeImportBatch
                @AttributeValueImportBatchId = ?,
                @LoadedRowCount = ?,
                @Status = 'Loaded',
                @ErrorMessage = NULL;
            """,
            batch_id,
            len(payload),
        )

        connection.commit()

        print(f"Attribute import batch: {batch_id}")
        print(f"Expected rows: {len(rows)}")
        print(f"Loaded rows: {len(payload)}")
        print("Status: Loaded")

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()

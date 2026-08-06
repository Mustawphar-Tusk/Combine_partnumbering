from __future__ import annotations

import argparse
import csv
import hashlib
import os
from pathlib import Path
from typing import Iterable

import pyodbc


REQUIRED_COLUMNS = {
    "family_code",
    "workbook_role",
    "workbook_name",
    "worksheet_name",
    "segment_code",
    "segment_name",
    "source_row",
    "source_id",
    "segment_value",
    "expected_width",
    "combination_key",
    "selections_json",
    "source_cells_json",
    "source_profile",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--file",
        type=Path,
        default=Path("exports/segment_combination_candidates.csv"),
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
    parser.add_argument("--batch-size", type=int, default=2000)
    parser.add_argument("--replace-existing", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_header(path: Path) -> None:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
    missing = REQUIRED_COLUMNS - columns
    if missing:
        raise ValueError(
            "CSV is missing required columns: " + ", ".join(sorted(missing))
        )


def count_rows(path: Path) -> int:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def row_batches(
    path: Path,
    import_batch_id: int,
    batch_size: int,
) -> Iterable[list[tuple]]:
    batch: list[tuple] = []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            batch.append(
                (
                    import_batch_id,
                    row["family_code"],
                    row["workbook_role"],
                    row["workbook_name"],
                    row["worksheet_name"],
                    row["segment_code"],
                    row["segment_name"],
                    int(row["source_row"]),
                    int(row["source_id"]),
                    row["segment_value"],
                    int(row["expected_width"]),
                    row["combination_key"],
                    row["selections_json"],
                    row["source_cells_json"],
                    row["source_profile"],
                )
            )
            if len(batch) >= batch_size:
                yield batch
                batch = []
    if batch:
        yield batch


def connection_string(server: str, database: str, driver: str) -> str:
    return (
        f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
        "Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;"
    )


def main() -> None:
    args = parse_args()
    source_file = args.file.resolve()

    if not source_file.exists():
        raise SystemExit(f"CSV file not found: {source_file}")

    validate_header(source_file)
    expected_count = count_rows(source_file)
    source_hash = sha256_file(source_file)
    family_code = "FYBROC"

    connection = pyodbc.connect(
        connection_string(args.server, args.database, args.driver),
        autocommit=False,
    )

    try:
        cursor = connection.cursor()

        existing = cursor.execute(
            """
            SELECT ImportBatchId
            FROM stg.SegmentCombinationImportBatch
            WHERE FamilyCode = ? AND SourceFileHash = ?;
            """,
            family_code,
            source_hash,
        ).fetchone()

        if existing:
            existing_id = int(existing[0])
            if not args.replace_existing:
                raise SystemExit(
                    f"This exact CSV is already loaded as batch {existing_id}. "
                    "Use --replace-existing to reload it."
                )
            cursor.execute(
                "DELETE FROM stg.SegmentCombinationImport WHERE ImportBatchId = ?;",
                existing_id,
            )
            cursor.execute(
                "DELETE FROM stg.SegmentCombinationImportBatch WHERE ImportBatchId = ?;",
                existing_id,
            )
            connection.commit()

        batch_id = int(
            cursor.execute(
                """
                INSERT INTO stg.SegmentCombinationImportBatch
                (
                    FamilyCode,
                    SourceFile,
                    SourceFileHash,
                    ExpectedRowCount,
                    Status
                )
                OUTPUT INSERTED.ImportBatchId
                VALUES (?, ?, ?, ?, 'Loading');
                """,
                family_code,
                str(source_file),
                source_hash,
                expected_count,
            ).fetchone()[0]
        )
        connection.commit()

        insert_sql = """
        INSERT INTO stg.SegmentCombinationImport
        (
            ImportBatchId,
            FamilyCode,
            WorkbookRole,
            WorkbookName,
            WorksheetName,
            SegmentCode,
            SegmentName,
            SourceRow,
            SourceId,
            SegmentValue,
            ExpectedWidth,
            CombinationKey,
            SelectionsJson,
            SourceCellsJson,
            SourceProfile
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """

        cursor.fast_executemany = True
        loaded_count = 0

        for batch in row_batches(source_file, batch_id, args.batch_size):
            cursor.executemany(insert_sql, batch)
            connection.commit()
            loaded_count += len(batch)
            print(
                f"Loaded {loaded_count:,} of {expected_count:,} rows...",
                flush=True,
            )

        status = "Loaded" if loaded_count == expected_count else "Failed"
        error_message = (
            None
            if status == "Loaded"
            else "Loaded row count does not match expected row count."
        )

        cursor.execute(
            """
            UPDATE stg.SegmentCombinationImportBatch
            SET LoadedRowCount = ?,
                Status = ?,
                CompletedAt = SYSUTCDATETIME(),
                ErrorMessage = ?
            WHERE ImportBatchId = ?;
            """,
            loaded_count,
            status,
            error_message,
            batch_id,
        )
        connection.commit()

        print()
        print(f"Import batch: {batch_id}")
        print(f"Expected rows: {expected_count:,}")
        print(f"Loaded rows: {loaded_count:,}")

        rows = cursor.execute(
            """
            SELECT
                SegmentCode,
                SegmentRowCount,
                MinimumSourceId,
                MaximumSourceId,
                FirstSourceRow,
                LastSourceRow,
                InvalidWidthCount,
                InvalidSelectionsJsonCount
            FROM stg.vw_SegmentCombinationImportValidation
            WHERE ImportBatchId = ?
            ORDER BY SegmentCode;
            """,
            batch_id,
        ).fetchall()

        print()
        print("Validation summary:")
        for row in rows:
            print(
                f"{row.SegmentCode}: "
                f"{int(row.SegmentRowCount):,} rows, "
                f"IDs {row.MinimumSourceId}-{row.MaximumSourceId}, "
                f"source rows {row.FirstSourceRow}-{row.LastSourceRow}, "
                f"invalid widths {row.InvalidWidthCount}, "
                f"invalid JSON {row.InvalidSelectionsJsonCount}"
            )
    finally:
        connection.close()


if __name__ == "__main__":
    main()

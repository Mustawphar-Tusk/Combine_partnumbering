from __future__ import annotations

import pyodbc


def get_runtime_revision(
    connection_string: str,
    *,
    family_code: str,
    metadata_publication_id: int,
) -> str:
    connection = pyodbc.connect(
        connection_string,
        autocommit=True,
    )

    try:
        cursor = connection.cursor()

        def latest(
            table: str,
            id_column: str,
        ) -> int:
            row = cursor.execute(
                f"""
                SELECT TOP (1) {id_column}
                FROM {table}
                WHERE FamilyCode = ?
                  AND Status IN ('Loaded', 'Validated')
                ORDER BY {id_column} DESC;
                """,
                family_code,
            ).fetchone()

            if row is None:
                raise RuntimeError(
                    f"No loaded batch exists in {table} "
                    f"for {family_code}."
                )

            return int(row[0])

        series_batch = latest(
            "stg.SeriesFieldOptionImportBatch",
            "SeriesFieldOptionImportBatchId",
        )
        combination_batch = latest(
            "stg.SegmentCombinationImportBatch",
            "ImportBatchId",
        )
        dependency_batch = latest(
            "stg.FieldOptionDependencyImportBatch",
            "FieldOptionDependencyImportBatchId",
        )

        return (
            f"publication:{metadata_publication_id};"
            f"series-batch:{series_batch};"
            f"combination-batch:{combination_batch};"
            f"dependency-batch:{dependency_batch}"
        )

    finally:
        connection.close()

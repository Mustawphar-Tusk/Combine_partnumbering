from __future__ import annotations

import json
from typing import Any

import pyodbc

from src.configuration_engine.models import (
    ResolvedConfigurationSegment,
)
from src.configuration_engine.normalization import (
    build_combination_key,
)


class SqlConfigurationRepository:
    def __init__(
        self,
        connection_string: str,
        segment_field_order: dict[str, tuple[str, ...]],
        import_batch_id: int | None = None,
    ) -> None:
        self.connection_string = connection_string
        self.segment_field_order = segment_field_order
        self.import_batch_id = import_batch_id

    def _latest_batch_id(
        self,
        cursor: pyodbc.Cursor,
        family_code: str,
    ) -> int:
        if self.import_batch_id is not None:
            return self.import_batch_id

        row = cursor.execute(
            """
            SELECT TOP (1) ImportBatchId
            FROM stg.SegmentCombinationImportBatch
            WHERE FamilyCode = ?
              AND Status IN ('Loaded', 'Validated')
            ORDER BY ImportBatchId DESC;
            """,
            family_code,
        ).fetchone()

        if row is None:
            raise RuntimeError(
                f"No loaded staging batch exists for {family_code}."
            )

        return int(row[0])

    def resolve_combination_segment(
        self,
        *,
        family_code: str,
        segment_code: str,
        selections: dict[str, str],
    ) -> ResolvedConfigurationSegment | None:
        field_order = self.segment_field_order.get(segment_code)

        if field_order is None:
            raise KeyError(
                f"No field order is configured for {segment_code}."
            )

        combination_key = build_combination_key(
            selections,
            field_order,
        )

        connection = pyodbc.connect(
            self.connection_string,
            autocommit=True,
        )

        try:
            cursor = connection.cursor()
            batch_id = self._latest_batch_id(
                cursor,
                family_code,
            )

            rows = cursor.execute(
                """
                SELECT TOP (2)
                    SourceId,
                    SegmentValue
                FROM stg.SegmentCombinationImport
                WHERE ImportBatchId = ?
                  AND FamilyCode = ?
                  AND SegmentCode = ?
                  AND CombinationKeyHash =
                      CONVERT
                      (
                          binary(32),
                          HASHBYTES
                          (
                              'SHA2_256',
                              CONVERT(varbinary(max), ?)
                          )
                      )
                  AND CombinationKey = ?
                ORDER BY SourceId;
                """,
                batch_id,
                family_code,
                segment_code,
                combination_key,
                combination_key,
            ).fetchall()

            if not rows:
                return None

            if len(rows) > 1:
                raise RuntimeError(
                    f"Multiple {segment_code} combinations matched."
                )

            return ResolvedConfigurationSegment(
                segment_code=segment_code,
                segment_value=str(rows[0].SegmentValue),
                source_id=int(rows[0].SourceId),
                resolution_type="COMBINATION",
            )

        finally:
            connection.close()

from __future__ import annotations

from dataclasses import dataclass

import pyodbc


@dataclass(frozen=True)
class AvailableOption:
    field_code: str
    display_value: str


class SqlConstraintProjectionRepository:
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
                f"No loaded combination batch exists for {family_code}."
            )

        return int(row[0])

    def available_combination_values(
        self,
        *,
        family_code: str,
        segment_code: str,
        target_field_code: str,
        current_selections: dict[str, str],
    ) -> tuple[AvailableOption, ...]:
        field_order = self.segment_field_order.get(segment_code)

        if field_order is None:
            raise KeyError(
                f"No field order is configured for {segment_code}."
            )

        if target_field_code not in field_order:
            raise KeyError(
                f"{target_field_code} is not part of {segment_code}."
            )

        invalid_fields = [
            field
            for field in current_selections
            if field not in field_order
        ]
        if invalid_fields:
            raise ValueError(
                "Unexpected fields for "
                f"{segment_code}: {', '.join(invalid_fields)}"
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

            predicates = [
                "ImportBatchId = ?",
                "FamilyCode = ?",
                "SegmentCode = ?",
            ]
            parameters: list[object] = [
                batch_id,
                family_code,
                segment_code,
            ]

            for field_code, value in current_selections.items():
                if field_code == target_field_code:
                    continue

                predicates.append(
                    "JSON_VALUE(SelectionsJson, ?) = ?"
                )
                parameters.extend(
                    [
                        f'$.\"{field_code}\"',
                        str(value).strip(),
                    ]
                )

            target_path = f'$.\"{target_field_code}\"'

            sql = f"""
            SELECT DISTINCT
                JSON_VALUE(SelectionsJson, ?) AS DisplayValue
            FROM stg.SegmentCombinationImport
            WHERE {' AND '.join(predicates)}
              AND JSON_VALUE(SelectionsJson, ?) IS NOT NULL
            ORDER BY DisplayValue;
            """

            rows = cursor.execute(
                sql,
                target_path,
                *parameters,
                target_path,
            ).fetchall()

            return tuple(
                AvailableOption(
                    field_code=target_field_code,
                    display_value=str(row.DisplayValue),
                )
                for row in rows
            )

        finally:
            connection.close()

    def validate_partial_combination(
        self,
        *,
        family_code: str,
        segment_code: str,
        current_selections: dict[str, str],
    ) -> bool:
        field_order = self.segment_field_order.get(segment_code)

        if field_order is None:
            raise KeyError(
                f"No field order is configured for {segment_code}."
            )

        invalid_fields = [
            field
            for field in current_selections
            if field not in field_order
        ]
        if invalid_fields:
            raise ValueError(
                "Unexpected fields for "
                f"{segment_code}: {', '.join(invalid_fields)}"
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

            predicates = [
                "ImportBatchId = ?",
                "FamilyCode = ?",
                "SegmentCode = ?",
            ]
            parameters: list[object] = [
                batch_id,
                family_code,
                segment_code,
            ]

            for field_code, value in current_selections.items():
                predicates.append(
                    "JSON_VALUE(SelectionsJson, ?) = ?"
                )
                parameters.extend(
                    [
                        f'$.\"{field_code}\"',
                        str(value).strip(),
                    ]
                )

            row = cursor.execute(
                f"""
                SELECT TOP (1) 1
                FROM stg.SegmentCombinationImport
                WHERE {' AND '.join(predicates)};
                """,
                *parameters,
            ).fetchone()

            return row is not None

        finally:
            connection.close()


class SqlAttributeProjectionRepository:
    def __init__(
        self,
        connection_string: str,
        metadata_publication_id: int,
    ) -> None:
        self.connection_string = connection_string
        self.metadata_publication_id = metadata_publication_id

    def available_attribute_values(
        self,
        *,
        family_code: str,
        field_code: str,
    ) -> tuple[AvailableOption, ...]:
        connection = pyodbc.connect(
            self.connection_string,
            autocommit=True,
        )

        try:
            rows = connection.cursor().execute(
                """
                SELECT
                    av.DisplayValue
                FROM cfg.AttributeValue AS av
                INNER JOIN cfg.PumpFamily AS pf
                    ON pf.PumpFamilyId = av.PumpFamilyId
                WHERE av.MetadataPublicationId = ?
                  AND pf.FamilyCode = ?
                  AND av.FieldCode = ?
                  AND av.IsActive = 1
                ORDER BY av.DisplayOrder, av.DisplayValue;
                """,
                self.metadata_publication_id,
                family_code,
                field_code,
            ).fetchall()

            return tuple(
                AvailableOption(
                    field_code=field_code,
                    display_value=str(row.DisplayValue),
                )
                for row in rows
            )

        finally:
            connection.close()

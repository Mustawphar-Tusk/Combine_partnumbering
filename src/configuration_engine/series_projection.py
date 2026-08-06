from __future__ import annotations

from dataclasses import dataclass

import pyodbc


@dataclass(frozen=True)
class SeriesAllowedOption:
    field_code: str
    option_value: str
    series_code: str


class SqlSeriesConstraintRepository:
    def __init__(
        self,
        connection_string: str,
        metadata_publication_id: int,
    ) -> None:
        self.connection_string = connection_string
        self.metadata_publication_id = (
            metadata_publication_id
        )

    def available_values(
        self,
        *,
        family_code: str,
        series_code: str,
        field_code: str,
    ) -> tuple[SeriesAllowedOption, ...]:
        connection = pyodbc.connect(
            self.connection_string,
            autocommit=True,
        )

        try:
            rows = connection.cursor().execute(
                """
                SELECT DISTINCT
                    sfo.FieldCode,
                    sfo.OptionValue,
                    sfo.SeriesCode
                FROM cfg.SeriesFieldOption AS sfo
                INNER JOIN cfg.PumpFamily AS pf
                    ON pf.PumpFamilyId = sfo.PumpFamilyId
                WHERE sfo.MetadataPublicationId = ?
                  AND pf.FamilyCode = ?
                  AND sfo.SeriesCode = ?
                  AND sfo.FieldCode = ?
                  AND sfo.IsActive = 1
                ORDER BY sfo.OptionValue;
                """,
                self.metadata_publication_id,
                family_code,
                series_code,
                field_code,
            ).fetchall()

            return tuple(
                SeriesAllowedOption(
                    field_code=str(row.FieldCode),
                    option_value=str(row.OptionValue),
                    series_code=str(row.SeriesCode),
                )
                for row in rows
            )

        finally:
            connection.close()

    def is_allowed(
        self,
        *,
        family_code: str,
        series_code: str,
        field_code: str,
        option_value: str,
    ) -> bool:
        return any(
            row.option_value == option_value
            for row in self.available_values(
                family_code=family_code,
                series_code=series_code,
                field_code=field_code,
            )
        )

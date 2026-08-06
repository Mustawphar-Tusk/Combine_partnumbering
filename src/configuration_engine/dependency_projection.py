from __future__ import annotations

import json
from dataclasses import dataclass

import pyodbc


@dataclass(frozen=True)
class DependencyOption:
    display_value: str
    identifier_code: str | None


class SqlFieldDependencyRepository:
    def __init__(
        self,
        *,
        connection_string: str,
        metadata_publication_id: int,
        dependency_field_aliases: dict[str, str],
    ) -> None:
        self.connection_string = connection_string
        self.metadata_publication_id = metadata_publication_id
        self.dependency_field_aliases = {
            field.strip().upper(): source.strip().upper()
            for field, source in dependency_field_aliases.items()
        }

    def applies_to(self, target_field_code: str) -> bool:
        return (
            target_field_code.strip().upper()
            in self.dependency_field_aliases
        )

    def available_values(
        self,
        *,
        family_code: str,
        target_field_code: str,
        series_code: str | None,
        current_selections: dict[str, str],
    ) -> tuple[DependencyOption, ...]:
        target = target_field_code.strip().upper()
        source_target = self.dependency_field_aliases[target]

        connection = pyodbc.connect(
            self.connection_string,
            autocommit=True,
        )

        try:
            rows = connection.cursor().execute(
                """
                SELECT
                    dependency.TargetDisplayValue,
                    dependency.TargetIdentifierCode,
                    dependency.ContextJson
                FROM cfg.FieldOptionDependency AS dependency
                INNER JOIN cfg.PumpFamily AS family
                    ON family.PumpFamilyId =
                       dependency.PumpFamilyId
                WHERE dependency.MetadataPublicationId = ?
                  AND family.FamilyCode = ?
                  AND dependency.TargetFieldCode = ?
                  AND dependency.IsActive = 1
                  AND (
                        dependency.SeriesCode IS NULL
                        OR dependency.SeriesCode = ?
                  );
                """,
                self.metadata_publication_id,
                family_code,
                source_target,
                series_code,
            ).fetchall()

        finally:
            connection.close()

        matched: dict[str, DependencyOption] = {}

        for row in rows:
            context = json.loads(str(row.ContextJson))

            if not all(
                current_selections.get(field) == value
                for field, value in context.items()
            ):
                continue

            display_value = str(row.TargetDisplayValue)
            identifier_code = (
                str(row.TargetIdentifierCode)
                if row.TargetIdentifierCode is not None
                else None
            )
            matched.setdefault(
                display_value,
                DependencyOption(
                    display_value=display_value,
                    identifier_code=identifier_code,
                ),
            )

        options = tuple(matched.values())

        if target.startswith("MOTOR_MODIFICATION_"):
            return self._apply_modification_sequence(
                target_field_code=target,
                options=options,
                current_selections=current_selections,
            )

        return tuple(
            sorted(
                options,
                key=lambda option: option.display_value.casefold(),
            )
        )

    @staticmethod
    def _apply_modification_sequence(
        *,
        target_field_code: str,
        options: tuple[DependencyOption, ...],
        current_selections: dict[str, str],
    ) -> tuple[DependencyOption, ...]:
        slot = int(target_field_code.rsplit("_", 1)[1])
        previous_fields = [
            f"MOTOR_MODIFICATION_{index}"
            for index in range(1, slot)
        ]
        previous_values = [
            current_selections[field]
            for field in previous_fields
            if field in current_selections
        ]

        option_by_value = {
            option.display_value: option
            for option in options
        }
        no_modification = option_by_value.get(
            "No Modification"
        )

        if (
            "No Modification" in previous_values
            and no_modification is not None
        ):
            return (no_modification,)

        selected = set(previous_values)
        previous_codes = [
            option_by_value[value].identifier_code
            for value in previous_values
            if (
                value in option_by_value
                and option_by_value[value].identifier_code
            )
        ]
        minimum_code = (
            previous_codes[-1]
            if previous_codes
            else None
        )

        filtered: list[DependencyOption] = []

        for option in options:
            if option.display_value in selected:
                continue

            if option.display_value == "No Modification":
                filtered.append(option)
                continue

            if (
                minimum_code is not None
                and option.identifier_code is not None
                and option.identifier_code <= minimum_code
            ):
                continue

            filtered.append(option)

        return tuple(
            sorted(
                filtered,
                key=lambda option: (
                    option.identifier_code or "",
                    option.display_value.casefold(),
                ),
            )
        )

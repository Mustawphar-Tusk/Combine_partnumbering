from __future__ import annotations

from src.repositories.sql_configuration_repository import (
    SqlConfigurationRepository,
)


class CombinationResolverAdapter:
    def __init__(
        self,
        repository: SqlConfigurationRepository,
    ) -> None:
        self.repository = repository

    def resolve(
        self,
        *,
        family_code: str,
        segment_code: str,
        payload,
    ):
        if not isinstance(payload, dict):
            raise TypeError(
                f"{segment_code} requires a selection dictionary."
            )

        return self.repository.resolve_combination_segment(
            family_code=family_code,
            segment_code=segment_code,
            selections=payload,
        )

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.configuration_engine.value_normalization import (
    normalize_engineering_value,
)


@dataclass(frozen=True)
class ValueEquivalenceProfile:
    family_code: str
    aliases: dict[str, dict[str, str]]
    combination_passthrough: dict[str, frozenset[str]]

    @classmethod
    def from_mapping(
        cls,
        mapping: dict[str, Any],
    ) -> "ValueEquivalenceProfile":
        family_code = str(
            mapping["family_code"]
        ).strip().upper()

        aliases: dict[str, dict[str, str]] = {}
        passthrough: dict[str, frozenset[str]] = {}

        for raw_field, configuration in mapping.get(
            "fields",
            {},
        ).items():
            field = str(raw_field).strip().upper()
            field_aliases: dict[str, str] = {}

            for group in configuration.get(
                "equivalence_groups",
                [],
            ):
                canonical = (
                    "equivalence:"
                    + normalize_engineering_value(
                        str(group["canonical_key"])
                    )
                )

                for raw_value in group.get("values", []):
                    key = normalize_engineering_value(
                        str(raw_value)
                    )
                    existing = field_aliases.get(key)

                    if (
                        existing is not None
                        and existing != canonical
                    ):
                        raise ValueError(
                            f"Conflicting equivalence mapping for "
                            f"{field}='{raw_value}'."
                        )

                    field_aliases[key] = canonical

            aliases[field] = field_aliases
            passthrough[field] = frozenset(
                normalize_engineering_value(
                    str(value)
                )
                for value in configuration.get(
                    "combination_passthrough_values",
                    [],
                )
            )

        return cls(
            family_code=family_code,
            aliases=aliases,
            combination_passthrough=passthrough,
        )

    def canonical_key(
        self,
        *,
        field_code: str,
        raw_value: str,
        fallback_key: str,
    ) -> str:
        field = field_code.strip().upper()
        normalized = normalize_engineering_value(
            raw_value
        )

        return self.aliases.get(
            field,
            {},
        ).get(
            normalized,
            fallback_key,
        )

    def is_combination_passthrough(
        self,
        *,
        field_code: str,
        raw_value: str,
    ) -> bool:
        field = field_code.strip().upper()
        normalized = normalize_engineering_value(
            raw_value
        )

        return normalized in self.combination_passthrough.get(
            field,
            frozenset(),
        )

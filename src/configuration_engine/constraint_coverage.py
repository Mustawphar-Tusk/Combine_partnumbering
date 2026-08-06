from __future__ import annotations

from dataclasses import dataclass


class ConstraintCoverageError(RuntimeError):
    """Raised when a navigation field lacks authoritative coverage."""


@dataclass(frozen=True)
class ConstraintCoveragePolicy:
    family_code: str
    required_fields: dict[str, str]

    @classmethod
    def from_mapping(
        cls,
        mapping: dict,
    ) -> "ConstraintCoveragePolicy":
        return cls(
            family_code=str(
                mapping["family_code"]
            ).upper(),
            required_fields={
                str(field).upper(): str(policy).upper()
                for field, policy
                in mapping["required_fields"].items()
            },
        )

    def assert_field_order(
        self,
        field_order: tuple[str, ...],
    ) -> None:
        fields = tuple(field.upper() for field in field_order)
        expected = set(self.required_fields)
        actual = set(fields)

        missing = sorted(expected - actual)
        unclassified = sorted(actual - expected)

        if missing or unclassified:
            raise ConstraintCoverageError(
                "Constraint coverage mismatch. "
                f"Missing navigation fields: {missing}; "
                f"Unclassified navigation fields: {unclassified}."
            )

        unresolved = sorted(
            field
            for field, policy in self.required_fields.items()
            if policy in {
                "",
                "UNRESOLVED",
                "CATALOG_UNREVIEWED",
            }
        )

        if unresolved:
            raise ConstraintCoverageError(
                "Fields have unresolved constraint coverage: "
                + ", ".join(unresolved)
            )

    def assert_complete_state(
        self,
        selections: dict[str, str],
    ) -> None:
        missing = sorted(
            set(self.required_fields) - set(selections)
        )

        if missing:
            raise ConstraintCoverageError(
                "Completed state is missing covered fields: "
                + ", ".join(missing)
            )

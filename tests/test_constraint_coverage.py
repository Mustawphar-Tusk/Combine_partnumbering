import pytest

from src.configuration_engine.constraint_coverage import (
    ConstraintCoverageError,
    ConstraintCoveragePolicy,
)


def test_complete_coverage_passes() -> None:
    policy = ConstraintCoveragePolicy(
        family_code="FYBROC",
        required_fields={
            "SERIES": "ATTRIBUTE_GLOBAL",
            "SIZE": "ATTRIBUTE_SERIES",
        },
    )

    policy.assert_field_order(
        ("SERIES", "SIZE")
    )


def test_unclassified_field_fails() -> None:
    policy = ConstraintCoveragePolicy(
        family_code="FYBROC",
        required_fields={
            "SERIES": "ATTRIBUTE_GLOBAL",
        },
    )

    with pytest.raises(
        ConstraintCoverageError
    ):
        policy.assert_field_order(
            ("SERIES", "SIZE")
        )

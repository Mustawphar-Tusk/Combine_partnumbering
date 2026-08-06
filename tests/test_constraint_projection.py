import pytest

from src.configuration_engine.projection import (
    AvailableOption,
    SqlAttributeProjectionRepository,
    SqlConstraintProjectionRepository,
)


def test_projection_types_exist() -> None:
    option = AvailableOption(
        field_code="SERIES",
        display_value="1530 (ANSI)",
    )

    assert option.field_code == "SERIES"
    assert callable(
        SqlConstraintProjectionRepository
        .available_combination_values
    )
    assert callable(
        SqlAttributeProjectionRepository
        .available_attribute_values
    )

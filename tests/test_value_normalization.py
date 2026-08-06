from src.configuration_engine.value_normalization import (
    normalize_engineering_value,
)


def test_normalizes_workbook_display_variations() -> None:
    assert (
        normalize_engineering_value(
            "External_Flush"
        )
        == normalize_engineering_value(
            "External Flush*"
        )
    )

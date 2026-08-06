from src.configuration_engine.models import (
    ConfigurationRequest,
    ResolvedConfigurationSegment,
)
from src.configuration_engine.service import ConfigurationEngine


class Repository:
    def resolve_combination_segment(
        self,
        *,
        family_code,
        segment_code,
        selections,
    ):
        values = {
            "PUMP_OPTIONS": ("0001", 1),
            "SEAL_ASSEMBLY": ("01", 1),
            "OPTIONS": ("01", 1),
        }

        value, source_id = values[segment_code]

        return ResolvedConfigurationSegment(
            segment_code=segment_code,
            segment_value=value,
            source_id=source_id,
            resolution_type="COMBINATION",
        )


def test_engine_generates_part_number_and_sku() -> None:
    segment_order = (
        "SERIES",
        "PUMP_OPTIONS",
        "SEAL_ASSEMBLY",
        "OPTIONS",
    )

    engine = ConfigurationEngine(
        repository=Repository(),
        segment_order=segment_order,
        required_combination_segments=(
            "PUMP_OPTIONS",
            "SEAL_ASSEMBLY",
            "OPTIONS",
        ),
    )

    result = engine.configure(
        ConfigurationRequest(
            family_code="FYBROC",
            series_code="1530",
            size_code="1x1.5x6",
            base_identifier="F1530",
            direct_segment_values={
                "SERIES": "B",
            },
            combination_selections={
                "PUMP_OPTIONS": {"A": "1"},
                "SEAL_ASSEMBLY": {"A": "1"},
                "OPTIONS": {"A": "1"},
            },
        )
    )

    assert result.valid is True
    assert result.part_number == "F1530-B-0001-01-01"
    assert result.sku == "F1530-V1-B00010101"

from src.configuration_engine.available_options import (
    AvailableOptionsRequest,
    AvailableOptionsService,
)
from src.configuration_engine.projection import (
    AvailableOption,
)
from src.configuration_engine.series_projection import (
    SeriesAllowedOption,
)


class AttributeRepository:
    def available_attribute_values(
        self,
        *,
        family_code,
        field_code,
    ):
        return (
            AvailableOption(field_code, "A"),
            AvailableOption(field_code, "B"),
            AvailableOption(field_code, "C"),
        )


class SeriesRepository:
    def available_values(
        self,
        *,
        family_code,
        series_code,
        field_code,
    ):
        return (
            SeriesAllowedOption(
                field_code,
                "B",
                series_code,
            ),
            SeriesAllowedOption(
                field_code,
                "C",
                series_code,
            ),
        )


class CombinationRepository:
    def available_combination_values(
        self,
        *,
        family_code,
        segment_code,
        target_field_code,
        current_selections,
    ):
        return (
            AvailableOption(target_field_code, "C"),
            AvailableOption(target_field_code, "D"),
        )


def test_service_intersects_sources() -> None:
    service = AvailableOptionsService(
        attribute_repository=AttributeRepository(),
        series_repository=SeriesRepository(),
        combination_repository=CombinationRepository(),
        attribute_fields={"FIELD"},
        segment_field_map={"FIELD": "SEGMENT"},
    )

    result = service.available_options(
        AvailableOptionsRequest(
            family_code="FYBROC",
            target_field_code="FIELD",
            series_code="1530",
        )
    )

    assert result.values == ("C",)
    assert result.applied_filters == (
        "ATTRIBUTE",
        "SERIES",
        "COMBINATION",
    )

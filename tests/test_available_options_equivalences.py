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
from src.configuration_engine.value_equivalences import (
    ValueEquivalenceProfile,
)


class AttributeRepository:
    def available_attribute_values(self, **kwargs):
        return ()


class SeriesRepository:
    def available_values(self, **kwargs):
        return (
            SeriesAllowedOption(
                "CASING_DRAINS",
                "Not_Supplied_by_Fybroc",
                "1530",
            ),
        )


class CombinationRepository:
    def available_combination_values(self, **kwargs):
        return (
            AvailableOption(
                "CASING_DRAINS",
                "No Casing Drains*",
            ),
            AvailableOption(
                "CASING_DRAINS",
                "Casing Drains",
            ),
        )


def test_service_intersects_equivalent_labels() -> None:
    equivalences = ValueEquivalenceProfile.from_mapping(
        {
            "family_code": "FYBROC",
            "fields": {
                "CASING_DRAINS": {
                    "equivalence_groups": [
                        {
                            "canonical_key": "NOT_INCLUDED",
                            "values": [
                                "Not_Supplied_by_Fybroc",
                                "No Casing Drains*",
                            ],
                        }
                    ]
                }
            },
        }
    )

    service = AvailableOptionsService(
        attribute_repository=AttributeRepository(),
        series_repository=SeriesRepository(),
        combination_repository=CombinationRepository(),
        attribute_fields=set(),
        segment_field_map={
            "CASING_DRAINS": "PUMP_OPTIONS"
        },
        value_equivalences=equivalences,
    )

    result = service.available_options(
        AvailableOptionsRequest(
            family_code="FYBROC",
            series_code="1530",
            target_field_code="CASING_DRAINS",
        )
    )

    assert result.values == (
        "No Casing Drains*",
    )

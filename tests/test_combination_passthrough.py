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


class EmptyAttributes:
    def available_attribute_values(self, **kwargs):
        return ()


class Series:
    def available_values(self, **kwargs):
        return (
            SeriesAllowedOption(
                "SEAL_TYPE",
                "Crane_8B2_Single_Outside",
                "1530",
            ),
        )


class Combination:
    def available_combination_values(self, **kwargs):
        return (
            AvailableOption(
                "SEAL_TYPE",
                "-",
            ),
        )


def test_explicit_combination_only_value_survives() -> None:
    profile = ValueEquivalenceProfile.from_mapping(
        {
            "family_code": "FYBROC",
            "fields": {
                "SEAL_TYPE": {
                    "equivalence_groups": [],
                    "combination_passthrough_values": [
                        "-"
                    ],
                }
            },
        }
    )

    service = AvailableOptionsService(
        attribute_repository=EmptyAttributes(),
        series_repository=Series(),
        combination_repository=Combination(),
        attribute_fields=set(),
        segment_field_map={
            "SEAL_TYPE": "SEAL_ASSEMBLY"
        },
        value_equivalences=profile,
    )

    result = service.available_options(
        AvailableOptionsRequest(
            family_code="FYBROC",
            series_code="1530",
            target_field_code="SEAL_TYPE",
        )
    )

    assert result.values == ("-",)

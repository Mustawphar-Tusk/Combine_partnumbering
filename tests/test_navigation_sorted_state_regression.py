from src.configuration_engine.allowable_navigation import (
    AllowableConfigurationNavigator,
)
from src.configuration_engine.available_options import (
    AvailableOptionsResult,
)
from src.configuration_engine.navigation_tokens import (
    NavigationTokenCodec,
)


class Options:
    values = {
        "SERIES": ("1530",),
        "SIZE": ("1x1.5x6",),
        "PUMP_MATERIAL": ("VR-1*",),
        "IMPELLER_TRIM": ("16.000",),
    }

    def available_options(self, request):
        values = self.values[
            request.target_field_code
        ]
        return AvailableOptionsResult(
            family_code=request.family_code,
            target_field_code=request.target_field_code,
            series_code=request.series_code,
            segment_code=request.segment_code,
            values=values,
            source_counts={"TEST": len(values)},
            applied_filters=("TEST",),
        )


def test_state_survives_more_than_two_selections() -> None:
    navigator = AllowableConfigurationNavigator(
        available_options_service=Options(),
        token_codec=NavigationTokenCodec.from_text(
            "01234567890123456789012345678901"
        ),
        runtime_revision="publication:1;batch:2",
        field_order=(
            "SERIES",
            "SIZE",
            "PUMP_MATERIAL",
            "IMPELLER_TRIM",
        ),
        segment_field_map={},
        combination_segment_field_order={},
    )

    response = navigator.start(
        family_code="FYBROC"
    )

    while not response.complete:
        response = navigator.advance(
            state_token=response.state_token,
            option_token=(
                response.options[0].option_token
            ),
        )

    selections = navigator.selections_from_state(
        state_token=response.state_token,
        require_complete=True,
    )

    assert set(selections) == {
        "SERIES",
        "SIZE",
        "PUMP_MATERIAL",
        "IMPELLER_TRIM",
    }

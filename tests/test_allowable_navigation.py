from src.configuration_engine.allowable_navigation import (
    AllowableConfigurationNavigator,
)
from src.configuration_engine.available_options import (
    AvailableOptionsResult,
)
from src.configuration_engine.navigation_tokens import (
    NavigationTokenCodec,
    NavigationTokenError,
)


class FakeAvailableOptionsService:
    values = {
        "SERIES": ("1530",),
        "SIZE": ("1x1.5x6", "2x3x6"),
        "PUMP_MATERIAL": ("VR-1",),
    }

    def available_options(self, request):
        values = self.values[
            request.target_field_code
        ]

        return AvailableOptionsResult(
            family_code=request.family_code,
            target_field_code=(
                request.target_field_code
            ),
            series_code=request.series_code,
            segment_code=request.segment_code,
            values=values,
            source_counts={"TEST": len(values)},
            applied_filters=("TEST",),
        )


def navigator() -> AllowableConfigurationNavigator:
    return AllowableConfigurationNavigator(
        available_options_service=(
            FakeAvailableOptionsService()
        ),
        token_codec=NavigationTokenCodec.from_text(
            "01234567890123456789012345678901"
        ),
        runtime_revision="publication:1;batch:2",
        field_order=(
            "SERIES",
            "SIZE",
            "PUMP_MATERIAL",
        ),
        segment_field_map={},
        combination_segment_field_order={},
    )


def test_navigation_only_advances_with_issued_option() -> None:
    service = navigator()
    start = service.start(family_code="FYBROC")

    assert start.next_field_code == "SERIES"
    assert len(start.options) == 1

    size = service.advance(
        state_token=start.state_token,
        option_token=start.options[0].option_token,
    )

    assert size.next_field_code == "SIZE"
    assert {
        option.display_value
        for option in size.options
    } == {"1x1.5x6", "2x3x6"}


def test_option_from_old_state_cannot_be_reused() -> None:
    service = navigator()
    start = service.start(family_code="FYBROC")

    size = service.advance(
        state_token=start.state_token,
        option_token=start.options[0].option_token,
    )

    with __import__("pytest").raises(
        NavigationTokenError
    ):
        service.advance(
            state_token=size.state_token,
            option_token=start.options[0].option_token,
        )

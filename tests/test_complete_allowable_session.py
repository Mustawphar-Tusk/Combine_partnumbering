from dataclasses import dataclass

import pytest

from src.configuration_engine.complete_session import (
    CompleteAllowableConfigurationSession,
)
from src.configuration_engine.identifier_generation import (
    IdentifierGenerationResult,
)


@dataclass(frozen=True)
class Response:
    family_code: str
    runtime_revision: str
    state_token: str
    complete: bool


class FakeNavigator:
    def resume(self, *, state_token):
        return Response(
            family_code="FYBROC",
            runtime_revision="publication:1;batch:2",
            state_token=state_token,
            complete=state_token == "complete",
        )

    def selections_from_state(
        self,
        *,
        state_token,
        require_complete,
    ):
        assert state_token == "complete"
        assert require_complete is True
        return {
            "SERIES": "1530",
            "SIZE": "1x1.5x6",
        }


class FakeGenerator:
    def __init__(self):
        self.received = None

    def generate(self, selections):
        self.received = selections
        return IdentifierGenerationResult(
            valid=True,
            part_number="F1530-B-1",
            sku="F1530-V1-B1",
            configuration_signature="abc",
            segments=(),
            validation_messages=(),
            metadata_trace={},
        )


def test_finalize_uses_complete_signed_state() -> None:
    generator = FakeGenerator()
    service = CompleteAllowableConfigurationSession(
        navigator=FakeNavigator(),
        identifier_generator=generator,
    )

    result = service.finalize(
        state_token="complete"
    )

    assert result.identifier_result.part_number == (
        "F1530-B-1"
    )
    assert generator.received == {
        "SERIES": "1530",
        "SIZE": "1x1.5x6",
    }


def test_incomplete_state_cannot_generate() -> None:
    service = CompleteAllowableConfigurationSession(
        navigator=FakeNavigator(),
        identifier_generator=FakeGenerator(),
    )

    with pytest.raises(RuntimeError):
        service.finalize(
            state_token="incomplete"
        )

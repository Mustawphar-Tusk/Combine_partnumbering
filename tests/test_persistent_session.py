from __future__ import annotations

from dataclasses import dataclass

from src.configuration_engine.persistent_session import (
    PersistentAllowableConfigurationSession,
)


@dataclass(frozen=True)
class Segment:
    segment_code: str = "SERIES"
    segment_value: str = "B"
    resolution_type: str = "ATTRIBUTE"
    source_id: int | None = 2
    source_ids: tuple[int, ...] = (2,)


@dataclass(frozen=True)
class IdentifierResult:
    configuration_signature: str = "a" * 64
    part_number: str = "F1530-B"
    sku: str = "F1530-V1-B"
    segments: tuple[Segment, ...] = (Segment(),)


@dataclass(frozen=True)
class Completed:
    family_code: str = "FYBROC"
    runtime_revision: str = (
        "publication:1;series-batch:2;"
        "combination-batch:3;dependency-batch:4"
    )
    selections: dict[str, str] = None
    identifier_result: IdentifierResult = IdentifierResult()

    def __post_init__(self):
        if self.selections is None:
            object.__setattr__(
                self,
                "selections",
                {"SERIES": "1530 (ANSI)"},
            )


class Navigator:
    field_order = ("SERIES",)


class CompleteSession:
    navigator = Navigator()

    def finalize(self, *, state_token):
        assert state_token == "signed-complete-state"
        return Completed()


class Repository:
    def __init__(self):
        self.payload = None

    def persist(self, payload):
        self.payload = payload
        return "persisted"


def test_persistent_session_uses_completed_state_only() -> None:
    repository = Repository()
    service = PersistentAllowableConfigurationSession(
        complete_session=CompleteSession(),
        persistence_repository=repository,
    )

    result = service.finalize_and_persist(
        state_token="signed-complete-state",
        requested_by="tester",
    )

    assert result.persisted_product == "persisted"
    assert repository.payload.part_number == "F1530-B"
    assert repository.payload.requested_by == "tester"

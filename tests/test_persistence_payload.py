from __future__ import annotations

import json
from dataclasses import dataclass

from src.configuration_engine.persistence import (
    build_persistence_payload,
    parse_runtime_revision,
)


@dataclass(frozen=True)
class Segment:
    segment_code: str
    segment_value: str
    resolution_type: str
    source_id: int | None
    source_ids: tuple[int, ...]


@dataclass(frozen=True)
class IdentifierResult:
    configuration_signature: str
    part_number: str
    sku: str
    segments: tuple[Segment, ...]


@dataclass(frozen=True)
class Completed:
    family_code: str
    runtime_revision: str
    selections: dict[str, str]
    identifier_result: IdentifierResult


def test_runtime_revision_parser() -> None:
    result = parse_runtime_revision(
        "publication:1;series-batch:2;"
        "combination-batch:3;dependency-batch:4"
    )

    assert result.metadata_publication_id == 1
    assert result.series_batch_id == 2
    assert result.combination_batch_id == 3
    assert result.dependency_batch_id == 4


def test_payload_preserves_navigation_order() -> None:
    completed = Completed(
        family_code="FYBROC",
        runtime_revision=(
            "publication:1;series-batch:2;"
            "combination-batch:3;dependency-batch:4"
        ),
        selections={
            "SIZE": "1x1.5x6",
            "SERIES": "1530 (ANSI)",
        },
        identifier_result=IdentifierResult(
            configuration_signature="a" * 64,
            part_number="F1530-B-1",
            sku="F1530-V1-B1",
            segments=(
                Segment(
                    segment_code="SERIES",
                    segment_value="B",
                    resolution_type="ATTRIBUTE",
                    source_id=2,
                    source_ids=(2,),
                ),
            ),
        ),
    )

    payload = build_persistence_payload(
        completed=completed,
        field_order=("SERIES", "SIZE"),
        requested_by="test-user",
    )

    selections = json.loads(
        payload.selections_json
    )

    assert [
        row["field_code"]
        for row in selections
    ] == ["SERIES", "SIZE"]
    assert payload.metadata_publication_id == 1
    assert payload.dependency_batch_id == 4

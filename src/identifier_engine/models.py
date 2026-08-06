from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResolvedModel:
    family_code: str
    model_identifier: str
    series_code: str
    size_code: str
    base_identifier: str


@dataclass(frozen=True)
class ResolvedSegment:
    segment_code: str
    assembly_order: int
    value: str
    expected_width: int | None


@dataclass(frozen=True)
class IdentifierResult:
    part_number: str
    sku: str
    segment_string: str
    compact_segment_string: str

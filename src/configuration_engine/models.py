from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ConfigurationRequest:
    family_code: str
    series_code: str
    size_code: str
    base_identifier: str
    combination_selections: dict[str, dict[str, str]]
    direct_segment_values: dict[str, str] = field(default_factory=dict)
    identifier_version: int = 1


@dataclass(frozen=True)
class ResolvedConfigurationSegment:
    segment_code: str
    segment_value: str
    source_id: int | None
    resolution_type: str


@dataclass(frozen=True)
class ConfigurationEngineResult:
    valid: bool
    part_number: str | None
    sku: str | None
    segment_string: str | None
    compact_segment_string: str | None
    segments: tuple[ResolvedConfigurationSegment, ...]
    validation_messages: tuple[str, ...]

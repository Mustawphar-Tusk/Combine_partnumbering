from __future__ import annotations

from typing import Protocol

from src.configuration_engine.models import ResolvedConfigurationSegment


class ConfigurationMetadataRepository(Protocol):
    def resolve_combination_segment(
        self,
        *,
        family_code: str,
        segment_code: str,
        selections: dict[str, str],
    ) -> ResolvedConfigurationSegment | None: ...

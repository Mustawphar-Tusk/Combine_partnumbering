from __future__ import annotations

from typing import Protocol

from src.identifier_engine.models import ResolvedModel, ResolvedSegment


class IdentifierMetadataRepository(Protocol):
    def resolve_model(
        self,
        family_code: str,
        series_code: str,
        size_code: str,
    ) -> ResolvedModel: ...

    def get_validated_segments(
        self,
        family_code: str,
        selections: dict[str, str],
    ) -> tuple[ResolvedSegment, ...]: ...

    def get_identifier_format(
        self,
        family_code: str,
        identifier_type: str,
    ) -> dict: ...

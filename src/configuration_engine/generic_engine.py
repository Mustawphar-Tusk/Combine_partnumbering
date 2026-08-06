from __future__ import annotations

from dataclasses import dataclass

from src.configuration_engine.models import (
    ConfigurationEngineResult,
    ResolvedConfigurationSegment,
)
from src.configuration_engine.resolvers import ResolverRegistry


@dataclass(frozen=True)
class SegmentRuntimeDefinition:
    segment_code: str
    resolution_type: str
    required: bool = True


@dataclass(frozen=True)
class GenericConfigurationRequest:
    family_code: str
    base_identifier: str
    identifier_version: int
    selections: dict[str, object]


class GenericConfigurationEngine:
    def __init__(
        self,
        registry: ResolverRegistry,
        segment_definitions: tuple[SegmentRuntimeDefinition, ...],
    ) -> None:
        self.registry = registry
        self.segment_definitions = segment_definitions

    def configure(
        self,
        request: GenericConfigurationRequest,
    ) -> ConfigurationEngineResult:
        messages: list[str] = []
        resolved: list[ResolvedConfigurationSegment] = []

        for definition in self.segment_definitions:
            payload = request.selections.get(definition.segment_code)

            if payload is None:
                if definition.required:
                    messages.append(
                        f"Selection is required for "
                        f"{definition.segment_code}."
                    )
                continue

            resolver = self.registry.get(
                definition.resolution_type
            )

            segment = resolver.resolve(
                family_code=request.family_code,
                segment_code=definition.segment_code,
                payload=payload,
            )

            if segment is None:
                messages.append(
                    f"No valid {definition.segment_code} value "
                    "matches the submitted selection."
                )
                continue

            resolved.append(segment)

        if messages:
            return ConfigurationEngineResult(
                valid=False,
                part_number=None,
                sku=None,
                segment_string=None,
                compact_segment_string=None,
                segments=tuple(resolved),
                validation_messages=tuple(messages),
            )

        segment_string = "-".join(
            item.segment_value for item in resolved
        )
        compact = "".join(
            item.segment_value for item in resolved
        )
        base = request.base_identifier.strip().upper()

        return ConfigurationEngineResult(
            valid=True,
            part_number=f"{base}-{segment_string}",
            sku=f"{base}-V{request.identifier_version}-{compact}",
            segment_string=segment_string,
            compact_segment_string=compact,
            segments=tuple(resolved),
            validation_messages=(),
        )

from __future__ import annotations

from src.configuration_engine.contracts import (
    ConfigurationMetadataRepository,
)
from src.configuration_engine.models import (
    ConfigurationEngineResult,
    ConfigurationRequest,
    ResolvedConfigurationSegment,
)


class ConfigurationEngine:
    def __init__(
        self,
        repository: ConfigurationMetadataRepository,
        segment_order: tuple[str, ...],
        required_combination_segments: tuple[str, ...],
    ) -> None:
        self.repository = repository
        self.segment_order = segment_order
        self.required_combination_segments = (
            required_combination_segments
        )

    def configure(
        self,
        request: ConfigurationRequest,
    ) -> ConfigurationEngineResult:
        messages: list[str] = []
        resolved: dict[str, ResolvedConfigurationSegment] = {}

        if not request.family_code.strip():
            messages.append("Family code is required.")

        if not request.series_code.strip():
            messages.append("Series code is required.")

        if not request.size_code.strip():
            messages.append("Size code is required.")

        if not request.base_identifier.strip():
            messages.append("Base identifier is required.")

        for segment_code in self.required_combination_segments:
            selections = request.combination_selections.get(
                segment_code
            )

            if not selections:
                messages.append(
                    f"Selections are required for {segment_code}."
                )
                continue

            segment = self.repository.resolve_combination_segment(
                family_code=request.family_code,
                segment_code=segment_code,
                selections=selections,
            )

            if segment is None:
                messages.append(
                    f"No valid {segment_code} combination matches "
                    "the submitted selections."
                )
                continue

            resolved[segment_code] = segment

        for (
            segment_code,
            segment_value,
        ) in request.direct_segment_values.items():
            if not str(segment_value).strip():
                messages.append(
                    f"Direct segment {segment_code} is blank."
                )
                continue

            resolved[segment_code] = ResolvedConfigurationSegment(
                segment_code=segment_code,
                segment_value=str(segment_value).strip().upper(),
                source_id=None,
                resolution_type="DIRECT",
            )

        missing_segments = [
            segment_code
            for segment_code in self.segment_order
            if segment_code not in resolved
        ]

        if missing_segments:
            messages.append(
                "The following identifier segments were not resolved: "
                + ", ".join(missing_segments)
            )

        if messages:
            return ConfigurationEngineResult(
                valid=False,
                part_number=None,
                sku=None,
                segment_string=None,
                compact_segment_string=None,
                segments=tuple(
                    resolved[segment_code]
                    for segment_code in self.segment_order
                    if segment_code in resolved
                ),
                validation_messages=tuple(messages),
            )

        ordered_segments = tuple(
            resolved[segment_code]
            for segment_code in self.segment_order
        )

        segment_string = "-".join(
            segment.segment_value
            for segment in ordered_segments
        )
        compact_segment_string = "".join(
            segment.segment_value
            for segment in ordered_segments
        )

        base_identifier = request.base_identifier.strip().upper()

        part_number = (
            f"{base_identifier}-{segment_string}"
        )
        sku = (
            f"{base_identifier}-V{request.identifier_version}-"
            f"{compact_segment_string}"
        )

        return ConfigurationEngineResult(
            valid=True,
            part_number=part_number,
            sku=sku,
            segment_string=segment_string,
            compact_segment_string=compact_segment_string,
            segments=ordered_segments,
            validation_messages=(),
        )

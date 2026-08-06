from __future__ import annotations

from src.identifier_engine.contracts import IdentifierMetadataRepository
from src.identifier_engine.models import IdentifierResult


class IdentifierEngine:
    def __init__(self, repository: IdentifierMetadataRepository) -> None:
        self.repository = repository

    def generate(
        self,
        *,
        family_code: str,
        series_code: str,
        size_code: str,
        selections: dict[str, str],
    ) -> IdentifierResult:
        model = self.repository.resolve_model(
            family_code=family_code,
            series_code=series_code,
            size_code=size_code,
        )

        segments = tuple(
            sorted(
                self.repository.get_validated_segments(
                    family_code=family_code,
                    selections=selections,
                ),
                key=lambda item: item.assembly_order,
            )
        )

        for segment in segments:
            if segment.expected_width is not None and len(segment.value) != segment.expected_width:
                raise ValueError(
                    f"Segment '{segment.segment_code}' expected width "
                    f"{segment.expected_width}, got {len(segment.value)}."
                )

        segment_separator = self.repository.get_identifier_format(
            family_code,
            "PART_NUMBER",
        ).get("segment_separator", "-")

        segment_string = segment_separator.join(segment.value for segment in segments)
        compact_segment_string = "".join(segment.value for segment in segments)

        part_format = self.repository.get_identifier_format(
            family_code,
            "PART_NUMBER",
        )
        sku_format = self.repository.get_identifier_format(
            family_code,
            "SKU",
        )

        part_number = part_format["template"].format(
            base_identifier=model.base_identifier,
            segment_string=segment_string,
            compact_segment_string=compact_segment_string,
            version=part_format.get("version", 1),
        )

        sku = sku_format["template"].format(
            base_identifier=model.base_identifier,
            segment_string=segment_string,
            compact_segment_string=compact_segment_string,
            version=sku_format.get("version", 1),
        )

        return IdentifierResult(
            part_number=part_number,
            sku=sku,
            segment_string=segment_string,
            compact_segment_string=compact_segment_string,
        )

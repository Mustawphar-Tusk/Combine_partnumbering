from src.identifier_engine.models import ResolvedModel, ResolvedSegment
from src.identifier_engine.service import IdentifierEngine


class Repository:
    def resolve_model(self, family_code, series_code, size_code):
        return ResolvedModel(
            family_code=family_code,
            model_identifier="A779",
            series_code=series_code,
            size_code=size_code,
            base_identifier="D779",
        )

    def get_validated_segments(self, family_code, selections):
        return (
            ResolvedSegment("A", 20, "AB", 2),
            ResolvedSegment("B", 10, "00CA", 4),
        )

    def get_identifier_format(self, family_code, identifier_type):
        if identifier_type == "PART_NUMBER":
            return {
                "template": "{base_identifier}-{segment_string}",
                "segment_separator": "-",
                "version": 1,
            }
        return {
            "template": "{base_identifier}-V{version}-{compact_segment_string}",
            "segment_separator": "",
            "version": 1,
        }


def test_identifier_engine_generates_part_number_and_sku():
    result = IdentifierEngine(Repository()).generate(
        family_code="DEAN",
        series_code="RA2096",
        size_code="1x1.5x6",
        selections={},
    )

    assert result.part_number == "D779-00CA-AB"
    assert result.sku == "D779-V1-00CAAB"

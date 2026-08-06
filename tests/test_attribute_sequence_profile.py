from src.configuration_engine.identifier_generation import (
    IdentifierGenerationProfile,
)


def test_attribute_sequence_profile() -> None:
    profile = IdentifierGenerationProfile.from_mapping(
        {
            "family_code": "FYBROC",
            "base_identifier": {
                "prefix": "F",
                "series_field_code": "SERIES",
                "series_code_pattern": "(\\d{4})",
            },
            "sku_version": 1,
            "segments": [
                {
                    "segment_code": "MOTOR_MODIFICATIONS",
                    "resolution_type": "ATTRIBUTE_SEQUENCE",
                    "source_field_code": "MOTOR_MODIFICATIONS",
                    "field_codes": [
                        "MOTOR_MODIFICATION_1",
                        "MOTOR_MODIFICATION_2",
                        "MOTOR_MODIFICATION_3",
                    ],
                }
            ],
        }
    )

    segment = profile.segments[0]

    assert segment.resolution_type == (
        "ATTRIBUTE_SEQUENCE"
    )
    assert segment.source_field_code == (
        "MOTOR_MODIFICATIONS"
    )
    assert len(segment.field_codes) == 3

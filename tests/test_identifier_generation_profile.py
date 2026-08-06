from src.configuration_engine.identifier_generation import (
    IdentifierGenerationProfile,
)


def test_profile_is_metadata_driven() -> None:
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
                    "segment_code": "SERIES",
                    "resolution_type": "ATTRIBUTE",
                    "field_code": "SERIES",
                },
                {
                    "segment_code": "OPTIONS",
                    "resolution_type": "COMBINATION",
                    "selection_fields": [
                        "OPTION_A",
                        "OPTION_B",
                    ],
                },
            ],
        }
    )

    assert profile.family_code == "FYBROC"
    assert profile.base_prefix == "F"
    assert len(profile.segments) == 2
    assert profile.segments[1].selection_fields == (
        "OPTION_A",
        "OPTION_B",
    )

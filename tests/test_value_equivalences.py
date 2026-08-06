from src.configuration_engine.value_equivalences import (
    ValueEquivalenceProfile,
)


def profile() -> ValueEquivalenceProfile:
    return ValueEquivalenceProfile.from_mapping(
        {
            "family_code": "FYBROC",
            "fields": {
                "CASING_DRAINS": {
                    "equivalence_groups": [
                        {
                            "canonical_key": "NOT_INCLUDED",
                            "values": [
                                "Not_Supplied_by_Fybroc",
                                "No Casing Drains*",
                            ],
                        }
                    ]
                },
                "SEAL_TYPE": {
                    "equivalence_groups": [],
                    "combination_passthrough_values": [
                        "-"
                    ],
                },
            },
        }
    )


def test_equivalent_values_share_key() -> None:
    value = profile()

    left = value.canonical_key(
        field_code="CASING_DRAINS",
        raw_value="Not_Supplied_by_Fybroc",
        fallback_key="left",
    )
    right = value.canonical_key(
        field_code="CASING_DRAINS",
        raw_value="No Casing Drains*",
        fallback_key="right",
    )

    assert left == right


def test_passthrough_is_explicit() -> None:
    value = profile()

    assert value.is_combination_passthrough(
        field_code="SEAL_TYPE",
        raw_value="-",
    )
    assert not value.is_combination_passthrough(
        field_code="SEAL_TYPE",
        raw_value="anything",
    )

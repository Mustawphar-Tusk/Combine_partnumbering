from __future__ import annotations

from collections import Counter
from pathlib import Path

from src.pricing_engine.compilation_merge import (
    merge_compiled_pricing,
)


ROOT = Path(__file__).resolve().parents[1]


def combined():
    return merge_compiled_pricing(
        (
            ROOT
            / "exports"
            / "fybroc_base_pump_pricing.json",
            ROOT
            / "exports"
            / "fybroc_seal_pricing.json",
        )
    )


def test_m0225_combined_compilation_baseline():
    data = combined()

    assert (
        data["candidate_count"]
        == 2884
    )
    assert (
        data["condition_count"]
        == 13112
    )
    assert data["issue_count"] == 0

    assert data[
        "component_counts"
    ] == {
        "BASE_PUMP": 436,
        "SEAL": 2448,
    }

    assert data[
        "status_counts"
    ] == {
        "call_for_price": 323,
        "found": 2561,
    }


def test_m0225_combined_conditions_are_complete():
    data = combined()

    base_condition_counts = Counter()
    seal_condition_counts = Counter()

    for candidate in (
        data["candidates"]
    ):
        component = candidate[
            "component_code"
        ]

        condition_count = len(
            candidate["conditions"]
        )

        if component == "BASE_PUMP":
            base_condition_counts[
                condition_count
            ] += 1
        elif component == "SEAL":
            seal_condition_counts[
                condition_count
            ] += 1

    assert base_condition_counts == {
        2: 436,
    }

    assert seal_condition_counts == {
        5: 2448,
    }


def test_m0225_combined_has_no_duplicate_rule_keys():
    data = combined()

    keys = []

    for candidate in (
        data["candidates"]
    ):
        conditions = tuple(
            (
                row["field_code"],
                row["comparison_operator"],
                row[
                    "comparison_value"
                ],
            )
            for row in sorted(
                candidate[
                    "conditions"
                ],
                key=lambda item:
                    item[
                        "sequence_no"
                    ],
            )
        )

        keys.append(
            (
                candidate[
                    "component_code"
                ],
                candidate.get(
                    "series_code"
                ),
                conditions,
            )
        )

    assert len(keys) == len(
        set(keys)
    )


def test_m0225_combined_source_contract():
    data = combined()

    assert (
        data["family_code"]
        == "FYBROC"
    )
    assert (
        data["currency_code"]
        == "USD"
    )
    assert (
        data["source_workbook"]
        == "Price Estimator-Fybroc.xlsm"
    )

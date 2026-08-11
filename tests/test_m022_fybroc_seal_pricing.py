from __future__ import annotations

from collections import Counter
from functools import lru_cache
from pathlib import Path


from src.compiler.fybroc_seal_pricing_compiler import (
    compile_fybroc_seal_pricing,
)


ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def compile_report():
    return compile_fybroc_seal_pricing(
        ROOT
        / "workbooks"
        / "Fybroc"
        / "Price Estimator-Fybroc.xlsm",
        ROOT
        / "workbooks"
        / "Fybroc"
        / "Fybroc Nomenclature_V5.xlsm",
        ROOT
        / "exports"
        / "fybroc_base_pump_pricing.json",
        ROOT
        / "config"
        / "pricing_profiles"
        / "fybroc_seal.json",
    )


def condition_map(candidate):
    return {
        condition.field_code:
            condition.comparison_value
        for condition
        in candidate.conditions
    }


def find_candidate(
    *,
    series,
    size,
    seal_option,
    seal_type,
    materials,
    elastomers,
):
    report = compile_report()
    matches = []

    for candidate in (
        report.candidates
    ):
        if (
            candidate.series_code
            != series
        ):
            continue

        values = condition_map(
            candidate
        )

        if (
            values.get("SIZE")
            == size
            and values.get(
                "SEAL_OPTION"
            )
            == seal_option
            and values.get(
                "SEAL_TYPE"
            )
            == seal_type
            and values.get(
                "SEAL_MATERIALS"
            )
            == materials
            and values.get(
                "SEAL_ELASTOMERS"
            )
            == elastomers
        ):
            matches.append(
                candidate
            )

    assert len(matches) == 1
    return matches[0]


def test_m0224b_complete_seal_compiler_baseline():
    report = compile_report()

    assert report.issue_count == 0
    assert report.candidate_count == 2448

    counts = Counter(
        candidate.pricing_status
        for candidate
        in report.candidates
    )

    assert counts == {
        "found": 2140,
        "call_for_price": 308,
    }


def test_m0224b_every_rule_has_five_conditions():
    report = compile_report()

    expected_fields = [
        "SIZE",
        "SEAL_OPTION",
        "SEAL_TYPE",
        "SEAL_MATERIALS",
        "SEAL_ELASTOMERS",
    ]

    for candidate in (
        report.candidates
    ):
        assert (
            candidate.component_code
            == "SEAL"
        )

        assert [
            condition.field_code
            for condition
            in candidate.conditions
        ] == expected_fields


def test_m0224b_1530_group1_standard_seal_prices():
    fkm = find_candidate(
        series="1530 (ANSI)",
        size="1x1.5x6",
        seal_option=(
            "Mechanical Seal Included*"
        ),
        seal_type=(
            "8B2 Single Outside*"
        ),
        materials=(
            "Carbon vs. Ceramic*"
        ),
        elastomers="FKM*",
    )

    assert fkm.amount == 749.0
    assert (
        fkm.pricing_status
        == "found"
    )
    assert fkm.table_name == "Table79"
    assert fkm.source_cell == "BS6"

    epr = find_candidate(
        series="1530 (ANSI)",
        size="1x1.5x6",
        seal_option=(
            "Mechanical Seal Included*"
        ),
        seal_type=(
            "8B2 Single Outside*"
        ),
        materials=(
            "Carbon vs. Ceramic*"
        ),
        elastomers="EPR",
    )

    assert epr.amount == 749.0
    assert epr.source_cell == "BS6"


def test_m0224b_ptfe_table137_and_call_for_price():
    found = find_candidate(
        series="1530 (ANSI)",
        size="1x1.5x6",
        seal_option=(
            "Mechanical Seal Included*"
        ),
        seal_type=(
            "8B2 Single Outside*"
        ),
        materials=(
            "Carbon vs. Ceramic*"
        ),
        elastomers="PTFE",
    )

    assert found.amount == 1508.0
    assert (
        found.pricing_status
        == "found"
    )
    assert found.table_name == "Table137"
    assert found.source_cell == "BS40"

    cfp = find_candidate(
        series="1530 (ANSI)",
        size="1x1.5x6",
        seal_option=(
            "Mechanical Seal Included*"
        ),
        seal_type=(
            "RAC Single Outside"
        ),
        materials=(
            "Carbon vs. Ceramic*"
        ),
        elastomers="PTFE",
    )

    assert cfp.amount is None
    assert (
        cfp.pricing_status
        == "call_for_price"
    )
    assert cfp.source_cell == "BS41"


def test_m0224b_customer_supplied_is_cfp():
    candidate = find_candidate(
        series="1530 (ANSI)",
        size="1x1.5x6",
        seal_option="Customer Supplied",
        seal_type="-",
        materials="-",
        elastomers="-",
    )

    assert candidate.amount is None
    assert (
        candidate.pricing_status
        == "call_for_price"
    )
    assert (
        candidate.source_option_value
        == (
            "Supplied by others; "
            "Installed by Fybroc | -"
        )
    )
    assert candidate.table_name == "Table79"
    assert candidate.source_cell == "BS15"


def test_m0224b_all_no_seal_variants_are_zero():
    options = (
        "No Seal (Single Seal Gland by Fyboc)",
        "No Seal (Double Seal Gland by Fyboc)",
        "No Seal (No Seal Gland)",
    )

    for option in options:
        candidate = find_candidate(
            series="1530 (ANSI)",
            size="1x1.5x6",
            seal_option=option,
            seal_type="-",
            materials="-",
            elastomers="-",
        )

        assert candidate.amount == 0.0
        assert (
            candidate.pricing_status
            == "found"
        )
        assert (
            candidate.source_cell
            == "BS16"
        )


def test_m0224b_option_counts():
    report = compile_report()

    counts = Counter(
        condition_map(
            candidate
        )["SEAL_OPTION"]
        for candidate
        in report.candidates
    )

    assert counts[
        "Mechanical Seal Included*"
    ] == 2160

    assert counts[
        "Customer Supplied"
    ] == 72

    assert counts[
        "No Seal (Single Seal Gland by Fyboc)"
    ] == 72

    assert counts[
        "No Seal (Double Seal Gland by Fyboc)"
    ] == 72

    assert counts[
        "No Seal (No Seal Gland)"
    ] == 72


def test_m0224b_series_counts():
    report = compile_report()

    counts = Counter(
        candidate.series_code
        for candidate
        in report.candidates
    )

    assert counts == {
        "1500": 646,
        "1530 (ANSI)": 544,
        "1550": 442,
        "1600": 204,
        "1630": 204,
        "1650": 204,
        "3000": 204,
    }


def test_m0224b_no_duplicate_canonical_rule_keys():
    report = compile_report()

    keys = []

    for candidate in (
        report.candidates
    ):
        keys.append(
            (
                candidate.component_code,
                candidate.series_code,
                tuple(
                    (
                        condition.field_code,
                        condition.comparison_operator,
                        condition.comparison_value,
                    )
                    for condition
                    in candidate.conditions
                ),
            )
        )

    assert len(keys) == len(
        set(keys)
    )

from pathlib import Path

from src.compiler.pricing_metadata_compiler import compile_base_pump_pricing
from src.pricing_engine.publisher import (
    _canonical_conditions_json,
    _legacy_transport_values,
    _normalized_conditions,
)

ROOT = Path(__file__).resolve().parents[1]


def test_m022_base_pump_emits_two_generic_conditions():
    report = compile_base_pump_pricing(
        ROOT / "workbooks" / "Fybroc" / "Price Estimator-Fybroc.xlsm",
        ROOT / "config" / "pricing_profiles" / "fybroc_base_pump.json",
    )
    assert report.issue_count == 0
    assert report.candidate_count == 436
    assert all(len(c.conditions) == 2 for c in report.candidates)
    first = report.candidates[0]
    assert first.conditions[0].field_code == "SIZE"
    assert first.conditions[0].comparison_value == first.size_value
    assert first.conditions[1].field_code == "PUMP_MATERIAL"
    assert first.conditions[1].comparison_value == first.option_value


def test_m022_publisher_preserves_base_pump_legacy_transport():
    candidate = {
        "size_value": "1x1.5x6",
        "source_size_value": "1x1.5x6 (6AA)",
        "option_field_code": "PUMP_MATERIAL",
        "option_value": "VR-1*",
        "source_option_value": "VR-1 (Standard)",
        "conditions": [
            {"sequence_no": 1, "field_code": "SIZE", "comparison_operator": "EQ", "comparison_value": "1x1.5x6"},
            {"sequence_no": 2, "field_code": "PUMP_MATERIAL", "comparison_operator": "EQ", "comparison_value": "VR-1*"},
        ],
    }
    payload = _canonical_conditions_json(candidate)
    assert len(_normalized_conditions(candidate)) == 2
    assert _legacy_transport_values(candidate, payload) == (
        "1x1.5x6",
        "1x1.5x6 (6AA)",
        "PUMP_MATERIAL",
        "VR-1*",
        "VR-1 (Standard)",
    )


def test_m022_multi_condition_uses_deterministic_proxy_key():
    candidate = {
        "size_value": "1x1.5x6",
        "source_size_value": "1x1.5x6 (6AA)",
        "option_field_code": None,
        "option_value": None,
        "source_option_value": None,
        "conditions": [
            {"sequence_no": 1, "field_code": "SIZE", "comparison_operator": "EQ", "comparison_value": "1x1.5x6"},
            {"sequence_no": 2, "field_code": "SEAL_OPTION", "comparison_operator": "EQ", "comparison_value": "Mechanical Seal Included*"},
            {"sequence_no": 3, "field_code": "SEAL_TYPE", "comparison_operator": "EQ", "comparison_value": "8B2 Single Outside*"},
            {"sequence_no": 4, "field_code": "SEAL_MATERIALS", "comparison_operator": "EQ", "comparison_value": "Carbon vs. Ceramic*"},
            {"sequence_no": 5, "field_code": "SEAL_ELASTOMERS", "comparison_operator": "EQ", "comparison_value": "FKM*"},
        ],
    }
    payload = _canonical_conditions_json(candidate)
    transport = _legacy_transport_values(candidate, payload)
    assert transport[0] == "1x1.5x6"
    assert transport[2] == "__CONDITION_SET__"
    assert len(transport[3]) == 64

from __future__ import annotations

import csv
import json
from pathlib import Path

from src.compiler.dependency_tuple_compiler import (
    compile_dependency_tuples,
    project_allowed_values,
)


def _write_ready_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["field_code", "option_value"],
        )
        writer.writeheader()
        for field, value in [
            ("CASING_MATERIAL", "316 SS"),
            ("CASING_MATERIAL", "Cast Steel"),
            ("FLANGE_CONFIGURATION", "150# Raised"),
            ("FLANGE_CONFIGURATION", "300# Raised"),
            ("SEAL_OPTION", "Included"),
            ("SEAL_OPTION", "None"),
            ("GLAND_TYPE", "Flush"),
            ("GLAND_TYPE", "Quench"),
            ("FLUSH_PLAN", "Plan 11"),
            ("FLUSH_PLAN", "Plan 32"),
            ("BARRIER_PLAN", "None"),
            ("BARRIER_PLAN", "Plan 53"),
        ]:
            writer.writerow(
                {
                    "field_code": field,
                    "option_value": value,
                }
            )


def _fixture(tmp_path: Path) -> Path:
    exports = tmp_path / "exports"
    profiles = tmp_path / "config" / "dependency_profiles"
    profiles.mkdir(parents=True)
    exports.mkdir(parents=True)

    reconciliation = {
        "reconciliation_version": "M023.1.1-TEST",
        "summary": {"error_count": 0},
        "field_reconciliation": [
            {
                "canonical_field_code": "SERIES",
                "labels": ["Series"],
            },
            {
                "canonical_field_code": "CASING_MATERIAL",
                "labels": ["Casing Material"],
            },
            {
                "canonical_field_code": "FLANGE_CONFIGURATION",
                "labels": ["Flange Configuration"],
            },
            {
                "canonical_field_code": "SEAL_OPTION",
                "labels": ["Seal Option"],
            },
            {
                "canonical_field_code": "GLAND_TYPE",
                "labels": ["Gland Type"],
            },
            {
                "canonical_field_code": "FLUSH_PLAN",
                "labels": ["Flush Plan"],
            },
            {
                "canonical_field_code": "BARRIER_PLAN",
                "labels": ["Barrier Plan"],
            },
        ],
        "logic_option_domains": [
            {
                "field_label": "Casing Material",
                "headers": ["Casing Material"],
                "rows": [
                    {"Casing Material": "316 SS"},
                    {"Casing Material": "Cast Steel"},
                ],
            },
            {
                "field_label": "Flange Configuration",
                "headers": ["Flange Configuration"],
                "rows": [
                    {"Flange Configuration": "150# Raised"},
                    {"Flange Configuration": "300# Raised"},
                ],
            },
            {
                "field_label": "Seal Option",
                "headers": ["Seal Option"],
                "rows": [
                    {"Seal Option": "Included"},
                    {"Seal Option": "None"},
                ],
            },
            {
                "field_label": "Gland Type",
                "headers": ["Gland Type"],
                "rows": [
                    {"Gland Type": "Flush"},
                    {"Gland Type": "Quench"},
                ],
            },
            {
                "field_label": "Flush Plan",
                "headers": ["Flush Plan"],
                "rows": [
                    {"Flush Plan": "Plan 11"},
                    {"Flush Plan": "Plan 32"},
                ],
            },
            {
                "field_label": "Barrier Plan",
                "headers": ["Barrier Plan"],
                "rows": [
                    {"Barrier Plan": "None"},
                    {"Barrier Plan": "Plan 53"},
                ],
            },
        ],
        "dependencies": [
            {
                "table_name": "Table64",
                "table_range": "A1:C3",
                "field_labels": [
                    "Series",
                    "Casing Material",
                    "Flange Configuration",
                ],
                "row_count": 2,
                "rows": [
                    {
                        "Series": "RA2096",
                        "Casing Material": "316 SS",
                        "Flange Configuration": "150# Raised",
                    },
                    {
                        "Series": "RA3146",
                        "Casing Material": "Cast Steel",
                        "Flange Configuration": "300# Raised",
                    },
                ],
            },
            {
                "table_name": "Table100",
                "table_range": "E1:H4",
                "field_labels": [
                    "Seal Option",
                    "Gland Type",
                    "Flush Plan",
                    "Barrier Plan",
                ],
                "row_count": 3,
                "rows": [
                    {
                        "Seal Option": "Included",
                        "Gland Type": "Flush",
                        "Flush Plan": "Plan 11",
                        "Barrier Plan": "None",
                    },
                    {
                        "Seal Option": "Included",
                        "Gland Type": "Quench",
                        "Flush Plan": "Plan 32",
                        "Barrier Plan": "Plan 53",
                    },
                    # duplicate: compiler should dedupe
                    {
                        "Seal Option": "Included",
                        "Gland Type": "Flush",
                        "Flush Plan": "Plan 11",
                        "Barrier Plan": "None",
                    },
                ],
            },
        ],
    }

    (exports / "m023_dean_source_reconciliation.json").write_text(
        json.dumps(reconciliation),
        encoding="utf-8",
    )

    _write_ready_csv(exports / "m023_dean_applicability_ready.csv")

    profile = {
        "family_code": "DEAN",
        "version": "M023.3-TEST",
        "reconciliation_json": "exports/m023_dean_source_reconciliation.json",
        "applicability_ready_csv": "exports/m023_dean_applicability_ready.csv",
        "rule_type": "ALLOWED_TUPLES",
        "identity_fields": ["SERIES", "SIZE"],
        "normalization": {
            "trim_text": True,
            "casefold_for_validation": True,
        },
        "safety": {
            "do_not_infer_direction": True,
            "do_not_infer_blank_as_wildcard": True,
            "unknown_field_blocks_rule": True,
            "unknown_option_blocks_tuple": True,
            "duplicate_tuples_are_deduplicated": True,
        },
    }

    profile_path = profiles / "dean.json"
    profile_path.write_text(
        json.dumps(profile),
        encoding="utf-8",
    )
    return profile_path


def test_compiles_multicolumn_codependency_as_allowed_tuples(tmp_path: Path) -> None:
    profile = _fixture(tmp_path)
    report = compile_dependency_tuples(
        project_root=tmp_path,
        profile_path=profile,
    )

    assert report["summary"]["error_count"] == 0
    assert report["summary"]["publication_gate"] == "PASS"
    assert report["summary"]["ready_rule_count"] == 2

    table100 = [
        x for x in report["rules"] if x["rule_code"] == "Table100"
    ][0]

    assert table100["field_count"] == 4
    assert table100["ready_tuple_count"] == 2
    assert table100["duplicate_tuple_count"] == 1


def test_projection_is_directionless_and_state_aware(tmp_path: Path) -> None:
    profile = _fixture(tmp_path)
    report = compile_dependency_tuples(
        project_root=tmp_path,
        profile_path=profile,
    )

    tuples = [
        x for x in report["tuples"] if x["rule_code"] == "Table100"
    ]

    flush_values = project_allowed_values(
        tuples=tuples,
        current_selection={
            "SEAL_OPTION": "Included",
            "GLAND_TYPE": "Flush",
        },
        target_field="FLUSH_PLAN",
    )

    assert flush_values == ["Plan 11"]

    # Reverse projection proves there is no parent/child hardcoding.
    gland_values = project_allowed_values(
        tuples=tuples,
        current_selection={
            "FLUSH_PLAN": "Plan 32",
            "BARRIER_PLAN": "Plan 53",
        },
        target_field="GLAND_TYPE",
    )

    assert gland_values == ["Quench"]


def test_identity_field_is_allowed_without_config_option_domain(tmp_path: Path) -> None:
    profile = _fixture(tmp_path)
    report = compile_dependency_tuples(
        project_root=tmp_path,
        profile_path=profile,
    )

    table64 = [
        x for x in report["rules"] if x["rule_code"] == "Table64"
    ][0]

    assert table64["publication_status"] == "READY"
    assert table64["ready_tuple_count"] == 2


def test_unknown_dependency_option_is_blocked_not_published(tmp_path: Path) -> None:
    profile = _fixture(tmp_path)

    reconciliation_path = (
        tmp_path / "exports" / "m023_dean_source_reconciliation.json"
    )
    data = json.loads(
        reconciliation_path.read_text(encoding="utf-8")
    )

    data["dependencies"][1]["rows"].append(
        {
            "Seal Option": "Included",
            "Gland Type": "Flush",
            "Flush Plan": "UNMAPPED PLAN",
            "Barrier Plan": "None",
        }
    )

    reconciliation_path.write_text(
        json.dumps(data),
        encoding="utf-8",
    )

    report = compile_dependency_tuples(
        project_root=tmp_path,
        profile_path=profile,
    )

    published_values = {
        item["value"]
        for row in report["tuples"]
        for item in row["selections"]
    }

    assert "UNMAPPED PLAN" not in published_values
    assert any(
        row["review_type"] == "UNKNOWN_DEPENDENCY_OPTION"
        for row in report["reviews"]
    )

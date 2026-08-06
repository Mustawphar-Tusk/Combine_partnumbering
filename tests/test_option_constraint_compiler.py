import json
from pathlib import Path

from openpyxl import Workbook

from src.compiler.option_constraint_compiler import (
    compile_option_constraints,
)


def test_option_constraint_compiler_separates_invalid_markers(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    workbook_dir = project_root / "workbooks" / "Test"
    workbook_dir.mkdir(parents=True)

    workbook_path = workbook_dir / "Test.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Logic"
    worksheet["A2"] = "Allowed"
    worksheet["B2"] = "01"
    worksheet["A3"] = "Invalid"
    worksheet["B3"] = "ERR"
    worksheet["D2"] = '=IF(A2="Allowed","01","ERR")'
    workbook.save(workbook_path)

    discovery = {
        "records": [
            {
                "family_code": "TEST",
                "role": "logic",
                "discovery_status": "discovered",
                "relative_path": "workbooks/Test/Test.xlsx",
            }
        ]
    }
    discovery_path = project_root / "discovery.json"
    discovery_path.write_text(json.dumps(discovery), encoding="utf-8")

    profile_directory = project_root / "profiles"
    profile_directory.mkdir()

    profile = {
        "family_code": "TEST",
        "workbook_role": "logic",
        "option_sources": [
            {
                "worksheet_name": "Logic",
                "field_code": "OPTION",
                "description_column": "A",
                "hex_column": "B",
                "row_from": 2,
                "row_to": 3
            }
        ],
        "dependency_sources": [
            {
                "worksheet_name": "Logic",
                "child_field_code": "OPTION",
                "parent_field_codes": ["PARENT"],
                "formula_cells": ["D2"],
                "dependency_type": "filters_options"
            }
        ],
        "explicit_constraints": []
    }

    (profile_directory / "test.json").write_text(
        json.dumps(profile),
        encoding="utf-8",
    )

    report = compile_option_constraints(
        project_root=project_root,
        discovery_path=discovery_path,
        profile_directory=profile_directory,
    )

    assert report.option_count == 1
    assert report.options[0].option_description == "Allowed"
    assert report.legacy_marker_count == 1
    assert report.constraint_count == 1
    assert report.constraints[0].rule_type == "reject"

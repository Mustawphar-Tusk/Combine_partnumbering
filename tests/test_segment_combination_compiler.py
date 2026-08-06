import json
from pathlib import Path

from openpyxl import Workbook

from src.compiler.segment_combination_compiler import (
    compile_segment_combinations,
    to_base36,
)


def test_base36_conversion() -> None:
    assert to_base36(1) == "1"
    assert to_base36(35) == "Z"
    assert to_base36(36) == "10"


def test_segment_combination_compiler(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    workbook_dir = project_root / "workbooks" / "Test"
    workbook_dir.mkdir(parents=True)

    workbook_path = workbook_dir / "Test.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Options"
    worksheet["C2"] = "=D2&E2"
    worksheet["D2"] = "A"
    worksheet["E2"] = "B"
    worksheet["J2"] = 36
    workbook.save(workbook_path)

    discovery = {
        "records": [
            {
                "family_code": "TEST",
                "role": "configuration",
                "discovery_status": "discovered",
                "relative_path": "workbooks/Test/Test.xlsx",
            }
        ]
    }

    discovery_path = project_root / "discovery.json"
    discovery_path.write_text(
        json.dumps(discovery),
        encoding="utf-8",
    )

    profile = {
        "family_code": "TEST",
        "workbook_role": "configuration",
        "segments": [
            {
                "segment_code": "OPTIONS",
                "segment_name": "Options",
                "worksheet_name": "Options",
                "row_from": 2,
                "row_to": 2,
                "combination_key_column": None,
                "id_column": "J",
                "expected_width": 2,
                "selection_columns": {
                    "FIELD_A": "D",
                    "FIELD_B": "E",
                },
            }
        ],
    }

    profile_path = project_root / "profile.json"
    profile_path.write_text(
        json.dumps(profile),
        encoding="utf-8",
    )

    report = compile_segment_combinations(
        project_root=project_root,
        discovery_path=discovery_path,
        profile_path=profile_path,
    )

    assert report.segment_count == 1
    assert report.combination_count == 1
    assert report.issue_count == 0
    assert report.combinations[0].segment_value == "10"

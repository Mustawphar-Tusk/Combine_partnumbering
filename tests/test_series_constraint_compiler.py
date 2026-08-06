import json
from pathlib import Path

from openpyxl import Workbook

from src.compiler.series_constraint_compiler import (
    compile_series_constraints,
)


def test_series_constraint_compiler(
    tmp_path: Path,
) -> None:
    workbook_dir = (
        tmp_path
        / "workbooks"
        / "Fybroc"
    )
    workbook_dir.mkdir(parents=True)

    workbook_path = (
        workbook_dir
        / "Constraints.xlsx"
    )

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "MAIN"
    worksheet["B3"] = "Alt_Size"
    worksheet["C3"] = "1x1.5x6"
    worksheet["E3"] = "1500"
    worksheet["F3"] = "1530"
    workbook.save(workbook_path)

    discovery = tmp_path / "discovery.json"
    discovery.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "family_code": "FYBROC",
                        "role": (
                            "attributes_and_constraints"
                        ),
                        "discovery_status": "discovered",
                        "relative_path": (
                            "workbooks/Fybroc/"
                            "Constraints.xlsx"
                        ),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    profile = tmp_path / "profile.json"
    profile.write_text(
        json.dumps(
            {
                "family_code": "FYBROC",
                "workbook_role": (
                    "attributes_and_constraints"
                ),
                "worksheet_name": "MAIN",
                "row_from": 3,
                "field_code_column": "B",
                "option_value_column": "C",
                "series_columns": {
                    "E": "1500",
                    "F": "1530",
                },
                "field_code_map": {
                    "Alt_Size": "SIZE",
                },
            }
        ),
        encoding="utf-8",
    )

    report = compile_series_constraints(
        project_root=tmp_path,
        discovery_path=discovery,
        profile_path=profile,
    )

    assert report.field_count == 1
    assert report.option_count == 1
    assert report.relation_count == 2
    assert {
        row.series_code
        for row in report.candidates
    } == {"1500", "1530"}

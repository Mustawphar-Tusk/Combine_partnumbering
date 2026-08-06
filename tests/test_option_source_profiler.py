import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.worksheet.datavalidation import DataValidation

from src.compiler.option_source_profiler import profile_option_sources


def test_option_source_profiler_finds_validation_and_table(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    workbook_dir = project_root / "workbooks" / "Test"
    workbook_dir.mkdir(parents=True)

    workbook_path = workbook_dir / "Test.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Options"
    worksheet["A1"] = "Description"
    worksheet["B1"] = "Hex Code"
    worksheet["A2"] = "Option A"
    worksheet["B2"] = "01"

    validation = DataValidation(
        type="list",
        formula1='"Option A,Option B"',
    )
    worksheet.add_data_validation(validation)
    validation.add("D2")
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
    discovery_path.write_text(
        json.dumps(discovery),
        encoding="utf-8",
    )

    profile = {
        "table_scan_rows": 10,
        "table_scan_columns": 10,
        "workbooks": [
            {
                "family_code": "TEST",
                "workbook_role": "logic",
            }
        ],
    }
    profile_path = project_root / "profile.json"
    profile_path.write_text(
        json.dumps(profile),
        encoding="utf-8",
    )

    report = profile_option_sources(
        project_root=project_root,
        discovery_path=discovery_path,
        profile_path=profile_path,
    )

    assert report.validation_count == 1
    assert report.option_table_count >= 1
    assert report.option_tables[0].description_column == "A"
    assert report.option_tables[0].hex_column == "B"

import json
from pathlib import Path

from openpyxl import Workbook

from src.compiler.attribute_metadata_compiler import (
    compile_attribute_metadata,
)


def test_attribute_compiler(tmp_path: Path) -> None:
    workbook_dir = tmp_path / "workbooks" / "Test"
    workbook_dir.mkdir(parents=True)
    workbook_path = workbook_dir / "Test.xlsx"

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Attributes"
    worksheet["F8"] = "Series A"
    worksheet["G8"] = "A"
    workbook.save(workbook_path)

    discovery_path = tmp_path / "discovery.json"
    discovery_path.write_text(
        json.dumps({
            "records": [{
                "family_code": "TEST",
                "role": "configuration",
                "discovery_status": "discovered",
                "relative_path": "workbooks/Test/Test.xlsx",
            }]
        }),
        encoding="utf-8",
    )

    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps({
            "family_code": "TEST",
            "workbook_role": "configuration",
            "worksheet_name": "Attributes",
            "row_from": 8,
            "row_to": 20,
            "max_consecutive_blank_rows": 2,
            "attributes": [{
                "field_code": "SERIES",
                "field_name": "Series",
                "display_column": "F",
                "code_column": "G",
            }],
        }),
        encoding="utf-8",
    )

    report = compile_attribute_metadata(
        project_root=tmp_path,
        discovery_path=discovery_path,
        profile_path=profile_path,
    )

    assert report.field_count == 1
    assert report.value_count == 1
    assert report.values[0].identifier_code == "A"

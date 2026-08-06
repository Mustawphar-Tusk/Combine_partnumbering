import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.workbook.defined_name import DefinedName

from src.compiler.defined_name_option_compiler import (
    compile_defined_name_options,
)


def test_defined_name_option_compiler_extracts_one_column_list(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    workbook_dir = project_root / "workbooks" / "Test"
    workbook_dir.mkdir(parents=True)

    workbook_path = workbook_dir / "Test.xlsx"
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Options"
    worksheet["A2"] = "Option A"
    worksheet["A3"] = "Option B"

    workbook.defined_names.add(
        DefinedName(
            "MyOptions",
            attr_text="'Options'!$A$2:$A$3",
        )
    )
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
        "input_worksheet": "Smart",
        "mappings": [
            {
                "input_range": "B2",
                "defined_name": "MyOptions",
                "field_code": "MY_FIELD",
                "field_name": "My Field",
            }
        ],
    }

    profile_path = project_root / "profile.json"
    profile_path.write_text(
        json.dumps(profile),
        encoding="utf-8",
    )

    report = compile_defined_name_options(
        project_root=project_root,
        discovery_path=discovery_path,
        profile_path=profile_path,
    )

    assert report.field_count == 1
    assert report.option_count == 2
    assert report.issue_count == 0
    assert report.options[0].option_description == "Option A"

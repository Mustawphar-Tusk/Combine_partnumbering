import json
from pathlib import Path

from openpyxl import Workbook

from src.compiler.configuration_model import (
    compile_configuration_model,
)


def test_configuration_model_compiles_numbered_and_column_profiles(
    tmp_path: Path,
) -> None:
    project_root = tmp_path
    (project_root / "workbooks" / "Alpha").mkdir(parents=True)
    (project_root / "workbooks" / "Beta").mkdir(parents=True)
    profile_dir = project_root / "profiles"
    profile_dir.mkdir()

    alpha_path = project_root / "workbooks" / "Alpha" / "Alpha.xlsx"
    alpha = Workbook()
    alpha_ws = alpha.active
    alpha_ws.title = "Data"
    alpha_ws["A1"] = 1
    alpha_ws["B1"] = "Series"
    alpha_ws["A2"] = 2
    alpha_ws["B2"] = "Size"
    alpha.save(alpha_path)

    beta_path = project_root / "workbooks" / "Beta" / "Beta.xlsx"
    beta = Workbook()
    beta.active.title = "Smart"
    beta.save(beta_path)

    discovery = {
        "records": [
            {
                "family_code": "ALPHA",
                "role": "configuration",
                "discovery_status": "discovered",
                "relative_path": "workbooks/Alpha/Alpha.xlsx",
            },
            {
                "family_code": "BETA",
                "role": "configuration",
                "discovery_status": "discovered",
                "relative_path": "workbooks/Beta/Beta.xlsx",
            },
        ]
    }
    discovery_path = project_root / "discovery.json"
    discovery_path.write_text(json.dumps(discovery), encoding="utf-8")

    alpha_profile = {
        "family_code": "ALPHA",
        "workbook_role": "configuration",
        "worksheet_name": "Data",
        "strategy": {
            "type": "numbered_rows",
            "minimum_sequence": 1,
            "maximum_sequence": 2,
            "scan_max_rows": 10,
            "scan_max_columns": 5,
            "label_search_width": 2,
            "sections": [
                {
                    "section_code": "PRIMARY",
                    "section_name": "Primary",
                    "sequence_from": 1,
                    "sequence_to": 2,
                }
            ],
        },
    }
    beta_profile = {
        "family_code": "BETA",
        "workbook_role": "configuration",
        "worksheet_name": "Smart",
        "strategy": {
            "type": "column_workflow",
            "sections": [
                {
                    "section_code": "PRIMARY",
                    "section_name": "Primary",
                    "fields": [
                        {
                            "field_code": "SERIES",
                            "field_name": "Series",
                            "columns": ["E"],
                            "display_order": 10,
                        }
                    ],
                }
            ],
        },
    }

    (profile_dir / "alpha.json").write_text(
        json.dumps(alpha_profile),
        encoding="utf-8",
    )
    (profile_dir / "beta.json").write_text(
        json.dumps(beta_profile),
        encoding="utf-8",
    )

    report = compile_configuration_model(
        project_root=project_root,
        discovery_path=discovery_path,
        profile_directory=profile_dir,
    )

    assert report.section_count == 2
    assert report.field_count == 3
    assert {field.field_code for field in report.fields} == {
        "SERIES_001",
        "SIZE_002",
        "SERIES",
    }

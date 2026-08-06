from pathlib import Path

from scripts.load_segment_combinations_to_staging import (
    count_rows,
    sha256_file,
    validate_header,
)


def test_loader_helpers(tmp_path: Path) -> None:
    path = tmp_path / "rows.csv"
    path.write_text(
        "family_code,workbook_role,workbook_name,worksheet_name,"
        "segment_code,segment_name,source_row,source_id,"
        "segment_value,expected_width,combination_key,"
        "selections_json,source_cells_json,source_profile\n"
        'FYBROC,role,book,sheet,OPTIONS,Options,12,1,01,2,key,'
        '"{""A"":""B""}","{""A"":""D12""}",profile\n',
        encoding="utf-8",
    )

    validate_header(path)
    assert count_rows(path) == 1
    assert len(sha256_file(path)) == 64

import json
from pathlib import Path

def test_motor_assembly_profile() -> None:
    root = Path(__file__).resolve().parents[1]
    profile = json.loads(
        (root / "config" / "segment_profiles" / "fybroc_segment_combinations.json")
        .read_text(encoding="utf-8")
    )
    motor = next(x for x in profile["segments"] if x["segment_code"] == "MOTOR_ASSEMBLY")
    assert motor["worksheet_name"] == " Motor Assy"
    assert motor["row_from"] == 27
    assert motor["row_to"] == 728
    assert motor["id_column"] == "P"
    assert motor["expected_width"] == 3
    assert len(motor["selection_columns"]) == 11

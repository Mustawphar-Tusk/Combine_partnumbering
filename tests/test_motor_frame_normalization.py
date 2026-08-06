from src.configuration_engine.value_normalization import (
    canonical_engineering_value,
)


def test_jm_series_frame_matches_numeric_motor_frame() -> None:
    series = canonical_engineering_value(
        field_code="MOTOR_FRAME",
        value="143JM",
        source_type="SERIES",
    )
    combination = canonical_engineering_value(
        field_code="MOTOR_FRAME",
        value="143",
        source_type="COMBINATION",
    )

    assert series == combination == "143"


def test_t_and_ts_reduce_to_same_series_frame_stem() -> None:
    assert (
        canonical_engineering_value(
            field_code="MOTOR_FRAME",
            value="284T",
            source_type="SERIES",
        )
        == "284"
    )
    assert (
        canonical_engineering_value(
            field_code="MOTOR_FRAME",
            value="284TS",
            source_type="SERIES",
        )
        == "284"
    )
    assert (
        canonical_engineering_value(
            field_code="MOTOR_FRAME",
            value="284JM",
            source_type="SERIES",
        )
        == "284"
    )


def test_motor_frame_orientation_is_not_encoded_in_series_key() -> None:
    t_value = canonical_engineering_value(
        field_code="MOTOR_FRAME",
        value="284",
        context={"MOTOR_ORIENTATION": "Hor T"},
        source_type="COMBINATION",
    )
    ts_value = canonical_engineering_value(
        field_code="MOTOR_FRAME",
        value="284",
        context={"MOTOR_ORIENTATION": "Hor TS"},
        source_type="COMBINATION",
    )

    assert t_value == ts_value == "284"

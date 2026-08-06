from src.configuration_engine.dependency_projection import (
    DependencyOption,
    SqlFieldDependencyRepository,
)


def test_no_modification_is_terminal() -> None:
    result = (
        SqlFieldDependencyRepository
        ._apply_modification_sequence(
            target_field_code=(
                "MOTOR_MODIFICATION_2"
            ),
            options=(
                DependencyOption(
                    "No Modification",
                    "X",
                ),
                DependencyOption(
                    "Class H Insulation",
                    "8",
                ),
            ),
            current_selections={
                "MOTOR_MODIFICATION_1": (
                    "No Modification"
                )
            },
        )
    )

    assert result == (
        DependencyOption(
            "No Modification",
            "X",
        ),
    )


def test_selected_modification_is_not_repeated() -> None:
    result = (
        SqlFieldDependencyRepository
        ._apply_modification_sequence(
            target_field_code=(
                "MOTOR_MODIFICATION_2"
            ),
            options=(
                DependencyOption(
                    "No Modification",
                    "X",
                ),
                DependencyOption(
                    "First",
                    "1",
                ),
                DependencyOption(
                    "Second",
                    "2",
                ),
            ),
            current_selections={
                "MOTOR_MODIFICATION_1": "First"
            },
        )
    )

    assert {
        item.display_value
        for item in result
    } == {
        "No Modification",
        "Second",
    }

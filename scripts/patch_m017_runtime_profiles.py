from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read(path: Path) -> dict:
    return json.loads(
        path.read_text(encoding="utf-8")
    )


def write(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    runtime_dir = (
        PROJECT_ROOT
        / "config"
        / "runtime_profiles"
    )

    navigation_path = (
        runtime_dir
        / "fybroc_allowable_navigation.json"
    )
    navigation = read(navigation_path)
    fields = navigation["field_order"]

    replacement = [
        "MOTOR_MODIFICATION_1",
        "MOTOR_MODIFICATION_2",
        "MOTOR_MODIFICATION_3",
    ]

    if "MOTOR_MODIFICATIONS" in fields:
        index = fields.index(
            "MOTOR_MODIFICATIONS"
        )
        fields[index:index + 1] = replacement
    else:
        for field in replacement:
            if field not in fields:
                testing_index = fields.index(
                    "TESTING"
                )
                fields.insert(
                    testing_index,
                    field,
                )

    write(navigation_path, navigation)

    available_path = (
        runtime_dir
        / "fybroc_available_options.json"
    )
    available = read(available_path)
    aliases = available.setdefault(
        "attribute_field_aliases",
        {},
    )

    for field in replacement:
        aliases[field] = "MOTOR_MODIFICATIONS"

    write(available_path, available)

    identifier_path = (
        runtime_dir
        / "fybroc_identifier_generation.json"
    )
    identifier = read(identifier_path)

    replaced = False

    for index, segment in enumerate(
        identifier["segments"]
    ):
        if segment["segment_code"] != (
            "MOTOR_MODIFICATIONS"
        ):
            continue

        identifier["segments"][index] = {
            "segment_code": "MOTOR_MODIFICATIONS",
            "resolution_type": "ATTRIBUTE_SEQUENCE",
            "source_field_code": (
                "MOTOR_MODIFICATIONS"
            ),
            "field_codes": replacement,
        }
        replaced = True
        break

    if not replaced:
        raise RuntimeError(
            "MOTOR_MODIFICATIONS identifier segment "
            "was not found."
        )

    write(identifier_path, identifier)

    preferences_path = (
        runtime_dir
        / "fybroc_session_test_preferences.json"
    )
    preferences = read(preferences_path)
    preferences.pop(
        "MOTOR_MODIFICATIONS",
        None,
    )
    preferences["IMPELLER_TRIM"] = {
        "exact": "4.000"
    }

    for field in replacement:
        preferences[field] = {
            "exact": "No Modification"
        }

    preferences["TESTING"] = {
        "exact": "-"
    }

    write(preferences_path, preferences)

    print(
        "Navigation fields:",
        len(navigation["field_order"]),
    )
    print(
        "Motor modification slots:",
        ", ".join(replacement),
    )
    print(
        "Identifier resolution:",
        "ATTRIBUTE_SEQUENCE",
    )


if __name__ == "__main__":
    main()

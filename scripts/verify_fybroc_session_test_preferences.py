from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    runtime_dir = (
        PROJECT_ROOT
        / "config"
        / "runtime_profiles"
    )

    navigation = json.loads(
        (
            runtime_dir
            / "fybroc_allowable_navigation.json"
        ).read_text(encoding="utf-8")
    )
    preferences = json.loads(
        (
            runtime_dir
            / "fybroc_session_test_preferences.json"
        ).read_text(encoding="utf-8")
    )

    fields = tuple(navigation["field_order"])

    missing = [
        field
        for field in fields
        if field not in preferences
    ]
    extra = [
        field
        for field in preferences
        if field not in fields
    ]
    incomplete = [
        field
        for field in fields
        if field in preferences
        and not (
            preferences[field].get("exact")
            or preferences[field].get("contains")
        )
    ]

    output = {
        "navigation_field_count": len(fields),
        "preference_count": len(preferences),
        "missing_preferences": missing,
        "extra_preferences": extra,
        "incomplete_preferences": incomplete,
        "complete": not (
            missing
            or extra
            or incomplete
        ),
    }

    print(json.dumps(output, indent=2))

    if not output["complete"]:
        raise SystemExit(
            "Deterministic scenario preferences "
            "are incomplete."
        )


if __name__ == "__main__":
    main()

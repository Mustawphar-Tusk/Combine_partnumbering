from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_every_navigation_field_has_preference() -> None:
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

    field_order = tuple(
        navigation["field_order"]
    )

    assert len(field_order) == 41
    assert set(preferences) == set(field_order)

    for field_code in field_order:
        preference = preferences[field_code]

        assert isinstance(preference, dict)
        assert bool(
            preference.get("exact")
            or preference.get("contains")
        ), (
            f"{field_code} must define exact or contains."
        )


def test_preference_file_follows_navigation_order() -> None:
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

    assert tuple(preferences) == tuple(
        navigation["field_order"]
    )

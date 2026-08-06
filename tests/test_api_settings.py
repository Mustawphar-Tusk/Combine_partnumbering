from __future__ import annotations

from pathlib import Path

import pytest

from src.api.settings import (
    ApiConfigurationError,
    ApiSettings,
)


def test_environment_requires_token_secret(
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        "CONFIGURATION_TOKEN_SECRET",
        raising=False,
    )

    with pytest.raises(
        ApiConfigurationError
    ):
        ApiSettings.from_environment(
            project_root=Path.cwd()
        )


def test_environment_builds_windows_auth_connection(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "CONFIGURATION_TOKEN_SECRET",
        "x" * 40,
    )
    monkeypatch.delenv(
        "DB_USERNAME",
        raising=False,
    )
    monkeypatch.delenv(
        "DB_PASSWORD",
        raising=False,
    )

    settings = ApiSettings.from_environment(
        project_root=Path.cwd()
    )

    assert (
        "Trusted_Connection=yes"
        in settings.connection_string
    )
    assert (
        "PumpConfiguratorDB"
        in settings.connection_string
    )

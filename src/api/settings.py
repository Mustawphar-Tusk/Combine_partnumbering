from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


class ApiConfigurationError(RuntimeError):
    """Raised when required API configuration is missing or unsafe."""


def _boolean_environment(
    name: str,
    *,
    default: bool,
) -> bool:
    raw_value = os.getenv(name)

    if raw_value is None:
        return default

    value = raw_value.strip().casefold()

    if value in {"1", "true", "yes", "on"}:
        return True

    if value in {"0", "false", "no", "off"}:
        return False

    raise ApiConfigurationError(
        f"{name} must be true or false."
    )


@dataclass(frozen=True)
class ApiSettings:
    project_root: Path
    token_secret: str
    connection_string: str
    environment: str = "development"
    title: str = "Pump Configuration API"
    version: str = "0.19.0"
    docs_enabled: bool = True

    @classmethod
    def from_environment(
        cls,
        *,
        project_root: Path,
    ) -> "ApiSettings":
        secret = os.getenv(
            "CONFIGURATION_TOKEN_SECRET",
            "",
        ).strip()

        if len(secret) < 32:
            raise ApiConfigurationError(
                "CONFIGURATION_TOKEN_SECRET must contain "
                "at least 32 characters."
            )

        driver = os.getenv(
            "DB_DRIVER",
            "ODBC Driver 18 for SQL Server",
        ).strip()
        server = os.getenv(
            "DB_SERVER",
            "localhost",
        ).strip()
        database = os.getenv(
            "DB_DATABASE",
            "PumpConfiguratorDB",
        ).strip()
        username = os.getenv(
            "DB_USERNAME",
            "",
        ).strip()
        password = os.getenv(
            "DB_PASSWORD",
            "",
        )

        if bool(username) != bool(password):
            raise ApiConfigurationError(
                "DB_USERNAME and DB_PASSWORD must either "
                "both be provided or both be omitted."
            )

        authentication = (
            f"UID={username};PWD={password};"
            if username
            else "Trusted_Connection=yes;"
        )

        connection_string = (
            f"DRIVER={{{driver}}};"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"{authentication}"
            "Encrypt=yes;"
            "TrustServerCertificate=yes;"
        )

        return cls(
            project_root=project_root,
            token_secret=secret,
            connection_string=connection_string,
            environment=os.getenv(
                "API_ENVIRONMENT",
                "development",
            ).strip(),
            title=os.getenv(
                "API_TITLE",
                "Pump Configuration API",
            ).strip(),
            version=os.getenv(
                "API_VERSION",
                "0.19.0",
            ).strip(),
            docs_enabled=_boolean_environment(
                "API_DOCS_ENABLED",
                default=True,
            ),
        )

    @classmethod
    def for_testing(
        cls,
        *,
        project_root: Path,
    ) -> "ApiSettings":
        return cls(
            project_root=project_root,
            token_secret=(
                "test-only-configuration-token-secret-"
                "0123456789"
            ),
            connection_string=(
                "DRIVER={ODBC Driver 18 for SQL Server};"
                "SERVER=unused;"
                "DATABASE=unused;"
                "Trusted_Connection=yes;"
            ),
            environment="test",
            docs_enabled=True,
        )

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.api.settings import ApiSettings


class UnsupportedPumpFamilyError(LookupError):
    """Raised when the API has no runtime for a pump family."""


@dataclass(frozen=True)
class ConfigurationFamilyGateway:
    family_code: str
    navigation_session: Any
    persistent_session: Any


class ConfigurationRuntimeRegistry:
    def __init__(
        self,
        gateways: dict[
            str,
            ConfigurationFamilyGateway,
        ],
    ) -> None:
        self._gateways = {
            family_code.strip().upper(): gateway
            for family_code, gateway
            in gateways.items()
        }

    @property
    def family_codes(self) -> tuple[str, ...]:
        return tuple(sorted(self._gateways))

    def get(
        self,
        family_code: str,
    ) -> ConfigurationFamilyGateway:
        normalized = family_code.strip().upper()

        try:
            return self._gateways[normalized]
        except KeyError as exc:
            raise UnsupportedPumpFamilyError(
                f"Pump family {normalized} is not configured."
            ) from exc


def build_runtime_registry(
    settings: ApiSettings,
) -> ConfigurationRuntimeRegistry:
    # Imported lazily so OpenAPI and isolated API tests do not
    # connect to SQL Server during module import.
    from src.configuration_engine.fybroc_persistence_runtime import (
        build_fybroc_persistence_runtime,
    )

    fybroc = build_fybroc_persistence_runtime(
        project_root=settings.project_root,
        connection_string=settings.connection_string,
        token_secret=settings.token_secret,
    )

    return ConfigurationRuntimeRegistry(
        {
            "FYBROC": ConfigurationFamilyGateway(
                family_code="FYBROC",
                navigation_session=(
                    fybroc.configuration_runtime.session
                ),
                persistent_session=(
                    fybroc.persistent_session
                ),
            )
        }
    )

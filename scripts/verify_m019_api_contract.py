from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.runtime_registry import (
    ConfigurationFamilyGateway,
    ConfigurationRuntimeRegistry,
)
from src.api.settings import ApiSettings


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class UnusedSession:
    pass


def main() -> None:
    registry = ConfigurationRuntimeRegistry(
        {
            "FYBROC": ConfigurationFamilyGateway(
                family_code="FYBROC",
                navigation_session=UnusedSession(),
                persistent_session=UnusedSession(),
            )
        }
    )

    app = create_app(
        settings=ApiSettings.for_testing(
            project_root=PROJECT_ROOT
        ),
        runtime_registry=registry,
    )

    with TestClient(app) as client:
        schema = client.get(
            "/openapi.json"
        ).json()

    paths = sorted(schema["paths"])
    components = schema["components"]["schemas"]

    output = {
        "configuration_operations": [
            path
            for path in paths
            if "/configurations/" in path
        ],
        "start_request_fields": sorted(
            components[
                "StartConfigurationRequest"
            ].get("properties", {})
        ),
        "advance_request_fields": sorted(
            components[
                "AdvanceConfigurationRequest"
            ]["properties"]
        ),
        "finalize_request_fields": sorted(
            components[
                "FinalizeConfigurationRequest"
            ]["properties"]
        ),
        "engineering_field_value_payload_present": (
            False
        ),
        "closed_contract": True,
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

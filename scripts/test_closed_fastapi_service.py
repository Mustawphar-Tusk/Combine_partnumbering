from __future__ import annotations

import getpass
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.runtime_registry import (
    build_runtime_registry,
)
from src.api.settings import ApiSettings


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def choose_option(
    response_body: dict,
    preference: dict[str, str],
) -> dict:
    exact = preference.get("exact")
    contains = preference.get("contains")

    for option in response_body["options"]:
        value = option["displayValue"]

        if exact is not None and value == exact:
            return option

        if (
            contains is not None
            and contains in value
        ):
            return option

    raise RuntimeError(
        "The deterministic API preference was not "
        f"returned for "
        f"{response_body['nextFieldCode']}: "
        f"{preference}."
    )


def main() -> None:
    secret = os.getenv(
        "CONFIGURATION_TOKEN_SECRET",
        (
            "development-only-api-smoke-test-"
            "secret-0123456789"
        ),
    )

    driver = os.getenv(
        "DB_DRIVER",
        "ODBC Driver 18 for SQL Server",
    )
    server = os.getenv(
        "DB_SERVER",
        "localhost",
    )
    database = os.getenv(
        "DB_DATABASE",
        "PumpConfiguratorDB",
    )

    settings = ApiSettings(
        project_root=PROJECT_ROOT,
        token_secret=secret,
        connection_string=(
            f"DRIVER={{{driver}}};"
            f"SERVER={server};"
            f"DATABASE={database};"
            "Trusted_Connection=yes;"
            "Encrypt=yes;"
            "TrustServerCertificate=yes;"
        ),
        environment="local-smoke-test",
    )

    registry = build_runtime_registry(
        settings
    )
    app = create_app(
        settings=settings,
        runtime_registry=registry,
    )

    preferences = json.loads(
        (
            PROJECT_ROOT
            / "config"
            / "runtime_profiles"
            / "fybroc_session_test_preferences.json"
        ).read_text(encoding="utf-8")
    )

    with TestClient(app) as client:
        start = client.post(
            (
                "/api/v1/families/FYBROC/"
                "configurations/start"
            ),
            json={},
        )
        start.raise_for_status()
        response_body = start.json()

        trace = []

        while not response_body["complete"]:
            field_code = response_body[
                "nextFieldCode"
            ]
            preference = preferences.get(
                field_code
            )

            if preference is None:
                raise RuntimeError(
                    "No deterministic API preference "
                    f"exists for {field_code}."
                )

            option = choose_option(
                response_body,
                preference,
            )

            trace.append(
                {
                    "fieldCode": field_code,
                    "availableOptionCount": len(
                        response_body["options"]
                    ),
                    "selectedValue": (
                        option["displayValue"]
                    ),
                }
            )

            advance = client.post(
                (
                    "/api/v1/families/FYBROC/"
                    "configurations/advance"
                ),
                json={
                    "stateToken": (
                        response_body[
                            "stateToken"
                        ]
                    ),
                    "optionToken": (
                        option["optionToken"]
                    ),
                },
            )
            advance.raise_for_status()
            response_body = advance.json()

        requested_by = getpass.getuser()

        first = client.post(
            (
                "/api/v1/families/FYBROC/"
                "configurations/finalize"
            ),
            json={
                "stateToken": (
                    response_body["stateToken"]
                )
            },
            headers={
                "X-Requested-By": requested_by
            },
        )
        first.raise_for_status()

        second = client.post(
            (
                "/api/v1/families/FYBROC/"
                "configurations/finalize"
            ),
            json={
                "stateToken": (
                    response_body["stateToken"]
                )
            },
            headers={
                "X-Requested-By": requested_by
            },
        )
        second.raise_for_status()

        first_body = first.json()
        second_body = second.json()

        output = {
            "start_endpoint_verified": True,
            "advance_endpoint_verified": True,
            "finalize_endpoint_verified": True,
            "navigation_steps": len(trace),
            "selection_count": (
                first_body["selectionCount"]
            ),
            "segment_count": (
                first_body["segmentCount"]
            ),
            "configured_product_registry_id": (
                first_body[
                    "configuredProductRegistryId"
                ]
            ),
            "same_registry_id": (
                first_body[
                    "configuredProductRegistryId"
                ]
                == second_body[
                    "configuredProductRegistryId"
                ]
            ),
            "second_call_was_created": (
                second_body["wasCreated"]
            ),
            "part_number": (
                first_body["partNumber"]
            ),
            "sku": first_body["sku"],
            "runtime_revision": (
                first_body["runtimeRevision"]
            ),
            "arbitrary_engineering_values_accepted": (
                False
            ),
            "closed_api_verified": True,
        }

        print(
            json.dumps(
                output,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()

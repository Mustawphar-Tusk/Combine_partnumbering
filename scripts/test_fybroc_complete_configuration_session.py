from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from src.configuration_engine.fybroc_runtime import (
    build_fybroc_runtime,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def connection_string() -> str:
    server = os.getenv("DB_SERVER", "localhost")
    database = os.getenv(
        "DB_DATABASE",
        "PumpConfiguratorDB",
    )
    driver = os.getenv(
        "DB_DRIVER",
        "ODBC Driver 18 for SQL Server",
    )

    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        "Trusted_Connection=yes;"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
    )


def choose_option(
    response,
    preference: dict[str, str] | None,
):
    if preference is None:
        raise RuntimeError(
            f"No deterministic test preference exists for "
            f"{response.next_field_code}."
        )

    exact = preference.get("exact")
    contains = preference.get("contains")

    for option in response.options:
        if (
            exact is not None
            and option.display_value == exact
        ):
            return option

        if (
            contains is not None
            and contains in option.display_value
        ):
            return option

    raise RuntimeError(
        f"Preferred value was not returned for "
        f"{response.next_field_code}: {preference}. "
        f"Available values: "
        f"{[item.display_value for item in response.options]}"
    )


def main() -> None:
    preferences = json.loads(
        (
            PROJECT_ROOT
            / "config"
            / "runtime_profiles"
            / "fybroc_session_test_preferences.json"
        ).read_text(encoding="utf-8")
    )

    secret = os.getenv(
        "CONFIGURATION_TOKEN_SECRET",
        (
            "development-only-change-before-api-"
            "deployment-0123456789"
        ),
    )

    runtime = build_fybroc_runtime(
        project_root=PROJECT_ROOT,
        connection_string=connection_string(),
        token_secret=secret,
    )

    response = runtime.session.start(
        family_code="FYBROC"
    )
    navigation_trace: list[dict] = []

    while not response.complete:
        field_code = response.next_field_code

        if field_code is None:
            raise RuntimeError(
                "Incomplete response has no next field."
            )

        option = choose_option(
            response,
            preferences.get(field_code),
        )

        navigation_trace.append(
            {
                "field_code": field_code,
                "available_option_count": len(
                    response.options
                ),
                "selected_value": (
                    option.display_value
                ),
            }
        )

        response = runtime.session.advance(
            state_token=response.state_token,
            option_token=option.option_token,
        )

    completed = runtime.session.finalize(
        state_token=response.state_token
    )
    result = completed.identifier_result

    output = {
        "complete": True,
        "runtime_revision": (
            completed.runtime_revision
        ),
        "selection_count": len(
            completed.selections
        ),
        "navigation_steps": len(
            navigation_trace
        ),
        "part_number": result.part_number,
        "sku": result.sku,
        "configuration_signature": (
            result.configuration_signature
        ),
        "segments": [
            asdict(segment)
            for segment in result.segments
        ],
        "validation_messages": list(
            result.validation_messages
        ),
        "metadata_trace": (
            result.metadata_trace
        ),
        "navigation_trace": navigation_trace,
        "arbitrary_engineering_values_accepted": False,
        "identifier_input": (
            "completed signed state only"
        ),
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

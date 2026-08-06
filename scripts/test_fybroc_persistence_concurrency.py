from __future__ import annotations

import getpass
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from src.configuration_engine.fybroc_persistence_runtime import (
    build_fybroc_persistence_runtime,
)
from src.configuration_engine.persistence import (
    build_persistence_payload,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def connection_string() -> str:
    driver = os.getenv(
        "DB_DRIVER",
        "ODBC Driver 18 for SQL Server",
    )
    server = os.getenv("DB_SERVER", "localhost")
    database = os.getenv(
        "DB_DATABASE",
        "PumpConfiguratorDB",
    )

    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        "Trusted_Connection=yes;"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
    )


def choose_option(response, preference):
    exact = preference.get("exact")
    contains = preference.get("contains")

    for option in response.options:
        if exact is not None and option.display_value == exact:
            return option
        if contains is not None and contains in option.display_value:
            return option

    raise RuntimeError(
        f"Preference not returned for {response.next_field_code}."
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

    runtime = build_fybroc_persistence_runtime(
        project_root=PROJECT_ROOT,
        connection_string=connection_string(),
        token_secret=secret,
    )

    session = runtime.configuration_runtime.session
    response = session.start(family_code="FYBROC")

    while not response.complete:
        field_code = response.next_field_code
        option = choose_option(
            response,
            preferences[field_code],
        )
        response = session.advance(
            state_token=response.state_token,
            option_token=option.option_token,
        )

    completed = session.finalize(
        state_token=response.state_token
    )
    payload = build_persistence_payload(
        completed=completed,
        field_order=session.navigator.field_order,
        requested_by=getpass.getuser(),
    )

    def persist_once(_):
        repository = type(
            runtime.persistence_repository
        )(
            connection_string=connection_string()
        )
        return repository.persist(payload)

    worker_count = 8

    with ThreadPoolExecutor(
        max_workers=worker_count
    ) as executor:
        results = list(
            executor.map(
                persist_once,
                range(worker_count),
            )
        )

    registry_ids = {
        result.configured_product_registry_id
        for result in results
    }

    if len(registry_ids) != 1:
        raise RuntimeError(
            "Concurrent requests returned multiple registry IDs."
        )

    counts = (
        runtime.persistence_repository
        .counts_for_signature(
            family_code="FYBROC",
            configuration_signature=(
                payload.configuration_signature
            ),
        )
    )

    print(
        json.dumps(
            {
                "worker_count": worker_count,
                "unique_registry_ids": len(registry_ids),
                "registry_id": next(iter(registry_ids)),
                "created_result_count": sum(
                    result.was_created
                    for result in results
                ),
                "registry_count": counts.registry_count,
                "selection_count": counts.selection_count,
                "segment_count": counts.segment_count,
                "concurrency_reuse_verified": (
                    len(registry_ids) == 1
                    and counts.registry_count == 1
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

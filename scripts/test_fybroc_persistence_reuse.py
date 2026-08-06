from __future__ import annotations

import getpass
import json
import os
from pathlib import Path

from src.configuration_engine.fybroc_persistence_runtime import (
    build_fybroc_persistence_runtime,
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
    if preference is None:
        raise RuntimeError(
            "No deterministic preference exists for "
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
        "The deterministic preference was not returned for "
        f"{response.next_field_code}: {preference}."
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

        if field_code is None:
            raise RuntimeError(
                "Incomplete navigation response has no field."
            )

        option = choose_option(
            response,
            preferences.get(field_code),
        )

        response = session.advance(
            state_token=response.state_token,
            option_token=option.option_token,
        )

    requested_by = getpass.getuser()

    first = (
        runtime.persistent_session
        .finalize_and_persist(
            state_token=response.state_token,
            requested_by=requested_by,
        )
    )

    second = (
        runtime.persistent_session
        .finalize_and_persist(
            state_token=response.state_token,
            requested_by=requested_by,
        )
    )

    first_product = first.persisted_product
    second_product = second.persisted_product

    if (
        first_product.configured_product_registry_id
        != second_product.configured_product_registry_id
    ):
        raise RuntimeError(
            "Repeated persistence returned different registry IDs."
        )

    if second_product.was_created:
        raise RuntimeError(
            "The second persistence call created a duplicate record."
        )

    counts = (
        runtime.persistence_repository
        .counts_for_signature(
            family_code="FYBROC",
            configuration_signature=(
                first_product.configuration_signature
            ),
        )
    )

    if counts.registry_count != 1:
        raise RuntimeError(
            "The signature does not resolve to exactly one registry row."
        )

    if counts.selection_count != 41:
        raise RuntimeError(
            "The persisted selection count is not 41."
        )

    if counts.segment_count != 10:
        raise RuntimeError(
            "The persisted segment count is not 10."
        )

    output = {
        "configured_product_registry_id": (
            first_product.configured_product_registry_id
        ),
        "configuration_signature": (
            first_product.configuration_signature
        ),
        "part_number": first_product.part_number,
        "sku": first_product.sku,
        "first_call_was_created": (
            first_product.was_created
        ),
        "second_call_was_created": (
            second_product.was_created
        ),
        "same_registry_id": True,
        "request_count_after_second_call": (
            second_product.request_count
        ),
        "registry_count": counts.registry_count,
        "selection_count": counts.selection_count,
        "segment_count": counts.segment_count,
        "audit_count": counts.audit_count,
        "runtime_revision": (
            first_product.runtime_revision
        ),
        "reuse_verified": True,
    }

    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()

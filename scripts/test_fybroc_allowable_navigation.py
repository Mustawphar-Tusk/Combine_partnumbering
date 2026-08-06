from __future__ import annotations

import json
import os
from pathlib import Path

from src.configuration_engine.active_publication import (
    get_active_publication_id,
)
from src.configuration_engine.allowable_navigation import (
    AllowableConfigurationNavigator,
)
from src.configuration_engine.available_options import (
    AvailableOptionsService,
)
from src.configuration_engine.navigation_tokens import (
    NavigationTokenCodec,
)
from src.configuration_engine.projection import (
    SqlAttributeProjectionRepository,
    SqlConstraintProjectionRepository,
)
from src.configuration_engine.runtime_revision import (
    get_runtime_revision,
)
from src.configuration_engine.series_projection import (
    SqlSeriesConstraintRepository,
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


def find_option(
    response,
    *,
    exact: str | None = None,
    contains: str | None = None,
):
    for option in response.options:
        if exact is not None and (
            option.display_value == exact
        ):
            return option

        if contains is not None and (
            contains in option.display_value
        ):
            return option

    raise RuntimeError(
        f"Requested option was not returned for "
        f"{response.next_field_code}."
    )


def main() -> None:
    connection = connection_string()
    publication_id = get_active_publication_id(
        connection
    )

    available_profile = json.loads(
        (
            PROJECT_ROOT
            / "config"
            / "runtime_profiles"
            / "fybroc_available_options.json"
        ).read_text(encoding="utf-8")
    )

    engine_profile = json.loads(
        (
            PROJECT_ROOT
            / "config"
            / "runtime_profiles"
            / "fybroc_configuration_engine.json"
        ).read_text(encoding="utf-8")
    )

    navigation_profile = json.loads(
        (
            PROJECT_ROOT
            / "config"
            / "runtime_profiles"
            / "fybroc_allowable_navigation.json"
        ).read_text(encoding="utf-8")
    )

    segment_field_order = {
        code: tuple(order)
        for code, order in engine_profile[
            "combination_segment_field_order"
        ].items()
    }

    options_service = AvailableOptionsService(
        attribute_repository=(
            SqlAttributeProjectionRepository(
                connection_string=connection,
                metadata_publication_id=publication_id,
            )
        ),
        series_repository=(
            SqlSeriesConstraintRepository(
                connection_string=connection,
                metadata_publication_id=publication_id,
            )
        ),
        combination_repository=(
            SqlConstraintProjectionRepository(
                connection_string=connection,
                segment_field_order=segment_field_order,
            )
        ),
        attribute_fields=set(
            available_profile["attribute_fields"]
        ),
        segment_field_map=available_profile[
            "segment_field_map"
        ],
    )

    revision = get_runtime_revision(
        connection,
        family_code="FYBROC",
        metadata_publication_id=publication_id,
    )

    secret = os.getenv(
        "CONFIGURATION_TOKEN_SECRET",
        (
            "development-only-change-before-api-"
            "deployment-0123456789"
        ),
    )

    navigator = AllowableConfigurationNavigator(
        available_options_service=options_service,
        token_codec=NavigationTokenCodec.from_text(
            secret
        ),
        runtime_revision=revision,
        field_order=tuple(
            navigation_profile["field_order"]
        ),
        segment_field_map=available_profile[
            "segment_field_map"
        ],
        combination_segment_field_order=(
            segment_field_order
        ),
        series_code_pattern=navigation_profile[
            "series_code_pattern"
        ],
    )

    series_step = navigator.start(
        family_code="FYBROC"
    )

    series_option = find_option(
        series_step,
        contains="1530",
    )

    size_step = navigator.advance(
        state_token=series_step.state_token,
        option_token=series_option.option_token,
    )

    size_values = [
        option.display_value
        for option in size_step.options
    ]

    size_option = find_option(
        size_step,
        exact="1x1.5x6",
    )

    material_step = navigator.advance(
        state_token=size_step.state_token,
        option_token=size_option.option_token,
    )

    output = {
        "runtime_revision": revision,
        "start": {
            "next_field": (
                series_step.next_field_code
            ),
            "option_count": len(
                series_step.options
            ),
        },
        "after_series": {
            "next_field": size_step.next_field_code,
            "option_count": len(size_step.options),
            "contains_valid_size": (
                "1x1.5x6" in size_values
            ),
            "contains_unavailable_size": (
                "6x10x8" in size_values
            ),
        },
        "after_size": {
            "next_field": (
                material_step.next_field_code
            ),
            "option_count": len(
                material_step.options
            ),
            "values": [
                option.display_value
                for option in material_step.options
            ],
        },
        "client_submits": (
            "state_token + option_token only"
        ),
        "arbitrary_engineering_values_accepted": False,
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

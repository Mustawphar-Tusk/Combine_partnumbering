from __future__ import annotations

import json
import os
from pathlib import Path

from src.configuration_engine.active_publication import (
    get_active_publication_id,
)
from src.configuration_engine.available_options import (
    AvailableOptionsRequest,
    AvailableOptionsService,
)
from src.configuration_engine.projection import (
    SqlAttributeProjectionRepository,
    SqlConstraintProjectionRepository,
)
from src.configuration_engine.series_projection import (
    SqlSeriesConstraintRepository,
)
from src.configuration_engine.value_equivalences import (
    ValueEquivalenceProfile,
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


def read_json(path: Path) -> dict:
    return json.loads(
        path.read_text(encoding="utf-8")
    )


def main() -> None:
    connection = connection_string()
    publication_id = get_active_publication_id(
        connection
    )

    available_profile = read_json(
        PROJECT_ROOT
        / "config"
        / "runtime_profiles"
        / "fybroc_available_options.json"
    )
    engine_profile = read_json(
        PROJECT_ROOT
        / "config"
        / "runtime_profiles"
        / "fybroc_configuration_engine.json"
    )
    equivalence_profile = (
        ValueEquivalenceProfile.from_mapping(
            read_json(
                PROJECT_ROOT
                / "config"
                / "runtime_profiles"
                / "fybroc_value_equivalences.json"
            )
        )
    )

    service = AvailableOptionsService(
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
                segment_field_order={
                    code: tuple(order)
                    for code, order
                    in engine_profile[
                        "combination_segment_field_order"
                    ].items()
                },
            )
        ),
        attribute_fields=set(
            available_profile["attribute_fields"]
        ),
        segment_field_map=available_profile[
            "segment_field_map"
        ],
        value_equivalences=equivalence_profile,
    )

    rows = []
    zero_fields = []

    for field_code, segment_code in available_profile[
        "segment_field_map"
    ].items():
        series_rows = (
            service.series_repository.available_values(
                family_code="FYBROC",
                series_code="1530",
                field_code=field_code,
            )
        )

        if not series_rows:
            continue

        result = service.available_options(
            AvailableOptionsRequest(
                family_code="FYBROC",
                target_field_code=field_code,
                series_code="1530",
                segment_code=segment_code,
                current_segment_selections={},
            )
        )

        row = {
            "field_code": field_code,
            "series_count": result.source_counts.get(
                "SERIES",
                0,
            ),
            "combination_count": (
                result.source_counts.get(
                    "COMBINATION",
                    0,
                )
            ),
            "available_count": len(result.values),
            "available_values": list(result.values),
        }
        rows.append(row)

        if not result.values:
            zero_fields.append(field_code)

    print(
        json.dumps(
            {
                "active_publication_id": publication_id,
                "field_count": len(rows),
                "zero_intersection_fields": zero_fields,
                "fields": rows,
            },
            indent=2,
        )
    )

    if zero_fields:
        raise SystemExit(
            "One or more fields still have no reconciled "
            "allowable values."
        )


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import os

from src.configuration_engine.active_publication import (
    get_active_publication_id,
)
from src.configuration_engine.series_projection import (
    SqlSeriesConstraintRepository,
)


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


def main() -> None:
    connection = connection_string()
    publication_id = get_active_publication_id(
        connection
    )

    repository = SqlSeriesConstraintRepository(
        connection_string=connection,
        metadata_publication_id=publication_id,
    )

    sizes_1530 = repository.available_values(
        family_code="FYBROC",
        series_code="1530",
        field_code="SIZE",
    )

    materials_1530 = repository.available_values(
        family_code="FYBROC",
        series_code="1530",
        field_code="PUMP_MATERIAL",
    )

    output = {
        "active_publication_id": publication_id,
        "series": "1530",
        "size_count": len(sizes_1530),
        "sizes": [
            row.option_value
            for row in sizes_1530
        ],
        "material_count": len(materials_1530),
        "materials": [
            row.option_value
            for row in materials_1530
        ],
        "valid_size_1x1_5x6": (
            repository.is_allowed(
                family_code="FYBROC",
                series_code="1530",
                field_code="SIZE",
                option_value="1x1.5x6",
            )
        ),
        "invalid_size_6x10x8": (
            repository.is_allowed(
                family_code="FYBROC",
                series_code="1530",
                field_code="SIZE",
                option_value="6x10x8",
            )
        ),
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

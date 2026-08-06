from __future__ import annotations

import json
import os
from pathlib import Path

from src.configuration_engine.active_publication import (
    get_active_publication_id,
)
from src.configuration_engine.dependency_projection import (
    SqlFieldDependencyRepository,
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


def main() -> None:
    connection = connection_string()
    publication_id = get_active_publication_id(
        connection
    )

    coverage = json.loads(
        (
            PROJECT_ROOT
            / "config"
            / "runtime_profiles"
            / "fybroc_dependency_coverage.json"
        ).read_text(encoding="utf-8")
    )

    repository = SqlFieldDependencyRepository(
        connection_string=connection,
        metadata_publication_id=publication_id,
        dependency_field_aliases=coverage[
            "dependency_field_aliases"
        ],
    )

    trims = repository.available_values(
        family_code="FYBROC",
        target_field_code="IMPELLER_TRIM",
        series_code="1530",
        current_selections={
            "SERIES": "1530 (ANSI)",
            "SIZE": "1x1.5x6",
        },
    )

    no_motor_context = {
        "MOTOR_OPTION": "No Motor",
        "MOTOR_CLASS": "-",
        "MOTOR_ORIENTATION": "Hor T",
        "MOTOR_HORSEPOWER": "-",
        "MOTOR_RPM": "-",
        "MOTOR_VOLTAGE": "-",
        "MOTOR_HERTZ": "-",
        "MOTOR_FRAME": "143",
        "MOTOR_ENCLOSURE": "-",
        "MOTOR_EFFICIENCY": "-",
        "MOTOR_MANUFACTURER": "-",
    }

    modifications = repository.available_values(
        family_code="FYBROC",
        target_field_code="MOTOR_MODIFICATION_1",
        series_code="1530",
        current_selections=no_motor_context,
    )

    print(
        json.dumps(
            {
                "active_publication_id": publication_id,
                "trim_count": len(trims),
                "trims": [
                    item.display_value
                    for item in trims
                ],
                "no_motor_modification_count": (
                    len(modifications)
                ),
                "no_motor_modifications": [
                    item.display_value
                    for item in modifications
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import os
from pathlib import Path

from src.configuration_engine.active_publication import (
    get_active_publication_id,
)
from src.configuration_engine.projection import (
    SqlAttributeProjectionRepository,
    SqlConstraintProjectionRepository,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def connection_string() -> str:
    server = os.getenv("DB_SERVER", "localhost")
    database = os.getenv("DB_DATABASE", "PumpConfiguratorDB")
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

    profile = json.loads(
        (
            PROJECT_ROOT
            / "config"
            / "runtime_profiles"
            / "fybroc_configuration_engine.json"
        ).read_text(encoding="utf-8")
    )

    projection = SqlConstraintProjectionRepository(
        connection_string=connection,
        segment_field_order={
            code: tuple(order)
            for code, order in profile[
                "combination_segment_field_order"
            ].items()
        },
    )

    active_publication_id = get_active_publication_id(
        connection
    )

    attributes = SqlAttributeProjectionRepository(
        connection_string=connection,
        metadata_publication_id=active_publication_id,
    )

    series = attributes.available_attribute_values(
        family_code="FYBROC",
        field_code="SERIES",
    )

    flush_values = projection.available_combination_values(
        family_code="FYBROC",
        segment_code="PUMP_OPTIONS",
        target_field_code="FLUSH",
        current_selections={
            "CASING_DRAINS": "No Casing Drains*",
            "SUCTION_DISCHARGE": "No Suction Discharge Tap*",
            "SHAFT_MATERIAL": "303 SS Shaft*",
            "IMPELLER_SLEEVE": "Integral Impeller Sleeve*",
            "CASING_HARDWARE": "303 SS Casing HW*",
            "PUMP_ELASTOMERS": "FKM*",
            "BEARING_OPTION": "Oil Bath Lubrication*",
            "POWER_FRAME_HARDWARE": "303 SS Frame HW*",
            "GLAND_HARDWARE": "303 SS Gland HW*",
            "CYCLONE_SEPARATOR": "No Cyclone Separator*",
            "DYNAMIC_IMPELLER": "No Dynamic Impeller*",
        },
    )

    valid_partial = projection.validate_partial_combination(
        family_code="FYBROC",
        segment_code="MOTOR_ASSEMBLY",
        current_selections={
            "MOTOR_OPTION": "No Motor",
            "MOTOR_CLASS": "-",
        },
    )

    invalid_partial = projection.validate_partial_combination(
        family_code="FYBROC",
        segment_code="MOTOR_ASSEMBLY",
        current_selections={
            "MOTOR_OPTION": "No Motor",
            "MOTOR_CLASS": "Imperial",
            "MOTOR_MANUFACTURER": "Fybroc Choice*",
        },
    )

    output = {
        "active_publication_id": active_publication_id,
        "series_count": len(series),
        "series_sample": [
            item.display_value
            for item in series[:5]
        ],
        "available_flush_values": [
            item.display_value
            for item in flush_values
        ],
        "valid_motor_partial": valid_partial,
        "invalid_motor_partial": invalid_partial,
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

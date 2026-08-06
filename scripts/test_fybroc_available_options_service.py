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


def main() -> None:
    connection = connection_string()
    publication_id = get_active_publication_id(
        connection
    )

    options_profile = json.loads(
        (
            PROJECT_ROOT
            / "config"
            / "runtime_profiles"
            / "fybroc_available_options.json"
        ).read_text(encoding="utf-8")
    )

    combination_profile = json.loads(
        (
            PROJECT_ROOT
            / "config"
            / "runtime_profiles"
            / "fybroc_configuration_engine.json"
        ).read_text(encoding="utf-8")
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
                    for code, order in combination_profile[
                        "combination_segment_field_order"
                    ].items()
                },
            )
        ),
        attribute_fields=set(
            options_profile["attribute_fields"]
        ),
        segment_field_map=options_profile[
            "segment_field_map"
        ],
    )

    sizes = service.available_options(
        AvailableOptionsRequest(
            family_code="FYBROC",
            target_field_code="SIZE",
            series_code="1530",
        )
    )

    flush = service.available_options(
        AvailableOptionsRequest(
            family_code="FYBROC",
            target_field_code="FLUSH",
            series_code="1530",
            current_segment_selections={
                "CASING_DRAINS": "No Casing Drains*",
                "SUCTION_DISCHARGE": (
                    "No Suction Discharge Tap*"
                ),
                "SHAFT_MATERIAL": "303 SS Shaft*",
                "IMPELLER_SLEEVE": (
                    "Integral Impeller Sleeve*"
                ),
                "CASING_HARDWARE": (
                    "303 SS Casing HW*"
                ),
                "PUMP_ELASTOMERS": "FKM*",
                "BEARING_OPTION": (
                    "Oil Bath Lubrication*"
                ),
                "POWER_FRAME_HARDWARE": (
                    "303 SS Frame HW*"
                ),
                "GLAND_HARDWARE": (
                    "303 SS Gland HW*"
                ),
                "CYCLONE_SEPARATOR": (
                    "No Cyclone Separator*"
                ),
                "DYNAMIC_IMPELLER": (
                    "No Dynamic Impeller*"
                ),
            },
        )
    )

    motor_frame = service.available_options(
        AvailableOptionsRequest(
            family_code="FYBROC",
            target_field_code="MOTOR_FRAME",
            series_code="1530",
            current_segment_selections={
                "MOTOR_OPTION": "No Motor",
                "MOTOR_CLASS": "-",
                "MOTOR_ORIENTATION": "Hor T",
                "MOTOR_HORSEPOWER": "-",
                "MOTOR_RPM": "-",
                "MOTOR_VOLTAGE": "-",
                "MOTOR_HERTZ": "-",
                "MOTOR_ENCLOSURE": "-",
                "MOTOR_EFFICIENCY": "-",
                "MOTOR_MANUFACTURER": "-",
            },
        )
    )

    output = {
        "active_publication_id": publication_id,
        "sizes": {
            "count": len(sizes.values),
            "values": list(sizes.values),
            "filters": list(sizes.applied_filters),
            "source_counts": sizes.source_counts,
        },
        "flush": {
            "count": len(flush.values),
            "values": list(flush.values),
            "filters": list(flush.applied_filters),
            "source_counts": flush.source_counts,
        },
        "motor_frame": {
            "count": len(motor_frame.values),
            "values": list(motor_frame.values),
            "filters": list(
                motor_frame.applied_filters
            ),
            "source_counts": (
                motor_frame.source_counts
            ),
        },
        "validation": {
            "valid_size": (
                service.validate_selected_value(
                    AvailableOptionsRequest(
                        family_code="FYBROC",
                        target_field_code="SIZE",
                        series_code="1530",
                    ),
                    "1x1.5x6",
                )
            ),
            "invalid_size": (
                service.validate_selected_value(
                    AvailableOptionsRequest(
                        family_code="FYBROC",
                        target_field_code="SIZE",
                        series_code="1530",
                    ),
                    "6x10x8",
                )
            ),
        },
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

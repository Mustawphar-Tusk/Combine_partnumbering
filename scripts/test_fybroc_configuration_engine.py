from __future__ import annotations

import json
import os
from pathlib import Path

from src.configuration_engine.models import ConfigurationRequest
from src.configuration_engine.service import ConfigurationEngine
from src.repositories.sql_configuration_repository import (
    SqlConfigurationRepository,
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
    profile = json.loads(
        (
            PROJECT_ROOT
            / "config"
            / "runtime_profiles"
            / "fybroc_configuration_engine.json"
        ).read_text(encoding="utf-8")
    )

    repository = SqlConfigurationRepository(
        connection_string=connection_string(),
        segment_field_order={
            segment_code: tuple(field_order)
            for segment_code, field_order
            in profile[
                "combination_segment_field_order"
            ].items()
        },
    )

    engine = ConfigurationEngine(
        repository=repository,
        segment_order=tuple(profile["segment_order"]),
        required_combination_segments=tuple(
            profile["required_combination_segments"]
        ),
    )

    request = ConfigurationRequest(
        family_code="FYBROC",
        series_code="1530",
        size_code="1x1.5x6",
        base_identifier="F1530",
        direct_segment_values={
            "SERIES": "B",
            "SIZE": "1",
            "PUMP_MATERIAL": "1",
            "IMPELLER_TRIM": "MA",
            "MOTOR_ASSEMBLY": "00",
            "MOTOR_MODIFICATIONS": "X",
            "TESTING": "T00",
        },
        combination_selections={
            "PUMP_OPTIONS": {
                "CASING_DRAINS": "No Casing Drains*",
                "SUCTION_DISCHARGE": "No Suction Discharge Tap*",
                "SHAFT_MATERIAL": "303 SS Shaft*",
                "IMPELLER_SLEEVE": "Integral Impeller Sleeve*",
                "CASING_HARDWARE": "303 SS Casing HW*",
                "PUMP_ELASTOMERS": "FKM*",
                "BEARING_OPTION": "Oil Bath Lubrication*",
                "POWER_FRAME_HARDWARE": "303 SS Frame HW*",
                "GLAND_HARDWARE": "303 SS Gland HW*",
                "FLUSH": "External Flush*",
                "CYCLONE_SEPARATOR": "No Cyclone Separator*",
                "DYNAMIC_IMPELLER": "No Dynamic Impeller*"
            },
            "SEAL_ASSEMBLY": {
                "SEAL_OPTION": "Mechanical Seal Included*",
                "SEAL_TYPE": "8B2 Single Outside*",
                "SEAL_MATERIALS": "Carbon vs. Ceramic*",
                "SEAL_ELASTOMERS": "FKM*",
                "SEAL_GUARD": "No Seal Guard"
            },
            "OPTIONS": {
                "COUPLING_OPTION": "No Coupling",
                "COUPLING_GUARD": "No Coupling Guard",
                "BASEPLATE_OPTION": "No Baseplate",
                "BASEPLATE_HARDWARE": "-",
                "NAMEPLATE": "No Customer Nameplate"
            }
        }
    )

    result = engine.configure(request)

    print(json.dumps(
        {
            "valid": result.valid,
            "part_number": result.part_number,
            "sku": result.sku,
            "segments": [
                {
                    "segment_code": segment.segment_code,
                    "segment_value": segment.segment_value,
                    "source_id": segment.source_id,
                    "resolution_type": segment.resolution_type,
                }
                for segment in result.segments
            ],
            "validation_messages": list(
                result.validation_messages
            ),
        },
        indent=2,
    ))


if __name__ == "__main__":
    main()

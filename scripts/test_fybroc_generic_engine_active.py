from __future__ import annotations

import json
import os
from pathlib import Path

from src.configuration_engine.active_publication import get_active_publication_id
from src.configuration_engine.combination_resolver_adapter import CombinationResolverAdapter
from src.configuration_engine.generic_engine import (
    GenericConfigurationEngine,
    GenericConfigurationRequest,
    SegmentRuntimeDefinition,
)
from src.configuration_engine.resolvers import ResolverRegistry, SqlAttributeResolver
from src.repositories.sql_configuration_repository import SqlConfigurationRepository


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def connection_string() -> str:
    server = os.getenv("DB_SERVER", "localhost")
    database = os.getenv("DB_DATABASE", "PumpConfiguratorDB")
    driver = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")
    return (
        f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
        "Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;"
    )


def main() -> None:
    connection = connection_string()

    runtime_profile = json.loads(
        (PROJECT_ROOT / "config" / "runtime_profiles" / "fybroc_generic_runtime.json")
        .read_text(encoding="utf-8")
    )
    combination_profile = json.loads(
        (PROJECT_ROOT / "config" / "runtime_profiles" / "fybroc_configuration_engine.json")
        .read_text(encoding="utf-8")
    )

    publication_id = get_active_publication_id(connection)

    registry = ResolverRegistry()
    registry.register(
        "ATTRIBUTE",
        SqlAttributeResolver(
            connection_string=connection,
            metadata_publication_id=publication_id,
        ),
    )

    repository = SqlConfigurationRepository(
        connection_string=connection,
        segment_field_order={
            code: tuple(order)
            for code, order in combination_profile[
                "combination_segment_field_order"
            ].items()
        },
    )
    registry.register(
        "COMBINATION",
        CombinationResolverAdapter(repository=repository),
    )

    engine = GenericConfigurationEngine(
        registry=registry,
        segment_definitions=tuple(
            SegmentRuntimeDefinition(
                segment_code=row["segment_code"],
                resolution_type=row["resolution_type"],
                required=row.get("required", True),
            )
            for row in runtime_profile["segments"]
        ),
    )

    result = engine.configure(
        GenericConfigurationRequest(
            family_code="FYBROC",
            base_identifier="F1530",
            identifier_version=1,
            selections={
                "SERIES": "1530 (ANSI)",
                "SIZE": "1x1.5x6",
                "PUMP_MATERIAL": "VR-1*",
                "IMPELLER_TRIM": "16.000",
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
                },
                "MOTOR_ASSEMBLY": {
                    "MOTOR_OPTION": "No Motor",
                    "MOTOR_CLASS": "-",
                    "MOTOR_ORIENTATION": "-",
                    "MOTOR_HORSEPOWER": "-",
                    "MOTOR_RPM": "-",
                    "MOTOR_VOLTAGE": "-",
                    "MOTOR_HERTZ": "-",
                    "MOTOR_FRAME": "-",
                    "MOTOR_ENCLOSURE": "-",
                    "MOTOR_EFFICIENCY": "-",
                    "MOTOR_MANUFACTURER": "-"
                },
                "MOTOR_MODIFICATIONS": "No Modification",
                "TESTING": "-"
            },
        )
    )

    print(json.dumps(
        {
            "active_publication_id": publication_id,
            "valid": result.valid,
            "part_number": result.part_number,
            "sku": result.sku,
            "segments": [
                {
                    "segment_code": item.segment_code,
                    "segment_value": item.segment_value,
                    "source_id": item.source_id,
                    "resolution_type": item.resolution_type,
                }
                for item in result.segments
            ],
            "validation_messages": list(result.validation_messages),
        },
        indent=2,
    ))

    if not result.valid:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

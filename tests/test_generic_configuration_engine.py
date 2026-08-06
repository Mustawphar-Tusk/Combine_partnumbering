from src.configuration_engine.generic_engine import (
    GenericConfigurationEngine,
    GenericConfigurationRequest,
    SegmentRuntimeDefinition,
)
from src.configuration_engine.models import (
    ResolvedConfigurationSegment,
)
from src.configuration_engine.resolvers import ResolverRegistry


class Resolver:
    def resolve(
        self,
        *,
        family_code,
        segment_code,
        payload,
    ):
        return ResolvedConfigurationSegment(
            segment_code=segment_code,
            segment_value=str(payload),
            source_id=1,
            resolution_type="TEST",
        )


def test_generic_engine_uses_registry() -> None:
    registry = ResolverRegistry()
    registry.register("ATTRIBUTE", Resolver())
    registry.register("COMBINATION", Resolver())

    engine = GenericConfigurationEngine(
        registry=registry,
        segment_definitions=(
            SegmentRuntimeDefinition("SERIES", "ATTRIBUTE"),
            SegmentRuntimeDefinition("OPTIONS", "COMBINATION"),
        ),
    )

    result = engine.configure(
        GenericConfigurationRequest(
            family_code="FYBROC",
            base_identifier="F1530",
            identifier_version=1,
            selections={
                "SERIES": "B",
                "OPTIONS": "01",
            },
        )
    )

    assert result.valid is True
    assert result.part_number == "F1530-B-01"
    assert result.sku == "F1530-V1-B01"

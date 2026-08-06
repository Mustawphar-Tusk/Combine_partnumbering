from __future__ import annotations

import json
import re
from dataclasses import dataclass
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
from src.configuration_engine.complete_session import (
    CompleteAllowableConfigurationSession,
)
from src.configuration_engine.constraint_coverage import (
    ConstraintCoveragePolicy,
)
from src.configuration_engine.dependency_projection import (
    SqlFieldDependencyRepository,
)
from src.configuration_engine.identifier_generation import (
    IdentifierGenerationProfile,
    SqlMetadataIdentifierGenerator,
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
from src.configuration_engine.value_equivalences import (
    ValueEquivalenceProfile,
)


@dataclass(frozen=True)
class FybrocRuntime:
    metadata_publication_id: int
    combination_batch_id: int
    runtime_revision: str
    navigator: AllowableConfigurationNavigator
    session: CompleteAllowableConfigurationSession


def _read_json(path: Path) -> dict:
    return json.loads(
        path.read_text(encoding="utf-8")
    )


def build_fybroc_runtime(
    *,
    project_root: Path,
    connection_string: str,
    token_secret: str,
) -> FybrocRuntime:
    runtime_dir = (
        project_root
        / "config"
        / "runtime_profiles"
    )
    available_profile = _read_json(
        runtime_dir
        / "fybroc_available_options.json"
    )
    engine_profile = _read_json(
        runtime_dir
        / "fybroc_configuration_engine.json"
    )
    navigation_profile = _read_json(
        runtime_dir
        / "fybroc_allowable_navigation.json"
    )
    identifier_profile = _read_json(
        runtime_dir
        / "fybroc_identifier_generation.json"
    )
    equivalence_profile = _read_json(
        runtime_dir
        / "fybroc_value_equivalences.json"
    )
    coverage_mapping = _read_json(
        runtime_dir
        / "fybroc_dependency_coverage.json"
    )

    publication_id = get_active_publication_id(
        connection_string
    )
    revision = get_runtime_revision(
        connection_string,
        family_code="FYBROC",
        metadata_publication_id=publication_id,
    )

    combination_match = re.search(
        r"combination-batch:(\d+)",
        revision,
    )
    if combination_match is None:
        raise RuntimeError(
            "Combination batch is missing from "
            "runtime revision."
        )
    combination_batch_id = int(
        combination_match.group(1)
    )

    segment_field_order = {
        code: tuple(order)
        for code, order
        in engine_profile[
            "combination_segment_field_order"
        ].items()
    }

    dependency_repository = (
        SqlFieldDependencyRepository(
            connection_string=connection_string,
            metadata_publication_id=publication_id,
            dependency_field_aliases=(
                coverage_mapping[
                    "dependency_field_aliases"
                ]
            ),
        )
    )

    options_service = AvailableOptionsService(
        attribute_repository=(
            SqlAttributeProjectionRepository(
                connection_string=connection_string,
                metadata_publication_id=publication_id,
            )
        ),
        series_repository=(
            SqlSeriesConstraintRepository(
                connection_string=connection_string,
                metadata_publication_id=publication_id,
            )
        ),
        combination_repository=(
            SqlConstraintProjectionRepository(
                connection_string=connection_string,
                segment_field_order=segment_field_order,
                import_batch_id=combination_batch_id,
            )
        ),
        attribute_fields=set(
            available_profile["attribute_fields"]
        ),
        segment_field_map=available_profile[
            "segment_field_map"
        ],
        value_equivalences=(
            ValueEquivalenceProfile.from_mapping(
                equivalence_profile
            )
        ),
        dependency_repository=dependency_repository,
        attribute_field_aliases=(
            coverage_mapping[
                "attribute_field_aliases"
            ]
        ),
    )

    field_order = tuple(
        navigation_profile["field_order"]
    )
    coverage = ConstraintCoveragePolicy.from_mapping(
        coverage_mapping
    )
    coverage.assert_field_order(field_order)

    navigator = AllowableConfigurationNavigator(
        available_options_service=options_service,
        token_codec=NavigationTokenCodec.from_text(
            token_secret
        ),
        runtime_revision=revision,
        field_order=field_order,
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

    generator = SqlMetadataIdentifierGenerator(
        connection_string=connection_string,
        profile=IdentifierGenerationProfile.from_mapping(
            identifier_profile
        ),
        metadata_publication_id=publication_id,
        combination_batch_id=combination_batch_id,
    )

    session = CompleteAllowableConfigurationSession(
        navigator=navigator,
        identifier_generator=generator,
        constraint_coverage=coverage,
    )

    return FybrocRuntime(
        metadata_publication_id=publication_id,
        combination_batch_id=combination_batch_id,
        runtime_revision=revision,
        navigator=navigator,
        session=session,
    )

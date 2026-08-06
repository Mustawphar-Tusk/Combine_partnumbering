from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.configuration_engine.fybroc_runtime import (
    FybrocRuntime,
    build_fybroc_runtime,
)
from src.configuration_engine.persistence import (
    SqlConfiguredProductPersistenceRepository,
)
from src.configuration_engine.persistent_session import (
    PersistentAllowableConfigurationSession,
)


@dataclass(frozen=True)
class FybrocPersistenceRuntime:
    configuration_runtime: FybrocRuntime
    persistence_repository: (
        SqlConfiguredProductPersistenceRepository
    )
    persistent_session: (
        PersistentAllowableConfigurationSession
    )


def build_fybroc_persistence_runtime(
    *,
    project_root: Path,
    connection_string: str,
    token_secret: str,
) -> FybrocPersistenceRuntime:
    configuration_runtime = build_fybroc_runtime(
        project_root=project_root,
        connection_string=connection_string,
        token_secret=token_secret,
    )

    repository = (
        SqlConfiguredProductPersistenceRepository(
            connection_string=connection_string
        )
    )

    persistent_session = (
        PersistentAllowableConfigurationSession(
            complete_session=(
                configuration_runtime.session
            ),
            persistence_repository=repository,
        )
    )

    return FybrocPersistenceRuntime(
        configuration_runtime=configuration_runtime,
        persistence_repository=repository,
        persistent_session=persistent_session,
    )

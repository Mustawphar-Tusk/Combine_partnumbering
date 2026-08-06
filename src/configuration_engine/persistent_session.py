from __future__ import annotations

from dataclasses import dataclass

from src.configuration_engine.complete_session import (
    CompletedConfiguration,
    CompleteAllowableConfigurationSession,
)
from src.configuration_engine.persistence import (
    PersistedConfiguredProduct,
    SqlConfiguredProductPersistenceRepository,
    build_persistence_payload,
)


@dataclass(frozen=True)
class PersistedConfigurationResult:
    completed_configuration: CompletedConfiguration
    persisted_product: PersistedConfiguredProduct


class PersistentAllowableConfigurationSession:
    """
    Persists only a completed signed allowable-configuration state.

    No field/value payload is accepted by this boundary.
    """

    def __init__(
        self,
        *,
        complete_session: CompleteAllowableConfigurationSession,
        persistence_repository: (
            SqlConfiguredProductPersistenceRepository
        ),
    ) -> None:
        self.complete_session = complete_session
        self.persistence_repository = (
            persistence_repository
        )

    def finalize_and_persist(
        self,
        *,
        state_token: str,
        requested_by: str | None = None,
    ) -> PersistedConfigurationResult:
        completed = self.complete_session.finalize(
            state_token=state_token
        )

        payload = build_persistence_payload(
            completed=completed,
            field_order=(
                self.complete_session.navigator.field_order
            ),
            requested_by=requested_by,
        )

        persisted = self.persistence_repository.persist(
            payload
        )

        return PersistedConfigurationResult(
            completed_configuration=completed,
            persisted_product=persisted,
        )

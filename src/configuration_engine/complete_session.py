from __future__ import annotations

from dataclasses import dataclass

from src.configuration_engine.allowable_navigation import (
    AllowableConfigurationNavigator,
    AllowableNavigationResponse,
)
from src.configuration_engine.constraint_coverage import (
    ConstraintCoveragePolicy,
)
from src.configuration_engine.identifier_generation import (
    IdentifierGenerationResult,
    SqlMetadataIdentifierGenerator,
)


@dataclass(frozen=True)
class CompletedConfiguration:
    family_code: str
    runtime_revision: str
    state_token: str
    selections: dict[str, str]
    identifier_result: IdentifierGenerationResult


class CompleteAllowableConfigurationSession:
    def __init__(
        self,
        *,
        navigator: AllowableConfigurationNavigator,
        identifier_generator: SqlMetadataIdentifierGenerator,
        constraint_coverage: (
            ConstraintCoveragePolicy | None
        ) = None,
    ) -> None:
        self.navigator = navigator
        self.identifier_generator = identifier_generator
        self.constraint_coverage = constraint_coverage

    def start(
        self,
        *,
        family_code: str,
    ) -> AllowableNavigationResponse:
        return self.navigator.start(
            family_code=family_code
        )

    def advance(
        self,
        *,
        state_token: str,
        option_token: str,
    ) -> AllowableNavigationResponse:
        return self.navigator.advance(
            state_token=state_token,
            option_token=option_token,
        )

    def resume(
        self,
        *,
        state_token: str,
    ) -> AllowableNavigationResponse:
        return self.navigator.resume(
            state_token=state_token
        )

    def finalize(
        self,
        *,
        state_token: str,
    ) -> CompletedConfiguration:
        response = self.navigator.resume(
            state_token=state_token
        )

        if not response.complete:
            raise RuntimeError(
                "Identifier generation requires a complete "
                "allowable configuration state."
            )

        selections = (
            self.navigator.selections_from_state(
                state_token=state_token,
                require_complete=True,
            )
        )

        if self.constraint_coverage is not None:
            self.constraint_coverage.assert_complete_state(
                selections
            )

        result = self.identifier_generator.generate(
            selections
        )

        return CompletedConfiguration(
            family_code=response.family_code,
            runtime_revision=response.runtime_revision,
            state_token=response.state_token,
            selections=selections,
            identifier_result=result,
        )

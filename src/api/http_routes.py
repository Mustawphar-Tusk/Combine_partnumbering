from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Header,
    Path,
)

from src.api.dependencies import (
    get_runtime_registry,
)
from src.api.errors import (
    ConfigurationOperationConflict,
)
from src.api.models import (
    AdvanceConfigurationRequest,
    FinalizeConfigurationRequest,
    FinalizeConfigurationResponse,
    HealthResponse,
    NavigationResponse,
    StartConfigurationRequest,
)
from src.api.presenters import (
    present_navigation,
    present_persisted_configuration,
)
from src.api.runtime_registry import (
    ConfigurationRuntimeRegistry,
)


router = APIRouter()

FamilyCode = Annotated[
    str,
    Path(
        min_length=2,
        max_length=50,
        pattern=r"^[A-Za-z0-9_-]+$",
    ),
]


@router.get(
    "/health/live",
    response_model=HealthResponse,
    tags=["Health"],
)
def liveness(
    registry: ConfigurationRuntimeRegistry = Depends(
        get_runtime_registry
    ),
) -> HealthResponse:
    return HealthResponse(
        status="live",
        service="pump-configurator-api",
        version="0.19.0",
        environment="running",
        configured_families=list(
            registry.family_codes
        ),
    )


@router.get(
    "/health/ready",
    response_model=HealthResponse,
    tags=["Health"],
)
def readiness(
    registry: ConfigurationRuntimeRegistry = Depends(
        get_runtime_registry
    ),
) -> HealthResponse:
    return HealthResponse(
        status="ready",
        service="pump-configurator-api",
        version="0.19.0",
        environment="running",
        configured_families=list(
            registry.family_codes
        ),
    )


@router.post(
    (
        "/api/v1/families/{family_code}"
        "/configurations/start"
    ),
    response_model=NavigationResponse,
    tags=["Configurations"],
)
def start_configuration(
    family_code: FamilyCode,
    body: StartConfigurationRequest,
    registry: ConfigurationRuntimeRegistry = Depends(
        get_runtime_registry
    ),
) -> NavigationResponse:
    del body

    gateway = registry.get(family_code)
    response = gateway.navigation_session.start(
        family_code=gateway.family_code
    )

    return present_navigation(response)


@router.post(
    (
        "/api/v1/families/{family_code}"
        "/configurations/advance"
    ),
    response_model=NavigationResponse,
    tags=["Configurations"],
)
def advance_configuration(
    family_code: FamilyCode,
    body: AdvanceConfigurationRequest,
    registry: ConfigurationRuntimeRegistry = Depends(
        get_runtime_registry
    ),
) -> NavigationResponse:
    gateway = registry.get(family_code)

    response = gateway.navigation_session.advance(
        state_token=body.state_token,
        option_token=body.option_token,
    )

    return present_navigation(response)


@router.post(
    (
        "/api/v1/families/{family_code}"
        "/configurations/finalize"
    ),
    response_model=FinalizeConfigurationResponse,
    tags=["Configurations"],
)
def finalize_configuration(
    family_code: FamilyCode,
    body: FinalizeConfigurationRequest,
    requested_by: Annotated[
        str | None,
        Header(
            alias="X-Requested-By",
            max_length=200,
        ),
    ] = None,
    registry: ConfigurationRuntimeRegistry = Depends(
        get_runtime_registry
    ),
) -> FinalizeConfigurationResponse:
    gateway = registry.get(family_code)

    current_state = (
        gateway.navigation_session.resume(
            state_token=body.state_token
        )
    )

    if not current_state.complete:
        raise ConfigurationOperationConflict(
            "Finalization requires a completed "
            "signed configuration state."
        )

    result = (
        gateway.persistent_session
        .finalize_and_persist(
            state_token=body.state_token,
            requested_by=requested_by,
        )
    )

    pricing = None

    if gateway.pricing_service is not None:
        pricing = gateway.pricing_service.resolve(
            family_code=(
                result
                .completed_configuration
                .family_code
            ),
            configuration=(
                result
                .completed_configuration
                .selections
            ),
        )

    return present_persisted_configuration(
        result,
        pricing=pricing,
    )

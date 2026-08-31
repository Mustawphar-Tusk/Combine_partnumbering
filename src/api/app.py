from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import pyodbc
from fastapi import FastAPI, Request
from fastapi.exceptions import (
    RequestValidationError,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.api.errors import (
    ConfigurationOperationConflict,
)
from src.api.models import (
    ErrorBody,
    ErrorResponse,
)
from src.api.http_routes import router
from src.api.v2_routes import router_v2
from src.api.runtime_registry import (
    ConfigurationRuntimeRegistry,
    UnsupportedPumpFamilyError,
    build_runtime_registry,
)
from src.api.settings import (
    ApiConfigurationError,
    ApiSettings,
)
from src.configuration_engine.allowable_navigation import (
    AllowableNavigationError,
    NoAllowableOptionsError,
)
from src.configuration_engine.navigation_tokens import (
    NavigationTokenError,
)
from src.configuration_engine.persistence import (
    ConfiguredProductPersistenceError,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
) -> JSONResponse:
    payload = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
        )
    )

    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(
            by_alias=True,
            mode="json",
        ),
    )


def create_app(
    *,
    settings: ApiSettings | None = None,
    runtime_registry: (
        ConfigurationRuntimeRegistry | None
    ) = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(
        application: FastAPI,
    ):
        resolved_settings = (
            settings
            or ApiSettings.from_environment(
                project_root=PROJECT_ROOT
            )
        )
        # Build the runtime registry, but DO NOT let a failure here prevent the
        # app from starting and binding its port. build_runtime_registry opens
        # SQL connections at boot; when the database is unreachable (e.g. the
        # ngrok tunnel is down or its address just rotated) that would raise and
        # crash startup, so the platform reports "no open ports" and the service
        # never goes live. The v2 routes connect to SQL per-request and do not
        # need this registry, so degrade gracefully: log and continue with a
        # None registry. The older token-based routes that DO use it will surface
        # a clear error per-request instead of taking down the whole service.
        resolved_registry = runtime_registry
        if resolved_registry is None:
            try:
                resolved_registry = build_runtime_registry(
                    resolved_settings
                )
            except Exception as exc:  # noqa: BLE001 - must not crash startup
                import logging

                logging.getLogger("uvicorn.error").warning(
                    "Runtime registry build failed at startup "
                    "(continuing without it; DB may be unreachable): %s",
                    exc,
                )
                resolved_registry = None

        application.state.settings = (
            resolved_settings
        )
        application.state.runtime_registry = (
            resolved_registry
        )

        yield

    application = FastAPI(
        title=(
            settings.title
            if settings
            else "Pump Configuration API"
        ),
        version=(
            settings.version
            if settings
            else "0.19.0"
        ),
        description=(
            "Closed allowable-configuration API. "
            "The service accepts only server-issued "
            "state and option tokens."
        ),
        lifespan=lifespan,
        docs_url=(
            "/docs"
            if settings is None
            or settings.docs_enabled
            else None
        ),
        redoc_url=None,
    )

    application.include_router(router)
    application.include_router(router_v2)

    # CORS — allow all origins for development
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(
        RequestValidationError
    )
    async def request_validation_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        del request, exc
        return _error_response(
            status_code=422,
            code="request_schema_violation",
            message=(
                "The request does not match the "
                "closed API contract."
            ),
        )

    @application.exception_handler(
        UnsupportedPumpFamilyError
    )
    async def unsupported_family_handler(
        request: Request,
        exc: UnsupportedPumpFamilyError,
    ) -> JSONResponse:
        del request, exc
        return _error_response(
            status_code=404,
            code="pump_family_not_configured",
            message=(
                "The requested pump family is not "
                "configured in this service."
            ),
        )

    @application.exception_handler(
        NavigationTokenError
    )
    async def token_handler(
        request: Request,
        exc: NavigationTokenError,
    ) -> JSONResponse:
        del request, exc
        return _error_response(
            status_code=409,
            code="configuration_token_conflict",
            message=(
                "The configuration token is invalid, "
                "stale, or not applicable to the "
                "current state."
            ),
        )

    @application.exception_handler(
        NoAllowableOptionsError
    )
    async def no_options_handler(
        request: Request,
        exc: NoAllowableOptionsError,
    ) -> JSONResponse:
        del request, exc
        return _error_response(
            status_code=409,
            code="allowable_options_unavailable",
            message=(
                "No allowable continuation exists for "
                "the current metadata state."
            ),
        )

    @application.exception_handler(
        AllowableNavigationError
    )
    async def navigation_handler(
        request: Request,
        exc: AllowableNavigationError,
    ) -> JSONResponse:
        del request, exc
        return _error_response(
            status_code=409,
            code="configuration_state_conflict",
            message=(
                "The signed configuration state cannot "
                "be advanced or finalized."
            ),
        )

    @application.exception_handler(
        ConfigurationOperationConflict
    )
    async def operation_conflict_handler(
        request: Request,
        exc: ConfigurationOperationConflict,
    ) -> JSONResponse:
        del request, exc
        return _error_response(
            status_code=409,
            code="configuration_operation_conflict",
            message=(
                "The signed configuration state is "
                "not ready for this operation."
            ),
        )

    @application.exception_handler(
        ConfiguredProductPersistenceError
    )
    async def persistence_handler(
        request: Request,
        exc: ConfiguredProductPersistenceError,
    ) -> JSONResponse:
        del request, exc
        return _error_response(
            status_code=409,
            code="configured_product_conflict",
            message=(
                "The completed configuration could not "
                "be persisted or reused."
            ),
        )

    @application.exception_handler(
        pyodbc.Error
    )
    async def database_handler(
        request: Request,
        exc: pyodbc.Error,
    ) -> JSONResponse:
        del request, exc
        return _error_response(
            status_code=503,
            code="database_unavailable",
            message=(
                "The configuration database is "
                "temporarily unavailable."
            ),
        )

    @application.exception_handler(
        ApiConfigurationError
    )
    async def configuration_handler(
        request: Request,
        exc: ApiConfigurationError,
    ) -> JSONResponse:
        del request, exc
        return _error_response(
            status_code=503,
            code="service_configuration_error",
            message=(
                "The API service configuration is "
                "incomplete."
            ),
        )

    return application


# Mount static UI AFTER app creation (must be last to avoid route conflicts)
app = create_app()

_ui_dir = PROJECT_ROOT / "ui"
if _ui_dir.exists():
    app.mount(
        "/ui",
        StaticFiles(directory=str(_ui_dir), html=True),
        name="ui",
    )

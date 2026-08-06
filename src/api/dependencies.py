from __future__ import annotations

from fastapi import Request

from src.api.runtime_registry import (
    ConfigurationRuntimeRegistry,
)


def get_runtime_registry(
    request: Request,
) -> ConfigurationRuntimeRegistry:
    return request.app.state.runtime_registry

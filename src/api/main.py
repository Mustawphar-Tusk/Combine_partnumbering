"""Compatibility entry point for the Pump Configuration API.

The canonical FastAPI application is defined in src.api.app.
"""

from src.api.app import app

__all__ = ["app"]

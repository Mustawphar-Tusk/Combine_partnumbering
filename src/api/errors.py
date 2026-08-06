from __future__ import annotations


class ConfigurationOperationConflict(RuntimeError):
    """Raised when a signed state is not ready for an operation."""

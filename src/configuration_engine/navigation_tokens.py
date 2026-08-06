from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any


class NavigationTokenError(ValueError):
    """Raised when a state or option token cannot be trusted."""


@dataclass(frozen=True)
class NavigationTokenCodec:
    secret: bytes

    @classmethod
    def from_text(
        cls,
        secret: str,
    ) -> "NavigationTokenCodec":
        value = secret.encode("utf-8")

        if len(value) < 32:
            raise ValueError(
                "Navigation token secret must contain at least "
                "32 characters."
            )

        return cls(secret=value)

    def encode(
        self,
        payload: dict[str, Any],
    ) -> str:
        body = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

        signature = hmac.new(
            self.secret,
            body,
            hashlib.sha256,
        ).digest()

        return (
            self._base64_encode(body)
            + "."
            + self._base64_encode(signature)
        )

    def decode(
        self,
        token: str,
    ) -> dict[str, Any]:
        try:
            encoded_body, encoded_signature = token.split(
                ".",
                1,
            )
            body = self._base64_decode(encoded_body)
            supplied_signature = self._base64_decode(
                encoded_signature
            )
        except Exception as exc:
            raise NavigationTokenError(
                "Malformed navigation token."
            ) from exc

        expected_signature = hmac.new(
            self.secret,
            body,
            hashlib.sha256,
        ).digest()

        if not hmac.compare_digest(
            supplied_signature,
            expected_signature,
        ):
            raise NavigationTokenError(
                "Navigation token signature is invalid."
            )

        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception as exc:
            raise NavigationTokenError(
                "Navigation token payload is invalid."
            ) from exc

        if not isinstance(payload, dict):
            raise NavigationTokenError(
                "Navigation token payload must be an object."
            )

        return payload

    @staticmethod
    def _base64_encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(
            b"="
        ).decode("ascii")

    @staticmethod
    def _base64_decode(value: str) -> bytes:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(
            value + padding
        )

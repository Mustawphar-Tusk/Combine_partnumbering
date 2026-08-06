import pytest

from src.configuration_engine.navigation_tokens import (
    NavigationTokenCodec,
    NavigationTokenError,
)


def codec() -> NavigationTokenCodec:
    return NavigationTokenCodec.from_text(
        "01234567890123456789012345678901"
    )


def test_token_round_trip() -> None:
    payload = {
        "token_type": "configuration_state",
        "selections": {},
    }

    token = codec().encode(payload)

    assert codec().decode(token) == payload


def test_tampered_token_is_rejected() -> None:
    token = codec().encode(
        {"token_type": "configuration_state"}
    )

    body, signature = token.split(".", 1)
    replacement = "A" if body[-1] != "A" else "B"
    tampered = body[:-1] + replacement + "." + signature

    with pytest.raises(NavigationTokenError):
        codec().decode(tampered)

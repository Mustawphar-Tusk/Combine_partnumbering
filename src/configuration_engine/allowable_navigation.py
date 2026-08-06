from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from src.configuration_engine.available_options import (
    AvailableOptionsRequest,
    AvailableOptionsService,
)
from src.configuration_engine.navigation_tokens import (
    NavigationTokenCodec,
    NavigationTokenError,
)


class AllowableNavigationError(RuntimeError):
    """Base class for defensive navigation failures."""


class NoAllowableOptionsError(AllowableNavigationError):
    """Raised when authoritative metadata returns no next choice."""


@dataclass(frozen=True)
class AllowableOption:
    field_code: str
    display_value: str
    option_token: str


@dataclass(frozen=True)
class AllowableNavigationResponse:
    family_code: str
    runtime_revision: str
    state_token: str
    complete: bool
    next_field_code: str | None
    options: tuple[AllowableOption, ...]
    selection_count: int


class AllowableConfigurationNavigator:
    """
    Closed navigation over allowable configuration metadata.

    Public navigation accepts only:
    - a signed state token issued by this service
    - a signed option token issued for that exact state
    """

    def __init__(
        self,
        *,
        available_options_service: AvailableOptionsService,
        token_codec: NavigationTokenCodec,
        runtime_revision: str,
        field_order: tuple[str, ...],
        segment_field_map: dict[str, str],
        combination_segment_field_order: dict[
            str,
            tuple[str, ...],
        ],
        series_code_pattern: str = r"(\d{4})",
    ) -> None:
        self.available_options_service = (
            available_options_service
        )
        self.token_codec = token_codec
        self.runtime_revision = runtime_revision
        self.field_order = tuple(
            field.strip().upper()
            for field in field_order
        )
        self.segment_field_map = {
            field.strip().upper(): segment.strip().upper()
            for field, segment in segment_field_map.items()
        }
        self.combination_segment_field_order = {
            segment.strip().upper(): tuple(
                field.strip().upper()
                for field in fields
            )
            for segment, fields
            in combination_segment_field_order.items()
        }
        self.series_code_regex = re.compile(
            series_code_pattern
        )

        if not self.field_order:
            raise ValueError(
                "Allowable navigation field order is empty."
            )

    def start(
        self,
        *,
        family_code: str,
    ) -> AllowableNavigationResponse:
        state_payload = {
            "token_type": "configuration_state",
            "schema_version": 1,
            "family_code": family_code.strip().upper(),
            "runtime_revision": self.runtime_revision,
            "selections": {},
        }
        return self._build_response(state_payload)

    def resume(
        self,
        *,
        state_token: str,
    ) -> AllowableNavigationResponse:
        return self._build_response(
            self._decode_state(state_token)
        )

    def advance(
        self,
        *,
        state_token: str,
        option_token: str,
    ) -> AllowableNavigationResponse:
        state_payload = self._decode_state(
            state_token
        )
        option_payload = self.token_codec.decode(
            option_token
        )

        self._verify_option_payload(
            state_payload=state_payload,
            option_payload=option_payload,
        )

        current_response = self._build_response(
            state_payload
        )

        issued_option = next(
            (
                option
                for option in current_response.options
                if option.option_token == option_token
            ),
            None,
        )

        if issued_option is None:
            raise NavigationTokenError(
                "The option token is not available for the "
                "current configuration state."
            )

        selections = dict(
            state_payload["selections"]
        )
        selections[issued_option.field_code] = (
            issued_option.display_value
        )

        next_state = {
            **state_payload,
            "selections": selections,
        }

        return self._build_response(next_state)

    def selections_from_state(
        self,
        *,
        state_token: str,
        require_complete: bool = True,
    ) -> dict[str, str]:
        state_payload = self._decode_state(
            state_token
        )

        if require_complete:
            missing = [
                field
                for field in self.field_order
                if field not in state_payload["selections"]
            ]

            if missing:
                raise AllowableNavigationError(
                    "Configuration state is not complete."
                )

        return dict(state_payload["selections"])

    def _build_response(
        self,
        state_payload: dict[str, Any],
    ) -> AllowableNavigationResponse:
        selections = dict(
            state_payload["selections"]
        )
        next_field = next(
            (
                field
                for field in self.field_order
                if field not in selections
            ),
            None,
        )

        state_token = self.token_codec.encode(
            state_payload
        )

        if next_field is None:
            return AllowableNavigationResponse(
                family_code=state_payload[
                    "family_code"
                ],
                runtime_revision=self.runtime_revision,
                state_token=state_token,
                complete=True,
                next_field_code=None,
                options=(),
                selection_count=len(selections),
            )

        series_code = self._resolve_series_code(
            selections
        )
        segment_code = self.segment_field_map.get(
            next_field
        )
        segment_selections = self._segment_selections(
            segment_code=segment_code,
            selections=selections,
        )

        result = (
            self.available_options_service
            .available_options(
                AvailableOptionsRequest(
                    family_code=state_payload[
                        "family_code"
                    ],
                    target_field_code=next_field,
                    series_code=series_code,
                    segment_code=segment_code,
                    current_segment_selections=(
                        segment_selections
                    ),
                    current_selections=selections,
                )
            )
        )

        if not result.values:
            raise NoAllowableOptionsError(
                "Authoritative metadata returned no allowable "
                f"options for {next_field}."
            )

        fingerprint = self._state_fingerprint(
            state_payload
        )

        options = tuple(
            AllowableOption(
                field_code=next_field,
                display_value=value,
                option_token=self.token_codec.encode(
                    {
                        "token_type": (
                            "configuration_option"
                        ),
                        "schema_version": 1,
                        "family_code": state_payload[
                            "family_code"
                        ],
                        "runtime_revision": (
                            self.runtime_revision
                        ),
                        "state_fingerprint": fingerprint,
                        "field_code": next_field,
                        "display_value": value,
                    }
                ),
            )
            for value in result.values
        )

        return AllowableNavigationResponse(
            family_code=state_payload[
                "family_code"
            ],
            runtime_revision=self.runtime_revision,
            state_token=state_token,
            complete=False,
            next_field_code=next_field,
            options=options,
            selection_count=len(selections),
        )

    def _decode_state(
        self,
        token: str,
    ) -> dict[str, Any]:
        payload = self.token_codec.decode(token)

        if payload.get("token_type") != (
            "configuration_state"
        ):
            raise NavigationTokenError(
                "Expected a configuration state token."
            )

        if payload.get("runtime_revision") != (
            self.runtime_revision
        ):
            raise NavigationTokenError(
                "Configuration state belongs to an older "
                "metadata revision."
            )

        selections = payload.get("selections")

        if not isinstance(selections, dict):
            raise NavigationTokenError(
                "Configuration state selections are invalid."
            )

        unexpected = [
            field
            for field in selections
            if field not in self.field_order
        ]

        if unexpected:
            raise NavigationTokenError(
                "Configuration state contains unexpected fields."
            )

        # JSON token encoding sorts object keys. Therefore validity must
        # be checked by membership in the required field-order prefix,
        # not by dictionary insertion order.
        expected_prefix = set(
            self.field_order[: len(selections)]
        )

        if set(selections) != expected_prefix:
            raise NavigationTokenError(
                "Configuration state does not follow the "
                "allowable field order."
            )

        return payload

    def _verify_option_payload(
        self,
        *,
        state_payload: dict[str, Any],
        option_payload: dict[str, Any],
    ) -> None:
        if option_payload.get("token_type") != (
            "configuration_option"
        ):
            raise NavigationTokenError(
                "Expected a configuration option token."
            )

        if option_payload.get("family_code") != (
            state_payload["family_code"]
        ):
            raise NavigationTokenError(
                "Option token belongs to another pump family."
            )

        if option_payload.get("runtime_revision") != (
            self.runtime_revision
        ):
            raise NavigationTokenError(
                "Option token belongs to an older metadata "
                "revision."
            )

        expected_fingerprint = (
            self._state_fingerprint(state_payload)
        )

        if option_payload.get("state_fingerprint") != (
            expected_fingerprint
        ):
            raise NavigationTokenError(
                "Option token was not issued for the current "
                "configuration state."
            )

        expected_field = next(
            (
                field
                for field in self.field_order
                if field not in state_payload["selections"]
            ),
            None,
        )

        if option_payload.get("field_code") != expected_field:
            raise NavigationTokenError(
                "Option token is not for the current field."
            )

    def _resolve_series_code(
        self,
        selections: dict[str, str],
    ) -> str | None:
        value = selections.get("SERIES")

        if value is None:
            return None

        match = self.series_code_regex.search(value)

        if match is None:
            raise AllowableNavigationError(
                "Selected Series does not contain a resolvable "
                "series code."
            )

        return match.group(1)

    def _segment_selections(
        self,
        *,
        segment_code: str | None,
        selections: dict[str, str],
    ) -> dict[str, str]:
        if segment_code is None:
            return {}

        fields = self.combination_segment_field_order.get(
            segment_code
        )

        if fields is None:
            raise AllowableNavigationError(
                f"No field order exists for segment "
                f"{segment_code}."
            )

        return {
            field: selections[field]
            for field in fields
            if field in selections
        }

    @staticmethod
    def _state_fingerprint(
        state_payload: dict[str, Any],
    ) -> str:
        body = json.dumps(
            state_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

        return hashlib.sha256(body).hexdigest()

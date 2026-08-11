from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_FAMILY = "FYBROC"

EXPECTED_VERSION_ID = 5
EXPECTED_VERSION_CODE = "FYBROC-CONFIG-20260807-V3"

EXPECTED_BASE_AMOUNT = Decimal("4854")
EXPECTED_SEAL_AMOUNT = Decimal("749")
EXPECTED_TOTAL_AMOUNT = Decimal("5603")

# These values define the pricing proof. Every selection is still made
# exclusively from server-issued allowable options and submitted using
# the corresponding server-issued option token.
PROOF_OVERRIDES = {
    "SERIES": "1530 (ANSI)",
    "SIZE": "1x1.5x6",
    "PUMP_MATERIAL": "VR-1*",
    "SEAL_OPTION": "Mechanical Seal Included*",
    "SEAL_TYPE": "8B2 Single Outside*",
    "SEAL_MATERIALS": "Carbon vs. Ceramic*",
    "SEAL_ELASTOMERS": "FKM*",
}


def _decimal(value) -> Decimal:
    return Decimal(str(value))


def _request_json(
    *,
    method: str,
    url: str,
    payload=None,
    headers: dict[str, str] | None = None,
):
    body = None

    request_headers = {
        "Accept": "application/json",
    }

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    if headers:
        request_headers.update(headers)

    request = Request(
        url=url,
        data=body,
        method=method,
        headers=request_headers,
    )

    try:
        with urlopen(
            request,
            timeout=30,
        ) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw)

    except HTTPError as exc:
        raw = exc.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            f"{method} {url} failed with HTTP "
            f"{exc.code}:\n{raw}"
        ) from exc

    except URLError as exc:
        raise RuntimeError(
            f"{method} {url} failed: {exc}"
        ) from exc


def _load_test_preferences() -> dict:
    path = (
        ROOT
        / "config"
        / "runtime_profiles"
        / "fybroc_session_test_preferences.json"
    )

    if not path.exists():
        return {}

    return json.loads(
        path.read_text(
            encoding="utf-8-sig",
        )
    )


def _preferred_value(
    field_code: str,
    preferences: dict,
) -> str | None:
    entry = preferences.get(
        field_code
    )

    if isinstance(entry, str):
        return entry

    if isinstance(entry, dict):
        exact = entry.get("exact")

        if exact is not None:
            return str(exact)

    return None


def _choose_option(
    *,
    field_code: str,
    options: list[dict],
    preferences: dict,
) -> dict:
    if not options:
        raise RuntimeError(
            f"{field_code}: server returned no allowable options."
        )

    required_value = PROOF_OVERRIDES.get(
        field_code
    )

    desired_value = (
        required_value
        if required_value is not None
        else _preferred_value(
            field_code,
            preferences,
        )
    )

    if desired_value is not None:
        for option in options:
            if (
                option["displayValue"]
                == desired_value
            ):
                return option

        if required_value is not None:
            available = ", ".join(
                repr(
                    option["displayValue"]
                )
                for option in options
            )

            raise RuntimeError(
                f"{field_code}: required live-proof value "
                f"{required_value!r} is not currently allowable.\n"
                f"Server-issued options: {available}"
            )

    # Non-proof fields may safely use the first server-issued allowable
    # option when the deterministic test preference is unavailable.
    return options[0]


def _component_by_code(
    pricing: dict,
    component_code: str,
) -> dict:
    matches = [
        component
        for component in pricing[
            "components"
        ]
        if (
            component[
                "componentCode"
            ]
            == component_code
        )
    ]

    if len(matches) != 1:
        raise AssertionError(
            f"Expected exactly one {component_code} "
            f"pricing component; received {len(matches)}."
        )

    return matches[0]


def _assert_live_pricing(
    response: dict,
) -> None:
    pricing = response.get(
        "pricing"
    )

    if pricing is None:
        raise AssertionError(
            "Finalize response did not include nested pricing."
        )

    if (
        pricing["status"]
        != "found"
    ):
        raise AssertionError(
            "Expected aggregate pricing status 'found'; "
            f"received {pricing['status']!r}."
        )

    if (
        pricing[
            "priceBookVersionId"
        ]
        != EXPECTED_VERSION_ID
    ):
        raise AssertionError(
            "Aggregate pricing did not use active V3. "
            f"Expected version ID {EXPECTED_VERSION_ID}, "
            f"received "
            f"{pricing['priceBookVersionId']!r}."
        )

    if (
        pricing["versionCode"]
        != EXPECTED_VERSION_CODE
    ):
        raise AssertionError(
            "Aggregate pricing version-code mismatch. "
            f"Expected {EXPECTED_VERSION_CODE!r}, "
            f"received {pricing['versionCode']!r}."
        )

    base = _component_by_code(
        pricing,
        "BASE_PUMP",
    )

    seal = _component_by_code(
        pricing,
        "SEAL",
    )

    for component in (
        base,
        seal,
    ):
        if (
            component["status"]
            != "found"
        ):
            raise AssertionError(
                f"{component['componentCode']} pricing "
                f"status is {component['status']!r}, not 'found'."
            )

        if (
            component[
                "priceBookVersionId"
            ]
            != EXPECTED_VERSION_ID
        ):
            raise AssertionError(
                f"{component['componentCode']} used "
                "the wrong price-book version ID."
            )

        if (
            component["versionCode"]
            != EXPECTED_VERSION_CODE
        ):
            raise AssertionError(
                f"{component['componentCode']} used "
                "the wrong price-book version code."
            )

    base_amount = _decimal(
        base["amount"]
    )

    seal_amount = _decimal(
        seal["amount"]
    )

    total_amount = _decimal(
        pricing["totalAmount"]
    )

    known_amount = _decimal(
        pricing["knownAmount"]
    )

    legacy_price = _decimal(
        response["price"]
    )

    if (
        base_amount
        != EXPECTED_BASE_AMOUNT
    ):
        raise AssertionError(
            f"BASE_PUMP expected {EXPECTED_BASE_AMOUNT}; "
            f"received {base_amount}."
        )

    if (
        seal_amount
        != EXPECTED_SEAL_AMOUNT
    ):
        raise AssertionError(
            f"SEAL expected {EXPECTED_SEAL_AMOUNT}; "
            f"received {seal_amount}."
        )

    if (
        total_amount
        != EXPECTED_TOTAL_AMOUNT
    ):
        raise AssertionError(
            f"Aggregate total expected "
            f"{EXPECTED_TOTAL_AMOUNT}; "
            f"received {total_amount}."
        )

    if (
        known_amount
        != EXPECTED_TOTAL_AMOUNT
    ):
        raise AssertionError(
            f"Known amount expected "
            f"{EXPECTED_TOTAL_AMOUNT}; "
            f"received {known_amount}."
        )

    if (
        legacy_price
        != base_amount
    ):
        raise AssertionError(
            "Backward-compatible top-level price no longer "
            "equals the BASE_PUMP component amount."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Drive a live 41-field FYBROC API session and prove "
            "M022.6 aggregate pricing against active V3."
        )
    )

    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
    )

    parser.add_argument(
        "--family",
        default=DEFAULT_FAMILY,
    )

    parser.add_argument(
        "--requested-by",
        default="m0226-live-proof",
    )

    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    family = args.family.strip().upper()

    preferences = _load_test_preferences()

    start_url = (
        f"{base_url}/api/v1/families/"
        f"{family}/configurations/start"
    )

    advance_url = (
        f"{base_url}/api/v1/families/"
        f"{family}/configurations/advance"
    )

    finalize_url = (
        f"{base_url}/api/v1/families/"
        f"{family}/configurations/finalize"
    )

    print("=" * 80)
    print("M022.6 LIVE FASTAPI V3 PRICING PROOF")
    print("=" * 80)

    navigation = _request_json(
        method="POST",
        url=start_url,
        payload={},
    )

    print(
        "Runtime revision :",
        navigation[
            "runtimeRevision"
        ],
    )

    step = 0

    while not navigation["complete"]:
        step += 1

        if step > 60:
            raise RuntimeError(
                "Navigation exceeded 60 steps."
            )

        field_code = navigation[
            "nextFieldCode"
        ]

        if field_code is None:
            raise RuntimeError(
                "Navigation is incomplete but "
                "nextFieldCode is null."
            )

        option = _choose_option(
            field_code=field_code,
            options=navigation[
                "options"
            ],
            preferences=preferences,
        )

        print(
            f"{step:02d}. "
            f"{field_code:<28} "
            f"-> {option['displayValue']}"
        )

        navigation = _request_json(
            method="POST",
            url=advance_url,
            payload={
                "stateToken":
                    navigation[
                        "stateToken"
                    ],
                "optionToken":
                    option[
                        "optionToken"
                    ],
            },
        )

    print()
    print(
        "Navigation complete with",
        navigation[
            "selectionCount"
        ],
        "selections.",
    )

    if (
        navigation[
            "selectionCount"
        ]
        != 41
    ):
        raise AssertionError(
            "Expected the FYBROC live proof to complete "
            "with 41 selections; received "
            f"{navigation['selectionCount']}."
        )

    response = _request_json(
        method="POST",
        url=finalize_url,
        payload={
            "stateToken":
                navigation[
                    "stateToken"
                ],
        },
        headers={
            "X-Requested-By":
                args.requested_by,
        },
    )

    _assert_live_pricing(
        response
    )

    pricing = response[
        "pricing"
    ]

    base = _component_by_code(
        pricing,
        "BASE_PUMP",
    )

    seal = _component_by_code(
        pricing,
        "SEAL",
    )

    print()
    print("=" * 80)
    print("LIVE PROOF PASSED")
    print("=" * 80)
    print(
        "Registry ID       :",
        response[
            "configuredProductRegistryId"
        ],
    )
    print(
        "Was created       :",
        response[
            "wasCreated"
        ],
    )
    print(
        "Part number       :",
        response[
            "partNumber"
        ],
    )
    print(
        "SKU               :",
        response[
            "sku"
        ],
    )
    print(
        "Legacy price      :",
        response[
            "price"
        ],
        "(BASE_PUMP compatibility)",
    )
    print(
        "Pricing status    :",
        pricing[
            "status"
        ],
    )
    print(
        "Known amount      :",
        pricing[
            "knownAmount"
        ],
    )
    print(
        "Total amount      :",
        pricing[
            "totalAmount"
        ],
    )
    print(
        "Version ID        :",
        pricing[
            "priceBookVersionId"
        ],
    )
    print(
        "Version code      :",
        pricing[
            "versionCode"
        ],
    )
    print(
        "BASE_PUMP         :",
        base[
            "amount"
        ],
        base[
            "status"
        ],
        "rule",
        base[
            "priceRuleId"
        ],
    )
    print(
        "SEAL              :",
        seal[
            "amount"
        ],
        seal[
            "status"
        ],
        "rule",
        seal[
            "priceRuleId"
        ],
    )

    print()
    print(
        json.dumps(
            response,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

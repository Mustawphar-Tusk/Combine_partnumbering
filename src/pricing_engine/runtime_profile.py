from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PricingRuntimeProfile:
    family_code: str
    price_book_code: str | None
    component_codes: tuple[str, ...]
    legacy_component_code: str


def load_pricing_runtime_profile(
    project_root: Path,
    family_code: str,
) -> PricingRuntimeProfile:
    normalized_family = (
        family_code.strip().upper()
    )

    path = (
        project_root
        / "config"
        / "pricing_runtime"
        / f"{normalized_family.lower()}.json"
    )

    data = json.loads(
        path.read_text(
            encoding="utf-8-sig",
        )
    )

    profile_family = str(
        data["family_code"]
    ).strip().upper()

    if profile_family != normalized_family:
        raise RuntimeError(
            "Pricing runtime profile family mismatch: "
            f"requested={normalized_family}, "
            f"profile={profile_family}."
        )

    component_codes = tuple(
        str(value).strip().upper()
        for value in data[
            "component_codes"
        ]
        if str(value).strip()
    )

    if not component_codes:
        raise RuntimeError(
            "Pricing runtime profile contains "
            "no component codes."
        )

    if len(component_codes) != len(
        set(component_codes)
    ):
        raise RuntimeError(
            "Pricing runtime profile contains "
            "duplicate component codes."
        )

    legacy_component_code = str(
        data.get(
            "legacy_component_code"
        )
        or component_codes[0]
    ).strip().upper()

    if (
        legacy_component_code
        not in component_codes
    ):
        raise RuntimeError(
            "Legacy pricing component must be "
            "one of the configured components."
        )

    raw_price_book_code = data.get(
        "price_book_code"
    )

    price_book_code = (
        None
        if raw_price_book_code is None
        else str(
            raw_price_book_code
        ).strip().upper()
    )

    return PricingRuntimeProfile(
        family_code=profile_family,
        price_book_code=(
            price_book_code
        ),
        component_codes=(
            component_codes
        ),
        legacy_component_code=(
            legacy_component_code
        ),
    )

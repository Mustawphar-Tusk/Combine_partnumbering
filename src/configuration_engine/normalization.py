from __future__ import annotations

import re


def normalize_display_value(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def canonicalize_selections(
    selections: dict[str, str],
    field_order: tuple[str, ...],
) -> dict[str, str]:
    missing = [
        field_code
        for field_code in field_order
        if field_code not in selections
    ]

    extra = [
        field_code
        for field_code in selections
        if field_code not in field_order
    ]

    if missing:
        raise ValueError(
            "Missing selection fields: " + ", ".join(missing)
        )

    if extra:
        raise ValueError(
            "Unexpected selection fields: " + ", ".join(extra)
        )

    return {
        field_code: normalize_display_value(selections[field_code])
        for field_code in field_order
    }


def build_combination_key(
    selections: dict[str, str],
    field_order: tuple[str, ...],
) -> str:
    canonical = canonicalize_selections(
        selections,
        field_order,
    )

    return "|".join(
        canonical[field_code]
        for field_code in field_order
    )

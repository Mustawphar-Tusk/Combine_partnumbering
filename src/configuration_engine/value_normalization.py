from __future__ import annotations

import re
from collections.abc import Mapping


def normalize_engineering_value(value: str) -> str:
    """
    Generic normalization for comparison only.
    """
    text = str(value).strip()
    text = text.replace("_", " ")
    text = text.rstrip("*").strip()
    text = re.sub(r"\s+", " ", text)
    return text.casefold()


def _motor_frame_stem(value: str) -> str:
    """
    Return the numeric NEMA frame stem.

    Examples:
        143JM -> 143
        284TS -> 284
        326T  -> 326
        143   -> 143

    Series applicability and Motor Assembly use different suffix
    conventions. Orientation/type remains enforced by the Motor
    Assembly combination metadata, not by the series-frame stem.
    """
    compact = normalize_engineering_value(value).replace(" ", "")
    match = re.match(r"^(\d+)", compact)

    if match is None:
        return compact

    return match.group(1)


def canonical_engineering_value(
    *,
    field_code: str,
    value: str,
    context: Mapping[str, str] | None = None,
    source_type: str | None = None,
) -> str:
    """
    Produce a field-aware comparison key without altering display text.
    """
    field = field_code.strip().upper()

    if field == "MOTOR_FRAME":
        return _motor_frame_stem(value)

    return normalize_engineering_value(value)


def canonical_value_map(
    *,
    field_code: str,
    values: list[str] | tuple[str, ...],
    context: Mapping[str, str] | None = None,
    source_type: str | None = None,
) -> dict[str, str]:
    """
    Return canonical comparison key -> original display value.

    The first original display value is retained.
    """
    result: dict[str, str] = {}

    for value in values:
        key = canonical_engineering_value(
            field_code=field_code,
            value=value,
            context=context,
            source_type=source_type,
        )
        result.setdefault(key, value)

    return result

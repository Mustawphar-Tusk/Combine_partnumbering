"""Canonical normalization for the Fybroc SERIES type.

Scope: this module intentionally covers ONLY the series-code type coercion
issue, not a general-purpose normalization layer.

The V6 Attributes Series+Flange table (Nomenclature_V6.xlsm) stores series
values with inconsistent cell types: 1500/1530/1600/1630/5530/6000/7500/7530/
8500 are TEXT, but 2530/3000/5500 are INTEGER. When those cells are read
(openpyxl) or written back (Excel COM), the integer ones surface as numbers
(e.g. 5500 / 5500.0) instead of the text "5500".

The application's canonical type for a series code is TEXT. norm_series is the
single helper that converts an authoritative series cell value into that
canonical text form, so a series is "5500" everywhere downstream, never
5500 or "5500.0". See docs/DATA_TYPE_NORMALIZATION.md.
"""

from __future__ import annotations

from typing import Any


def norm_series(value: Any) -> str | None:
    """Series code as canonical TEXT, or None if blank.

    Handles the workbook's mixed str/int storage: an integer 5500 and a text
    '1500' both normalize to bare digit strings. A whole float (e.g. 5500.0
    from Excel COM / openpyxl) is rendered without a trailing '.0'.
    """
    if value is None:
        return None
    if isinstance(value, bool):  # guard: bools are ints in Python
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value).strip()
    text = str(value).strip()
    return text or None

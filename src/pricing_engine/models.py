from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PricingCondition:
    sequence_no: int
    field_code: str
    comparison_operator: str
    comparison_value: str | None


@dataclass(frozen=True)
class PricingRule:
    price_book_code: str
    price_book_version_id: int
    version_code: str
    currency_code: str

    price_rule_id: int
    rule_code: str
    component_code: str
    series_code: str | None
    priority: int

    amount: Decimal
    pricing_status: str

    conditions: tuple[
        PricingCondition,
        ...
    ]

    source_size_value: str | None = None
    source_option_value: str | None = None
    source_price_value: str | None = None
    source_worksheet: str | None = None
    source_table: str | None = None
    source_cell: str | None = None


@dataclass(frozen=True)
class PricingResult:
    amount: Decimal
    status: str
    currency_code: str | None

    price_book_code: str | None
    price_book_version_id: int | None
    version_code: str | None
    price_rule_id: int | None

    component_code: str

    source_worksheet: str | None = None
    source_table: str | None = None
    source_cell: str | None = None

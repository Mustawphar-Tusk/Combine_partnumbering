from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )


from src.pricing_engine import (
    PricingService,
    SqlPricingRepository,
)


service = PricingService(
    SqlPricingRepository()
)


cases = [
    (
        "1530 STANDARD PRICE",
        {
            "SERIES": "1530",
            "SIZE": "1x1.5x6",
            "PUMP_MATERIAL": "VR-1*",
        },
        "found",
        Decimal("4854"),
    ),
    (
        "3000 STANDARD PRICE",
        {
            "SERIES": "3000",
            "SIZE": "2x3x6",
            "PUMP_MATERIAL": "VR-1*",
        },
        "found",
        Decimal("11773"),
    ),
    (
        "3000 CALL FOR PRICE",
        {
            "SERIES": "3000",
            "SIZE": "6x8x11",
            "PUMP_MATERIAL": "VR-1*",
        },
        "call_for_price",
        Decimal("0"),
    ),
    (
        "KNOWN PRICING GAP",
        {
            "SERIES": "1530",
            "SIZE": "1x1.5x6",
            "PUMP_MATERIAL":
                "VR-1A BPO/DMA",
        },
        "not_found",
        Decimal("0"),
    ),
]


print("=" * 80)
print(
    "M021.2.2 SHARED PRICING RESOLVER"
)
print("=" * 80)


for (
    name,
    configuration,
    expected_status,
    expected_amount,
) in cases:

    result = service.resolve(
        family_code="FYBROC",
        configuration=configuration,
    )

    print()
    print(name)
    print("-" * 80)

    print(
        "Status               :",
        result.status,
    )

    print(
        "Amount               :",
        result.amount,
    )

    print(
        "Currency             :",
        result.currency_code,
    )

    print(
        "Price Book Version ID:",
        result.price_book_version_id,
    )

    print(
        "Version Code         :",
        result.version_code,
    )

    print(
        "Price Rule ID        :",
        result.price_rule_id,
    )

    print(
        "Source               :",
        result.source_worksheet,
        result.source_table,
        result.source_cell,
    )

    assert (
        result.status
        == expected_status
    )

    assert (
        result.amount
        == expected_amount
    )


print()
print("=" * 80)
print(
    "All shared pricing resolver "
    "checks passed."
)
print("=" * 80)

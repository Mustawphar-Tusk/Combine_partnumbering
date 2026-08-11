from decimal import Decimal

from src.api.presenters import (
    _present_configuration_pricing,
)
from src.pricing_engine.models import (
    PricingResult,
)


def test_m02261_legacy_pricing_result_is_presentable():
    pricing = PricingResult(
        amount=Decimal("4854"),
        status="found",
        currency_code="USD",
        price_book_code="FYBROC_STANDARD",
        price_book_version_id=4,
        version_code=(
            "FYBROC-BASE-20260807-V2"
        ),
        price_rule_id=655,
        component_code="BASE_PUMP",
        source_worksheet="Pricebook",
        source_table="Table49",
        source_cell="U6",
    )

    data = _present_configuration_pricing(
        pricing
    )

    assert (
        data["total_amount"]
        == Decimal("4854")
    )
    assert (
        data["known_amount"]
        == Decimal("4854")
    )
    assert data["status"] == "found"
    assert len(data["components"]) == 1
    assert (
        data["components"][0][
            "component_code"
        ]
        == "BASE_PUMP"
    )


def test_m02261_legacy_non_found_price_is_not_totaled():
    pricing = PricingResult(
        amount=Decimal("0"),
        status="call_for_price",
        currency_code="USD",
        price_book_code="FYBROC_STANDARD",
        price_book_version_id=5,
        version_code=(
            "FYBROC-CONFIG-20260807-V3"
        ),
        price_rule_id=1,
        component_code="BASE_PUMP",
        source_worksheet=None,
        source_table=None,
        source_cell=None,
    )

    data = _present_configuration_pricing(
        pricing
    )

    assert data["total_amount"] == 0
    assert data["known_amount"] == 0
    assert (
        data["status"]
        == "call_for_price"
    )

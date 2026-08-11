from decimal import Decimal

from src.api.models import (
    ConfigurationPricingResponse,
    PricingComponentResponse,
)


def test_m0226_api_pricing_models_accept_component_breakdown():
    response = ConfigurationPricingResponse(
        total_amount=Decimal("5603"),
        known_amount=Decimal("5603"),
        status="found",
        currency_code="USD",
        price_book_code="FYBROC_STANDARD",
        price_book_version_id=5,
        version_code=(
            "FYBROC-CONFIG-20260807-V3"
        ),
        components=[
            PricingComponentResponse(
                component_code=(
                    "BASE_PUMP"
                ),
                amount=Decimal("4854"),
                status="found",
            ),
            PricingComponentResponse(
                component_code="SEAL",
                amount=Decimal("749"),
                status="found",
            ),
        ],
    )

    assert (
        response.total_amount
        == Decimal("5603")
    )
    assert len(response.components) == 2

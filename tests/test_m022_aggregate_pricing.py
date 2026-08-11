from __future__ import annotations

from decimal import Decimal

from src.pricing_engine.aggregate import (
    ConfigurationPricingService,
)
from src.pricing_engine.models import (
    PricingResult,
)


ZERO = Decimal("0")


def result(
    component_code: str,
    *,
    amount: str,
    status: str,
    version_id: int | None = 5,
    version_code: str | None = (
        "FYBROC-CONFIG-20260807-V3"
    ),
) -> PricingResult:
    return PricingResult(
        amount=Decimal(amount),
        status=status,
        currency_code=(
            "USD"
            if version_id is not None
            else None
        ),
        price_book_code=(
            "FYBROC_STANDARD"
            if version_id is not None
            else None
        ),
        price_book_version_id=(
            version_id
        ),
        version_code=(
            version_code
        ),
        price_rule_id=(
            1
            if version_id is not None
            else None
        ),
        component_code=(
            component_code
        ),
        source_worksheet=None,
        source_table=None,
        source_cell=None,
    )


class FakeComponentService:
    def __init__(
        self,
        results,
    ) -> None:
        self.results = results
        self.calls = []

    def resolve(
        self,
        *,
        family_code,
        configuration,
        component_code,
        price_book_code=None,
    ):
        self.calls.append(
            (
                family_code,
                component_code,
                price_book_code,
            )
        )

        return self.results[
            component_code
        ]


def service(results):
    inner = FakeComponentService(
        results
    )

    outer = ConfigurationPricingService(
        inner,
        component_codes=(
            "BASE_PUMP",
            "SEAL",
        ),
        legacy_component_code=(
            "BASE_PUMP"
        ),
        default_price_book_code=(
            "FYBROC_STANDARD"
        ),
    )

    return outer, inner


def test_m0226_found_components_are_aggregated():
    resolver, inner = service(
        {
            "BASE_PUMP": result(
                "BASE_PUMP",
                amount="4854",
                status="found",
            ),
            "SEAL": result(
                "SEAL",
                amount="749",
                status="found",
            ),
        }
    )

    pricing = resolver.resolve(
        family_code="FYBROC",
        configuration={},
    )

    assert (
        pricing.total_amount
        == Decimal("5603")
    )
    assert (
        pricing.known_amount
        == Decimal("5603")
    )
    assert (
        pricing.aggregate_status
        == "found"
    )

    # Frozen M021 compatibility:
    assert (
        pricing.amount
        == Decimal("4854")
    )
    assert pricing.status == "found"
    assert (
        pricing.component_code
        == "BASE_PUMP"
    )

    assert inner.calls == [
        (
            "FYBROC",
            "BASE_PUMP",
            "FYBROC_STANDARD",
        ),
        (
            "FYBROC",
            "SEAL",
            "FYBROC_STANDARD",
        ),
    ]


def test_m0226_call_for_price_zeroes_total_but_preserves_known_amount():
    resolver, _ = service(
        {
            "BASE_PUMP": result(
                "BASE_PUMP",
                amount="4854",
                status="found",
            ),
            "SEAL": result(
                "SEAL",
                amount="0",
                status=(
                    "call_for_price"
                ),
            ),
        }
    )

    pricing = resolver.resolve(
        family_code="FYBROC",
        configuration={},
    )

    assert pricing.total_amount == ZERO
    assert (
        pricing.known_amount
        == Decimal("4854")
    )
    assert (
        pricing.aggregate_status
        == "call_for_price"
    )

    # Legacy BASE_PUMP projection is unchanged.
    assert (
        pricing.amount
        == Decimal("4854")
    )


def test_m0226_not_found_zeroes_total():
    resolver, _ = service(
        {
            "BASE_PUMP": result(
                "BASE_PUMP",
                amount="4854",
                status="found",
            ),
            "SEAL": result(
                "SEAL",
                amount="0",
                status="not_found",
                version_id=None,
                version_code=None,
            ),
        }
    )

    pricing = resolver.resolve(
        family_code="FYBROC",
        configuration={},
    )

    assert pricing.total_amount == ZERO
    assert (
        pricing.known_amount
        == Decimal("4854")
    )
    assert (
        pricing.aggregate_status
        == "not_found"
    )


def test_m0226_error_has_highest_precedence():
    resolver, _ = service(
        {
            "BASE_PUMP": result(
                "BASE_PUMP",
                amount="4854",
                status="found",
            ),
            "SEAL": result(
                "SEAL",
                amount="0",
                status="error",
                version_id=None,
                version_code=None,
            ),
        }
    )

    pricing = resolver.resolve(
        family_code="FYBROC",
        configuration={},
    )

    assert pricing.total_amount == ZERO
    assert (
        pricing.aggregate_status
        == "error"
    )


def test_m0226_mixed_publications_are_not_totaled():
    resolver, _ = service(
        {
            "BASE_PUMP": result(
                "BASE_PUMP",
                amount="4854",
                status="found",
                version_id=5,
                version_code=(
                    "FYBROC-CONFIG-20260807-V3"
                ),
            ),
            "SEAL": result(
                "SEAL",
                amount="749",
                status="found",
                version_id=99,
                version_code="WRONG",
            ),
        }
    )

    pricing = resolver.resolve(
        family_code="FYBROC",
        configuration={},
    )

    assert pricing.total_amount == ZERO
    assert (
        pricing.known_amount
        == Decimal("5603")
    )
    assert (
        pricing.aggregate_status
        == "error"
    )
    assert (
        pricing.price_book_version_id_aggregate
        is None
    )


def test_m0226_component_order_is_stable():
    resolver, _ = service(
        {
            "BASE_PUMP": result(
                "BASE_PUMP",
                amount="4854",
                status="found",
            ),
            "SEAL": result(
                "SEAL",
                amount="749",
                status="found",
            ),
        }
    )

    pricing = resolver.resolve(
        family_code="FYBROC",
        configuration={},
    )

    assert [
        item.component_code
        for item in pricing.components
    ] == [
        "BASE_PUMP",
        "SEAL",
    ]

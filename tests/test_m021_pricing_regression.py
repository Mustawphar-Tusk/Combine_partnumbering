from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.api.presenters import (
    present_persisted_configuration,
)
from src.compiler.pricing_metadata_compiler import (
    compile_base_pump_pricing,
)
from src.pricing_engine import (
    PricingCondition,
    PricingMetadataError,
    PricingResult,
    PricingRule,
    PricingService,
)
from src.pricing_engine.non_blocking import (
    NonBlockingPricingService,
)


ROOT = Path(__file__).resolve().parents[1]


class FakePricingRepository:
    def __init__(
        self,
        rules: tuple[PricingRule, ...],
    ) -> None:
        self.rules = rules

    def get_current_rules(
        self,
        *,
        family_code: str,
        price_book_code: str,
        component_code: str,
        series_code: str | None,
    ) -> tuple[PricingRule, ...]:
        del family_code
        del price_book_code
        del component_code

        return tuple(
            rule
            for rule in self.rules
            if (
                rule.series_code == series_code
                or rule.series_code is None
            )
        )


def make_rule(
    *,
    price_rule_id: int,
    amount: str,
    status: str,
    size: str,
    material: str,
) -> PricingRule:
    return PricingRule(
        price_book_code="FYBROC_STANDARD",
        price_book_version_id=4,
        version_code="FYBROC-BASE-20260807-V2",
        currency_code="USD",
        price_rule_id=price_rule_id,
        rule_code=f"RULE-{price_rule_id}",
        component_code="BASE_PUMP",
        series_code="1530 (ANSI)",
        priority=100,
        amount=Decimal(amount),
        pricing_status=status,
        conditions=(
            PricingCondition(
                sequence_no=1,
                field_code="SIZE",
                comparison_operator="EQ",
                comparison_value=size,
            ),
            PricingCondition(
                sequence_no=2,
                field_code="PUMP_MATERIAL",
                comparison_operator="EQ",
                comparison_value=material,
            ),
        ),
        source_size_value="1X1.5X6",
        source_option_value="VR-1 (Standard)",
        source_price_value=amount,
        source_worksheet="Pricebook",
        source_table="Table49",
        source_cell="U6",
    )


def test_m021_compiler_baseline() -> None:
    report = compile_base_pump_pricing(
        ROOT
        / "workbooks"
        / "Fybroc"
        / "Price Estimator-Fybroc.xlsm",
        ROOT
        / "config"
        / "pricing_profiles"
        / "fybroc_base_pump.json",
    )

    assert report.issue_count == 0
    assert report.candidate_count == 436

    found = [
        row
        for row in report.candidates
        if (
            row.source_series_code == "1530"
            and row.series_code == "1530 (ANSI)"
            and row.size_value == "1x1.5x6"
            and row.option_value == "VR-1*"
        )
    ]

    assert len(found) == 1

    row = found[0]

    assert row.amount == 4854.0
    assert row.pricing_status == "found"
    assert row.source_option_value == (
        "VR-1 (Standard)"
    )
    assert row.source_cell == "U6"

    call_for_price = [
        row
        for row in report.candidates
        if row.pricing_status == "call_for_price"
    ]

    assert len(call_for_price) == 15

    series_3000 = [
        row
        for row in report.candidates
        if row.source_series_code == "3000"
    ]

    assert len(series_3000) == 18

    assert {
        row.series_code
        for row in series_3000
    } == {"3000"}

    cfp_3000 = [
        row
        for row in series_3000
        if (
            row.size_value == "6x8x11"
            and row.option_value == "VR-1*"
        )
    ]

    assert len(cfp_3000) == 1
    assert cfp_3000[0].amount is None
    assert (
        cfp_3000[0].pricing_status
        == "call_for_price"
    )


def test_m021_resolver_found() -> None:
    service = PricingService(
        FakePricingRepository(
            (
                make_rule(
                    price_rule_id=655,
                    amount="4854",
                    status="found",
                    size="1x1.5x6",
                    material="VR-1*",
                ),
            )
        )
    )

    result = service.resolve(
        family_code="FYBROC",
        configuration={
            "SERIES": "1530 (ANSI)",
            "SIZE": "1x1.5x6",
            "PUMP_MATERIAL": "VR-1*",
        },
    )

    assert result.status == "found"
    assert result.amount == Decimal("4854")
    assert result.currency_code == "USD"
    assert result.price_book_version_id == 4
    assert (
        result.version_code
        == "FYBROC-BASE-20260807-V2"
    )
    assert result.price_rule_id == 655


def test_m021_resolver_call_for_price() -> None:
    rule = make_rule(
        price_rule_id=700,
        amount="0",
        status="call_for_price",
        size="6x8x11",
        material="VR-1*",
    )

    rule = PricingRule(
        **{
            **rule.__dict__,
            "series_code": "3000",
        }
    )

    service = PricingService(
        FakePricingRepository((rule,))
    )

    result = service.resolve(
        family_code="FYBROC",
        configuration={
            "SERIES": "3000",
            "SIZE": "6x8x11",
            "PUMP_MATERIAL": "VR-1*",
        },
    )

    assert result.status == "call_for_price"
    assert result.amount == Decimal("0")
    assert result.currency_code == "USD"


def test_m021_resolver_not_found() -> None:
    service = PricingService(
        FakePricingRepository(
            (
                make_rule(
                    price_rule_id=655,
                    amount="4854",
                    status="found",
                    size="1x1.5x6",
                    material="VR-1*",
                ),
            )
        )
    )

    result = service.resolve(
        family_code="FYBROC",
        configuration={
            "SERIES": "1530 (ANSI)",
            "SIZE": "1x1.5x6",
            "PUMP_MATERIAL":
                "VR-1A BPO/DMA",
        },
    )

    assert result.status == "not_found"
    assert result.amount == Decimal("0")
    assert result.currency_code == "USD"
    assert result.price_book_version_id == 4
    assert result.price_rule_id is None


def test_m021_resolver_rejects_ambiguous_match() -> None:
    rules = (
        make_rule(
            price_rule_id=655,
            amount="4854",
            status="found",
            size="1x1.5x6",
            material="VR-1*",
        ),
        make_rule(
            price_rule_id=656,
            amount="4854",
            status="found",
            size="1x1.5x6",
            material="VR-1*",
        ),
    )

    service = PricingService(
        FakePricingRepository(rules)
    )

    with pytest.raises(
        PricingMetadataError,
        match="multiple rules matched",
    ):
        service.resolve(
            family_code="FYBROC",
            configuration={
                "SERIES": "1530 (ANSI)",
                "SIZE": "1x1.5x6",
                "PUMP_MATERIAL": "VR-1*",
            },
        )


def test_m021_pricing_failure_is_non_blocking() -> None:
    class BrokenPricingService:
        def resolve(self, **kwargs):
            del kwargs
            raise RuntimeError(
                "Simulated pricing failure."
            )

    service = NonBlockingPricingService(
        BrokenPricingService()
    )

    result = service.resolve(
        family_code="FYBROC",
        configuration={
            "SERIES": "1530 (ANSI)",
        },
    )

    assert result.status == "error"
    assert result.amount == Decimal("0")
    assert result.price_rule_id is None


def test_m021_finalize_presenter_includes_pricing() -> None:
    completed = SimpleNamespace(
        selections={
            "SERIES": "1530 (ANSI)",
            "SIZE": "1x1.5x6",
            "PUMP_MATERIAL": "VR-1*",
        },
        identifier_result=SimpleNamespace(
            segments=tuple(range(10))
        ),
    )

    persisted = SimpleNamespace(
        configured_product_registry_id=5,
        was_created=False,
        configuration_signature="signature",
        part_number=(
            "F1530-B-1-1-AA-"
            "2SIY-0Y-1Q-025-XXX-T00"
        ),
        sku=(
            "F1530-V1-"
            "B11AA2SIY0Y1Q025XXXT00"
        ),
        request_count=2,
        runtime_revision=(
            "publication:1;"
            "series-batch:2;"
            "combination-batch:2;"
            "dependency-batch:1"
        ),
        metadata_publication_id=1,
        series_batch_id=2,
        combination_batch_id=2,
        dependency_batch_id=1,
        created_at=datetime(
            2026,
            8,
            7,
            19,
            20,
            58,
        ),
        last_requested_at=datetime(
            2026,
            8,
            7,
            19,
            43,
            43,
        ),
    )

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

    response = (
        present_persisted_configuration(
            SimpleNamespace(
                completed_configuration=completed,
                persisted_product=persisted,
            ),
            pricing=pricing,
        )
    )

    assert response.price == Decimal("4854")
    assert response.pricing_status == "found"
    assert response.currency_code == "USD"

    assert (
        response.pricing_version
        == "FYBROC-BASE-20260807-V2"
    )

    assert response.price_book_version_id == 4
    assert response.price_rule_id == 655

    assert (
        response.configured_product_registry_id
        == 5
    )

    assert response.was_created is False
    assert response.selection_count == 3
    assert response.segment_count == 10

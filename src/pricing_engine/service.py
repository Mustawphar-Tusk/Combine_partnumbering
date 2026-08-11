from __future__ import annotations

from decimal import Decimal
from typing import Mapping, Protocol

from src.pricing_engine.models import (
    PricingResult,
    PricingRule,
)


ZERO = Decimal("0")


class PricingMetadataError(
    RuntimeError
):
    pass


class PricingRepository(Protocol):
    def get_current_rules(
        self,
        *,
        family_code: str,
        price_book_code: str,
        component_code: str,
        series_code: str | None,
    ) -> tuple[PricingRule, ...]:
        ...


def _normalize_field_code(
    value: str,
) -> str:
    return value.strip().upper()


def _normalize_value(
    value: object,
) -> str:
    return str(
        value
    ).strip().casefold()


class PricingService:
    def __init__(
        self,
        repository: PricingRepository,
    ) -> None:
        self._repository = repository

    def resolve(
        self,
        *,
        family_code: str,
        configuration: Mapping[
            str,
            object,
        ],
        component_code: str = "BASE_PUMP",
        price_book_code: str | None = None,
    ) -> PricingResult:

        family_code = (
            family_code
            .strip()
            .upper()
        )

        component_code = (
            component_code
            .strip()
            .upper()
        )

        canonical_configuration = {
            _normalize_field_code(key):
                value
            for key, value
            in configuration.items()
        }

        series_value = (
            canonical_configuration.get(
                "SERIES"
            )
        )

        series_code = (
            None
            if series_value is None
            else str(
                series_value
            ).strip()
        )

        if price_book_code is None:
            price_book_code = (
                f"{family_code}_STANDARD"
            )

        rules = (
            self._repository
            .get_current_rules(
                family_code=family_code,
                price_book_code=(
                    price_book_code
                ),
                component_code=(
                    component_code
                ),
                series_code=series_code,
            )
        )

        if not rules:
            return PricingResult(
                amount=ZERO,
                status="not_found",
                currency_code=None,
                price_book_code=(
                    price_book_code
                ),
                price_book_version_id=None,
                version_code=None,
                price_rule_id=None,
                component_code=(
                    component_code
                ),
            )

        versions = {
            (
                rule.price_book_version_id,
                rule.version_code,
                rule.currency_code,
            )
            for rule in rules
        }

        if len(versions) != 1:
            raise PricingMetadataError(
                "Multiple current pricing "
                "versions were returned for "
                "the same price book."
            )

        (
            price_book_version_id,
            version_code,
            currency_code,
        ) = next(iter(versions))

        matching_rules: list[
            PricingRule
        ] = []

        for rule in rules:
            matched = True

            for condition in (
                rule.conditions
            ):
                operator = (
                    condition
                    .comparison_operator
                    .strip()
                    .upper()
                )

                if operator != "EQ":
                    raise PricingMetadataError(
                        "Unsupported pricing "
                        f"operator {operator!r} "
                        f"on rule "
                        f"{rule.price_rule_id}."
                    )

                field_code = (
                    _normalize_field_code(
                        condition.field_code
                    )
                )

                actual_value = (
                    canonical_configuration
                    .get(field_code)
                )

                if actual_value is None:
                    matched = False
                    break

                expected_value = (
                    condition
                    .comparison_value
                )

                if expected_value is None:
                    matched = False
                    break

                if (
                    _normalize_value(
                        actual_value
                    )
                    !=
                    _normalize_value(
                        expected_value
                    )
                ):
                    matched = False
                    break

            if matched:
                matching_rules.append(
                    rule
                )

        if not matching_rules:
            return PricingResult(
                amount=ZERO,
                status="not_found",
                currency_code=(
                    currency_code
                ),
                price_book_code=(
                    price_book_code
                ),
                price_book_version_id=(
                    price_book_version_id
                ),
                version_code=(
                    version_code
                ),
                price_rule_id=None,
                component_code=(
                    component_code
                ),
            )

        if len(matching_rules) > 1:
            ids = [
                rule.price_rule_id
                for rule
                in matching_rules
            ]

            raise PricingMetadataError(
                "Ambiguous pricing metadata: "
                "multiple rules matched the "
                f"configuration: {ids}"
            )

        rule = matching_rules[0]

        if (
            rule.pricing_status
            == "found"
        ):
            amount = rule.amount

        elif (
            rule.pricing_status
            == "call_for_price"
        ):
            amount = ZERO

        else:
            raise PricingMetadataError(
                "Unsupported runtime pricing "
                f"status "
                f"{rule.pricing_status!r}."
            )

        return PricingResult(
            amount=amount,
            status=rule.pricing_status,
            currency_code=(
                rule.currency_code
            ),
            price_book_code=(
                rule.price_book_code
            ),
            price_book_version_id=(
                rule.price_book_version_id
            ),
            version_code=(
                rule.version_code
            ),
            price_rule_id=(
                rule.price_rule_id
            ),
            component_code=(
                rule.component_code
            ),
            source_worksheet=(
                rule.source_worksheet
            ),
            source_table=(
                rule.source_table
            ),
            source_cell=(
                rule.source_cell
            ),
        )

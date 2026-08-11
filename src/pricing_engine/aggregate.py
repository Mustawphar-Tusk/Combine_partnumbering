from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping

from src.pricing_engine.models import (
    PricingResult,
)


ZERO = Decimal("0")


@dataclass(frozen=True)
class ConfigurationPricingResult:
    total_amount: Decimal
    known_amount: Decimal
    aggregate_status: str

    currency_code_aggregate: str | None
    price_book_code_aggregate: str | None
    price_book_version_id_aggregate: int | None
    version_code_aggregate: str | None

    components: tuple[
        PricingResult,
        ...
    ]

    legacy_component_code: str

    @property
    def legacy_component(
        self,
    ) -> PricingResult | None:
        for component in (
            self.components
        ):
            if (
                component.component_code
                == self.legacy_component_code
            ):
                return component

        return None

    # ----------------------------------------------------------
    # Backward-compatibility projection.
    #
    # M021 exposed a single PricingResult through the API.
    # These properties deliberately continue to project the
    # configured legacy component (BASE_PUMP for FYBROC) so the
    # existing top-level API pricing fields do not silently
    # change meaning during M022.6.
    # ----------------------------------------------------------

    @property
    def amount(self) -> Decimal:
        component = (
            self.legacy_component
        )

        if component is None:
            return ZERO

        return component.amount

    @property
    def status(self) -> str:
        component = (
            self.legacy_component
        )

        if component is None:
            return "not_found"

        return component.status

    @property
    def currency_code(
        self,
    ) -> str | None:
        component = (
            self.legacy_component
        )

        if component is None:
            return (
                self.currency_code_aggregate
            )

        return component.currency_code

    @property
    def price_book_code(
        self,
    ) -> str | None:
        component = (
            self.legacy_component
        )

        if component is None:
            return (
                self.price_book_code_aggregate
            )

        return component.price_book_code

    @property
    def price_book_version_id(
        self,
    ) -> int | None:
        component = (
            self.legacy_component
        )

        if component is None:
            return (
                self
                .price_book_version_id_aggregate
            )

        return (
            component
            .price_book_version_id
        )

    @property
    def version_code(
        self,
    ) -> str | None:
        component = (
            self.legacy_component
        )

        if component is None:
            return (
                self.version_code_aggregate
            )

        return component.version_code

    @property
    def price_rule_id(
        self,
    ) -> int | None:
        component = (
            self.legacy_component
        )

        if component is None:
            return None

        return component.price_rule_id

    @property
    def component_code(
        self,
    ) -> str:
        return (
            self.legacy_component_code
        )

    @property
    def source_worksheet(
        self,
    ) -> str | None:
        component = (
            self.legacy_component
        )

        return (
            None
            if component is None
            else component.source_worksheet
        )

    @property
    def source_table(
        self,
    ) -> str | None:
        component = (
            self.legacy_component
        )

        return (
            None
            if component is None
            else component.source_table
        )

    @property
    def source_cell(
        self,
    ) -> str | None:
        component = (
            self.legacy_component
        )

        return (
            None
            if component is None
            else component.source_cell
        )


def _single_or_none(
    values,
    *,
    label: str,
):
    non_null = {
        value
        for value in values
        if value is not None
    }

    if len(non_null) > 1:
        raise RuntimeError(
            "Resolved pricing components do not "
            f"share one {label}: "
            + ", ".join(
                sorted(
                    str(value)
                    for value
                    in non_null
                )
            )
        )

    if not non_null:
        return None

    return next(
        iter(non_null)
    )


def _aggregate_status(
    components: tuple[
        PricingResult,
        ...
    ],
) -> str:
    statuses = {
        component.status
        for component
        in components
    }

    if "error" in statuses:
        return "error"

    if "not_found" in statuses:
        return "not_found"

    if "call_for_price" in statuses:
        return "call_for_price"

    if statuses == {
        "found"
    }:
        return "found"

    return "error"


class ConfigurationPricingService:
    """
    Resolve all pricing components configured for a family and
    return both a component breakdown and a safe aggregate.

    This service is intentionally family-agnostic. Component
    membership comes from the runtime pricing profile.
    """

    def __init__(
        self,
        component_service,
        *,
        component_codes: tuple[
            str,
            ...
        ],
        legacy_component_code: str,
        default_price_book_code:
            str | None = None,
    ) -> None:
        normalized_components = tuple(
            str(code).strip().upper()
            for code in component_codes
            if str(code).strip()
        )

        if not normalized_components:
            raise ValueError(
                "At least one pricing component "
                "is required."
            )

        if len(
            normalized_components
        ) != len(
            set(
                normalized_components
            )
        ):
            raise ValueError(
                "Pricing component codes "
                "must be unique."
            )

        legacy = (
            legacy_component_code
            .strip()
            .upper()
        )

        if (
            legacy
            not in normalized_components
        ):
            raise ValueError(
                "Legacy pricing component must "
                "be included in component_codes."
            )

        self._component_service = (
            component_service
        )
        self._component_codes = (
            normalized_components
        )
        self._legacy_component_code = (
            legacy
        )
        self._default_price_book_code = (
            default_price_book_code
        )

    @property
    def component_codes(
        self,
    ) -> tuple[str, ...]:
        return self._component_codes

    def resolve(
        self,
        *,
        family_code: str,
        configuration: Mapping[
            str,
            object,
        ],
        price_book_code:
            str | None = None,
    ) -> ConfigurationPricingResult:
        effective_price_book = (
            price_book_code
            or self._default_price_book_code
        )

        components = tuple(
            self._component_service.resolve(
                family_code=family_code,
                configuration=configuration,
                component_code=component_code,
                price_book_code=(
                    effective_price_book
                ),
            )
            for component_code
            in self._component_codes
        )

        status = _aggregate_status(
            components
        )

        known_amount = sum(
            (
                component.amount
                for component
                in components
                if component.status
                == "found"
            ),
            ZERO,
        )

        total_amount = (
            known_amount
            if status == "found"
            else ZERO
        )

        try:
            currency_code = (
                _single_or_none(
                    (
                        component.currency_code
                        for component
                        in components
                    ),
                    label="currency",
                )
            )

            price_book_code_value = (
                _single_or_none(
                    (
                        component.price_book_code
                        for component
                        in components
                    ),
                    label="price book",
                )
            )

            price_book_version_id = (
                _single_or_none(
                    (
                        component
                        .price_book_version_id
                        for component
                        in components
                    ),
                    label=(
                        "price-book version ID"
                    ),
                )
            )

            version_code = (
                _single_or_none(
                    (
                        component.version_code
                        for component
                        in components
                    ),
                    label=(
                        "price-book version code"
                    ),
                )
            )

        except RuntimeError:
            # A mixed publication is unsafe to total.
            status = "error"
            total_amount = ZERO

            currency_code = None
            price_book_code_value = None
            price_book_version_id = None
            version_code = None

        return ConfigurationPricingResult(
            total_amount=(
                total_amount
            ),
            known_amount=(
                known_amount
            ),
            aggregate_status=(
                status
            ),
            currency_code_aggregate=(
                currency_code
            ),
            price_book_code_aggregate=(
                price_book_code_value
            ),
            price_book_version_id_aggregate=(
                price_book_version_id
            ),
            version_code_aggregate=(
                version_code
            ),
            components=components,
            legacy_component_code=(
                self._legacy_component_code
            ),
        )

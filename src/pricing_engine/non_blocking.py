from __future__ import annotations

import logging
from decimal import Decimal

from src.pricing_engine.models import (
    PricingResult,
)


logger = logging.getLogger(__name__)


class NonBlockingPricingService:
    """
    API-facing pricing boundary.

    Pricing failure must never invalidate an already
    completed and persisted allowable configuration.
    """

    def __init__(
        self,
        inner_service,
    ) -> None:
        self._inner_service = inner_service

    def resolve(
        self,
        *,
        family_code: str,
        configuration,
        component_code: str = "BASE_PUMP",
        price_book_code: str | None = None,
    ) -> PricingResult:

        try:
            return self._inner_service.resolve(
                family_code=family_code,
                configuration=configuration,
                component_code=component_code,
                price_book_code=price_book_code,
            )

        except Exception:
            logger.exception(
                "Pricing resolution failed for "
                "family=%s component=%s.",
                family_code,
                component_code,
            )

            return PricingResult(
                amount=Decimal("0"),
                status="error",
                currency_code=None,
                price_book_code=price_book_code,
                price_book_version_id=None,
                version_code=None,
                price_rule_id=None,
                component_code=component_code,
            )

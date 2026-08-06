from decimal import Decimal

from src.models.configured_product import (
    ConfiguredProductRequest,
    ConfiguredProductResponse,
    PriceResult,
    PricingStatus,
)
from src.services.signature_service import canonicalize, create_signature


class ConfiguredProductService:
    def __init__(self, repository) -> None:
        self.repository = repository

    def get_or_create(
        self,
        request: ConfiguredProductRequest,
    ) -> ConfiguredProductResponse:
        validation_messages = self.repository.validate(request)

        if validation_messages:
            return ConfiguredProductResponse(
                valid=False,
                existing_configuration=False,
                price=PriceResult(
                    unit_price=Decimal("0"),
                    extended_price=Decimal("0"),
                    currency_code=request.currency_code,
                    status=PricingStatus.ERROR,
                    message="Configuration validation failed.",
                    matched_rule_ids=[],
                ),
                validation_messages=validation_messages,
            )

        canonical_json = canonicalize(request)
        signature = create_signature(canonical_json)

        existing = self.repository.find_product(signature)
        existing_configuration = existing is not None

        product = existing or self.repository.create_product(
            request,
            canonical_json,
            signature,
        )

        price_match = self.repository.find_price(request)

        if price_match is None:
            unit_price = Decimal("0")
            pricing_status = PricingStatus.NOT_FOUND
            pricing_message = (
                "No matching active price was found; price returned as 0."
            )
            matched_rule_ids: list[int] = []
        else:
            unit_price = Decimal(price_match.unit_price)
            pricing_status = PricingStatus.MATCHED
            pricing_message = "Matching price rules were applied."
            matched_rule_ids = list(
                getattr(price_match, "rule_ids", ())
            )

        return ConfiguredProductResponse(
            valid=True,
            existing_configuration=existing_configuration,
            part_number=product.part_number,
            sku=product.sku,
            configuration_signature=signature,
            price=PriceResult(
                unit_price=unit_price,
                extended_price=unit_price * request.quantity,
                currency_code=request.currency_code,
                status=pricing_status,
                message=pricing_message,
                matched_rule_ids=matched_rule_ids,
            ),
            validation_messages=[],
        )
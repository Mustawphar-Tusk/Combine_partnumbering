from decimal import Decimal

from src.models.configured_product import ConfiguredProductRequest, PricingStatus
from src.repositories.memory_repository import MemoryConfigurationRepository
from src.services.configured_product_service import ConfiguredProductService


def request() -> ConfiguredProductRequest:
    return ConfiguredProductRequest.model_validate(
        {
            "pump_family_code": "DEAN",
            "series_code": "DS",
            "quantity": "2",
            "selections": [
                {"sequence": 1, "field_code": "SERIES", "option_code": "DS", "hex_code": "01"},
                {"sequence": 2, "field_code": "SIZE", "option_code": "3X4", "hex_code": "A2"},
            ],
        }
    )


def test_missing_price_returns_zero_and_still_generates_identifiers() -> None:
    repo = MemoryConfigurationRepository()
    result = ConfiguredProductService(repo).get_or_create(request())

    assert result.valid is True
    assert result.part_number is not None
    assert result.sku is not None
    assert result.price.unit_price == Decimal("0")
    assert result.price.extended_price == Decimal("0")
    assert result.price.status is PricingStatus.NOT_FOUND


def test_matched_price_returns_extended_price() -> None:
    repo = MemoryConfigurationRepository()
    repo.seed_price("DEAN", "DS", Decimal("1250.50"), (101,))

    result = ConfiguredProductService(repo).get_or_create(request())

    assert result.price.unit_price == Decimal("1250.50")
    assert result.price.extended_price == Decimal("2501.00")
    assert result.price.status is PricingStatus.MATCHED
    assert result.price.matched_rule_ids == [101]


def test_repeated_configuration_reuses_part_number_and_sku() -> None:
    repo = MemoryConfigurationRepository()
    service = ConfiguredProductService(repo)

    first = service.get_or_create(request())
    second = service.get_or_create(request())

    assert first.existing_configuration is False
    assert second.existing_configuration is True
    assert first.part_number == second.part_number
    assert first.sku == second.sku

from __future__ import annotations

from decimal import Decimal

from src.models.configured_product import ConfiguredProductRequest
from src.repositories.contracts import PriceMatch, ProductRecord


class MemoryConfigurationRepository:
    """Development repository used only to run the API before SQL is connected.

    Production behavior will use the same service contract with SQL Server.
    """

    def __init__(self) -> None:
        self.products: dict[str, ProductRecord] = {}
        self.prices: dict[tuple[str, str | None], PriceMatch] = {}
        self.valid_families = {"DEAN", "FYBROC"}

    def validate(self, request: ConfiguredProductRequest) -> list[str]:
        errors: list[str] = []
        if request.pump_family_code not in self.valid_families:
            errors.append(f"Unknown or inactive pump family: {request.pump_family_code}")
        return errors

    def find_product(self, signature: str) -> ProductRecord | None:
        return self.products.get(signature)

    def create_product(
        self,
        request: ConfiguredProductRequest,
        canonical_json: str,
        signature: str,
    ) -> ProductRecord:
        sequence = len(self.products) + 1
        prefix = request.pump_family_code[:3]
        product = ProductRecord(
            part_number=f"{prefix}-{sequence:08d}",
            sku=f"SKU-{sequence:08d}",
        )
        self.products[signature] = product
        return product

    def find_price(self, request: ConfiguredProductRequest) -> PriceMatch | None:
        return self.prices.get((request.pump_family_code, request.series_code))

    def seed_price(
        self,
        family: str,
        series: str | None,
        unit_price: Decimal,
        rule_ids: tuple[int, ...] = (),
    ) -> None:
        self.prices[(family.upper(), series.upper() if series else None)] = PriceMatch(
            unit_price=unit_price,
            rule_ids=rule_ids,
        )

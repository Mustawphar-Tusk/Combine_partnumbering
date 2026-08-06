from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from src.models.configured_product import ConfiguredProductRequest


@dataclass(frozen=True)
class ProductRecord:
    part_number: str
    sku: str


@dataclass(frozen=True)
class PriceMatch:
    unit_price: Decimal
    rule_ids: tuple[int, ...] = ()


class ConfigurationRepository(Protocol):
    def validate(
        self,
        request: ConfiguredProductRequest,
    ) -> list[str]:
        ...

    def find_price(
        self,
        request: ConfiguredProductRequest,
    ) -> PriceMatch | None:
        ...

    def find_product(
        self,
        signature: str,
    ) -> ProductRecord | None:
        ...

    def create_product(
        self,
        request: ConfiguredProductRequest,
        canonical_json: str,
        signature: str,
    ) -> ProductRecord:
        ...

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field

class PricingStatus(str, Enum):
    MATCHED = "matched"
    NOT_FOUND = "not_found"
    PARTIAL = "partial"
    ERROR = "error"

class ConfigurationSelection(BaseModel):
    sequence: int = Field(gt=0)
    field_code: str
    option_code: str
    hex_code: str | None = None

class ConfiguredProductRequest(BaseModel):
    pump_family_code: str
    series_code: str | None = None
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    currency_code: str = "USD"
    requested_by: str | None = None
    selections: list[ConfigurationSelection]

class PriceResult(BaseModel):
    unit_price: Decimal
    extended_price: Decimal
    currency_code: str
    status: PricingStatus
    message: str
    matched_rule_ids: list[int] = Field(default_factory=list)

class ConfiguredProductResponse(BaseModel):
    valid: bool
    existing_configuration: bool
    part_number: str | None = None
    sku: str | None = None
    configuration_signature: str | None = None
    price: PriceResult
    validation_messages: list[str] = []


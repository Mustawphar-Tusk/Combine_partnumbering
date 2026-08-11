from __future__ import annotations

from decimal import Decimal

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(
        word[:1].upper() + word[1:]
        for word in rest
    )


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )


class StartConfigurationRequest(ApiModel):
    """An intentionally empty request body."""


class AdvanceConfigurationRequest(ApiModel):
    state_token: str = Field(
        min_length=20,
        max_length=20000,
    )
    option_token: str = Field(
        min_length=20,
        max_length=20000,
    )


class FinalizeConfigurationRequest(ApiModel):
    state_token: str = Field(
        min_length=20,
        max_length=20000,
    )


class AllowableOptionResponse(ApiModel):
    field_code: str
    display_value: str
    option_token: str


class NavigationResponse(ApiModel):
    family_code: str
    runtime_revision: str
    state_token: str
    complete: bool
    next_field_code: str | None
    selection_count: int
    options: list[AllowableOptionResponse]


class PricingComponentResponse(ApiModel):
    component_code: str
    amount: Decimal
    status: str
    currency_code: str | None = None
    price_book_code: str | None = None
    price_book_version_id: int | None = None
    version_code: str | None = None
    price_rule_id: int | None = None
    source_worksheet: str | None = None
    source_table: str | None = None
    source_cell: str | None = None


class ConfigurationPricingResponse(ApiModel):
    total_amount: Decimal
    known_amount: Decimal
    status: str
    currency_code: str | None = None
    price_book_code: str | None = None
    price_book_version_id: int | None = None
    version_code: str | None = None
    components: list[
        PricingComponentResponse
    ]


class FinalizeConfigurationResponse(ApiModel):
    configured_product_registry_id: int
    was_created: bool
    configuration_signature: str
    part_number: str
    sku: str

    price: Decimal = Decimal("0")
    pricing_status: str = "not_found"
    currency_code: str | None = None
    pricing_version: str | None = None
    price_book_version_id: int | None = None
    price_rule_id: int | None = None

    request_count: int
    runtime_revision: str
    metadata_publication_id: int
    series_batch_id: int | None
    combination_batch_id: int | None
    dependency_batch_id: int | None
    selection_count: int
    segment_count: int
    created_at: datetime
    last_requested_at: datetime
    pricing: ConfigurationPricingResponse | None = None


class HealthResponse(ApiModel):
    status: str
    service: str
    version: str
    environment: str
    configured_families: list[str] = Field(
        default_factory=list
    )


class ErrorBody(ApiModel):
    code: str
    message: str


class ErrorResponse(ApiModel):
    error: ErrorBody

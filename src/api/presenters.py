from __future__ import annotations

from src.api.models import (
    AllowableOptionResponse,
    FinalizeConfigurationResponse,
    NavigationResponse,
)


def present_navigation(
    response,
) -> NavigationResponse:
    return NavigationResponse(
        family_code=response.family_code,
        runtime_revision=response.runtime_revision,
        state_token=response.state_token,
        complete=response.complete,
        next_field_code=response.next_field_code,
        selection_count=response.selection_count,
        options=[
            AllowableOptionResponse(
                field_code=option.field_code,
                display_value=option.display_value,
                option_token=option.option_token,
            )
            for option in response.options
        ],
    )


def _present_pricing_component(
    component,
):
    return {
        "component_code":
            component.component_code,
        "amount":
            component.amount,
        "status":
            component.status,
        "currency_code":
            component.currency_code,
        "price_book_code":
            component.price_book_code,
        "price_book_version_id":
            component.price_book_version_id,
        "version_code":
            component.version_code,
        "price_rule_id":
            component.price_rule_id,
        "source_worksheet":
            component.source_worksheet,
        "source_table":
            component.source_table,
        "source_cell":
            component.source_cell,
    }


def _present_configuration_pricing(
    pricing,
):
    """
    Present either:

    1. M022 aggregate ConfigurationPricingResult, or
    2. the historical M021 single-component PricingResult.

    Existing callers/tests remain backward compatible while the
    runtime migrates to aggregate pricing.
    """

    if hasattr(
        pricing,
        "components",
    ):
        return {
            "total_amount":
                pricing.total_amount,
            "known_amount":
                pricing.known_amount,
            "status":
                pricing.aggregate_status,
            "currency_code":
                pricing.currency_code_aggregate,
            "price_book_code":
                pricing.price_book_code_aggregate,
            "price_book_version_id":
                pricing.price_book_version_id_aggregate,
            "version_code":
                pricing.version_code_aggregate,
            "components": [
                _present_pricing_component(
                    component
                )
                for component
                in pricing.components
            ],
        }

    status = pricing.status

    known_amount = (
        pricing.amount
        if status == "found"
        else 0
    )

    total_amount = (
        pricing.amount
        if status == "found"
        else 0
    )

    return {
        "total_amount":
            total_amount,
        "known_amount":
            known_amount,
        "status":
            status,
        "currency_code":
            pricing.currency_code,
        "price_book_code":
            pricing.price_book_code,
        "price_book_version_id":
            pricing.price_book_version_id,
        "version_code":
            pricing.version_code,
        "components": [
            _present_pricing_component(
                pricing
            )
        ],
    }


def present_persisted_configuration(
    result,
    pricing=None,
) -> FinalizeConfigurationResponse:
    completed = result.completed_configuration
    persisted = result.persisted_product

    return FinalizeConfigurationResponse(
        configured_product_registry_id=(
            persisted.configured_product_registry_id
        ),
        was_created=persisted.was_created,
        configuration_signature=(
            persisted.configuration_signature
        ),
        part_number=persisted.part_number,
        sku=persisted.sku,

        price=(
            pricing.amount
            if pricing is not None
            else 0
        ),
        pricing_status=(
            pricing.status
            if pricing is not None
            else "not_found"
        ),
        currency_code=(
            pricing.currency_code
            if pricing is not None
            else None
        ),
        pricing_version=(
            pricing.version_code
            if pricing is not None
            else None
        ),
        price_book_version_id=(
            pricing.price_book_version_id
            if pricing is not None
            else None
        ),
        price_rule_id=(
            pricing.price_rule_id
            if pricing is not None
            else None
        ),

        request_count=persisted.request_count,
        runtime_revision=persisted.runtime_revision,
        metadata_publication_id=(
            persisted.metadata_publication_id
        ),
        series_batch_id=persisted.series_batch_id,
        combination_batch_id=(
            persisted.combination_batch_id
        ),
        dependency_batch_id=(
            persisted.dependency_batch_id
        ),
        selection_count=len(
            completed.selections
        ),
        segment_count=len(
            completed.identifier_result.segments
        ),
        created_at=persisted.created_at,
        last_requested_at=(
            persisted.last_requested_at
        ),
        pricing=(
            _present_configuration_pricing(
                pricing
            )
            if pricing is not None
            else None
        ),
    )

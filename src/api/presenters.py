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


def present_persisted_configuration(
    result,
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
    )

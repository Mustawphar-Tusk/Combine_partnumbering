from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

import pyodbc

from src.configuration_engine.complete_session import (
    CompletedConfiguration,
)


class ConfiguredProductPersistenceError(RuntimeError):
    """Raised when a completed configuration cannot be persisted."""


@dataclass(frozen=True)
class RuntimeRevisionParts:
    metadata_publication_id: int
    series_batch_id: int | None
    combination_batch_id: int | None
    dependency_batch_id: int | None


@dataclass(frozen=True)
class ConfiguredProductPersistencePayload:
    family_code: str
    configuration_signature: str
    part_number: str
    sku: str
    canonical_configuration_json: str
    selections_json: str
    segments_json: str
    runtime_revision: str
    metadata_publication_id: int
    series_batch_id: int | None
    combination_batch_id: int | None
    dependency_batch_id: int | None
    requested_by: str | None


@dataclass(frozen=True)
class PersistedConfiguredProduct:
    configured_product_registry_id: int
    configuration_signature: str
    part_number: str
    sku: str
    runtime_revision: str
    metadata_publication_id: int
    series_batch_id: int | None
    combination_batch_id: int | None
    dependency_batch_id: int | None
    created_at: datetime
    last_requested_at: datetime
    request_count: int
    was_created: bool


@dataclass(frozen=True)
class PersistedConfiguredProductCounts:
    registry_count: int
    selection_count: int
    segment_count: int
    audit_count: int


def parse_runtime_revision(
    runtime_revision: str,
) -> RuntimeRevisionParts:
    values = {
        key: int(value)
        for key, value in re.findall(
            r"([a-z-]+):(\d+)",
            runtime_revision,
        )
    }

    if "publication" not in values:
        raise ConfiguredProductPersistenceError(
            "Runtime revision does not contain publication:<id>."
        )

    return RuntimeRevisionParts(
        metadata_publication_id=values["publication"],
        series_batch_id=values.get("series-batch"),
        combination_batch_id=values.get(
            "combination-batch"
        ),
        dependency_batch_id=values.get(
            "dependency-batch"
        ),
    )


def _compact_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def build_persistence_payload(
    *,
    completed: CompletedConfiguration,
    field_order: Iterable[str],
    requested_by: str | None = None,
) -> ConfiguredProductPersistencePayload:
    result = completed.identifier_result
    revision = parse_runtime_revision(
        completed.runtime_revision
    )

    ordered_fields = tuple(field_order)
    missing = [
        field
        for field in ordered_fields
        if field not in completed.selections
    ]

    if missing:
        raise ConfiguredProductPersistenceError(
            "Completed configuration is missing ordered fields: "
            + ", ".join(missing)
        )

    unexpected = sorted(
        set(completed.selections) - set(ordered_fields)
    )

    if unexpected:
        raise ConfiguredProductPersistenceError(
            "Completed configuration contains unexpected fields: "
            + ", ".join(unexpected)
        )

    selection_rows = [
        {
            "selection_sequence": index,
            "field_code": field_code,
            "display_value": completed.selections[
                field_code
            ],
        }
        for index, field_code in enumerate(
            ordered_fields,
            start=1,
        )
    ]

    segment_rows = [
        {
            "segment_sequence": index,
            "segment_code": segment.segment_code,
            "segment_value": segment.segment_value,
            "resolution_type": segment.resolution_type,
            "source_id": segment.source_id,
            "source_ids_json": _compact_json(
                list(segment.source_ids)
            ),
        }
        for index, segment in enumerate(
            result.segments,
            start=1,
        )
    ]

    selections_json = _compact_json(selection_rows)
    segments_json = _compact_json(segment_rows)

    canonical = {
        "family_code": completed.family_code,
        "configuration_signature": (
            result.configuration_signature
        ),
        "part_number": result.part_number,
        "sku": result.sku,
        "runtime_revision": completed.runtime_revision,
        "selections": selection_rows,
        "segments": segment_rows,
    }

    return ConfiguredProductPersistencePayload(
        family_code=completed.family_code,
        configuration_signature=(
            result.configuration_signature
        ),
        part_number=result.part_number,
        sku=result.sku,
        canonical_configuration_json=_compact_json(
            canonical
        ),
        selections_json=selections_json,
        segments_json=segments_json,
        runtime_revision=completed.runtime_revision,
        metadata_publication_id=(
            revision.metadata_publication_id
        ),
        series_batch_id=revision.series_batch_id,
        combination_batch_id=(
            revision.combination_batch_id
        ),
        dependency_batch_id=(
            revision.dependency_batch_id
        ),
        requested_by=requested_by,
    )


class SqlConfiguredProductPersistenceRepository:
    def __init__(
        self,
        *,
        connection_string: str,
    ) -> None:
        self.connection_string = connection_string

    def persist(
        self,
        payload: ConfiguredProductPersistencePayload,
    ) -> PersistedConfiguredProduct:
        connection = pyodbc.connect(
            self.connection_string,
            autocommit=True,
        )

        try:
            row = connection.cursor().execute(
                """
                EXEC cfg.usp_PersistConfiguredProduct
                    @FamilyCode = ?,
                    @ConfigurationSignature = ?,
                    @PartNumber = ?,
                    @SKU = ?,
                    @CanonicalConfigurationJson = ?,
                    @SelectionsJson = ?,
                    @SegmentsJson = ?,
                    @RuntimeRevision = ?,
                    @MetadataPublicationId = ?,
                    @SeriesBatchId = ?,
                    @CombinationBatchId = ?,
                    @DependencyBatchId = ?,
                    @RequestedBy = ?;
                """,
                payload.family_code,
                payload.configuration_signature,
                payload.part_number,
                payload.sku,
                payload.canonical_configuration_json,
                payload.selections_json,
                payload.segments_json,
                payload.runtime_revision,
                payload.metadata_publication_id,
                payload.series_batch_id,
                payload.combination_batch_id,
                payload.dependency_batch_id,
                payload.requested_by,
            ).fetchone()

            if row is None:
                raise ConfiguredProductPersistenceError(
                    "Persistence procedure returned no result."
                )

            return PersistedConfiguredProduct(
                configured_product_registry_id=int(
                    row.ConfiguredProductRegistryId
                ),
                configuration_signature=str(
                    row.ConfigurationSignature
                ),
                part_number=str(row.PartNumber),
                sku=str(row.SKU),
                runtime_revision=str(row.RuntimeRevision),
                metadata_publication_id=int(
                    row.MetadataPublicationId
                ),
                series_batch_id=(
                    int(row.SeriesBatchId)
                    if row.SeriesBatchId is not None
                    else None
                ),
                combination_batch_id=(
                    int(row.CombinationBatchId)
                    if row.CombinationBatchId is not None
                    else None
                ),
                dependency_batch_id=(
                    int(row.DependencyBatchId)
                    if row.DependencyBatchId is not None
                    else None
                ),
                created_at=row.CreatedAt,
                last_requested_at=row.LastRequestedAt,
                request_count=int(row.RequestCount),
                was_created=bool(row.WasCreated),
            )

        finally:
            connection.close()

    def counts_for_signature(
        self,
        *,
        family_code: str,
        configuration_signature: str,
    ) -> PersistedConfiguredProductCounts:
        connection = pyodbc.connect(
            self.connection_string,
            autocommit=True,
        )

        try:
            row = connection.cursor().execute(
                """
                SELECT
                    COUNT(DISTINCT registry.
                        ConfiguredProductRegistryId)
                        AS RegistryCount,
                    COUNT(DISTINCT selection.
                        ConfiguredProductSelectionId)
                        AS SelectionCount,
                    COUNT(DISTINCT segment.
                        ConfiguredProductSegmentId)
                        AS SegmentCount,
                    COUNT(DISTINCT audit.
                        ConfiguredProductRequestAuditId)
                        AS AuditCount
                FROM cfg.ConfiguredProductRegistry AS registry
                INNER JOIN cfg.PumpFamily AS family
                    ON family.PumpFamilyId =
                       registry.PumpFamilyId
                LEFT JOIN cfg.ConfiguredProductSelection AS selection
                    ON selection.ConfiguredProductRegistryId =
                       registry.ConfiguredProductRegistryId
                LEFT JOIN cfg.ConfiguredProductSegment AS segment
                    ON segment.ConfiguredProductRegistryId =
                       registry.ConfiguredProductRegistryId
                LEFT JOIN cfg.ConfiguredProductRequestAudit AS audit
                    ON audit.ConfiguredProductRegistryId =
                       registry.ConfiguredProductRegistryId
                WHERE family.FamilyCode = ?
                  AND registry.ConfigurationSignature = ?;
                """,
                family_code,
                configuration_signature,
            ).fetchone()

            if row is None:
                return PersistedConfiguredProductCounts(
                    registry_count=0,
                    selection_count=0,
                    segment_count=0,
                    audit_count=0,
                )

            return PersistedConfiguredProductCounts(
                registry_count=int(row.RegistryCount),
                selection_count=int(row.SelectionCount),
                segment_count=int(row.SegmentCount),
                audit_count=int(row.AuditCount),
            )

        finally:
            connection.close()

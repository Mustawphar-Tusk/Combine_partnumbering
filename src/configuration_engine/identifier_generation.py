from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

import pyodbc


class IdentifierGenerationError(RuntimeError):
    """Raised when published metadata cannot resolve an identifier."""


@dataclass(frozen=True)
class ResolvedIdentifierSegment:
    segment_code: str
    segment_value: str
    source_id: int | None
    resolution_type: str
    source_ids: tuple[int, ...] = field(
        default_factory=tuple
    )


@dataclass(frozen=True)
class IdentifierGenerationResult:
    valid: bool
    part_number: str
    sku: str
    configuration_signature: str
    segments: tuple[ResolvedIdentifierSegment, ...]
    validation_messages: tuple[str, ...]
    metadata_trace: dict[str, Any]


@dataclass(frozen=True)
class IdentifierSegmentProfile:
    segment_code: str
    resolution_type: str
    field_code: str | None
    selection_fields: tuple[str, ...]
    source_field_code: str | None = None
    field_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class IdentifierGenerationProfile:
    family_code: str
    base_prefix: str
    series_field_code: str
    series_code_pattern: str
    sku_version: int
    part_separator: str
    segments: tuple[IdentifierSegmentProfile, ...]

    @classmethod
    def from_mapping(
        cls,
        value: dict[str, Any],
    ) -> "IdentifierGenerationProfile":
        return cls(
            family_code=str(
                value["family_code"]
            ).upper(),
            base_prefix=str(
                value["base_identifier"]["prefix"]
            ),
            series_field_code=str(
                value["base_identifier"][
                    "series_field_code"
                ]
            ).upper(),
            series_code_pattern=str(
                value["base_identifier"][
                    "series_code_pattern"
                ]
            ),
            sku_version=int(value["sku_version"]),
            part_separator=str(
                value.get("part_separator", "-")
            ),
            segments=tuple(
                IdentifierSegmentProfile(
                    segment_code=str(
                        row["segment_code"]
                    ).upper(),
                    resolution_type=str(
                        row["resolution_type"]
                    ).upper(),
                    field_code=(
                        str(row["field_code"]).upper()
                        if row.get("field_code")
                        else None
                    ),
                    selection_fields=tuple(
                        str(item).upper()
                        for item in row.get(
                            "selection_fields",
                            (),
                        )
                    ),
                    source_field_code=(
                        str(
                            row["source_field_code"]
                        ).upper()
                        if row.get(
                            "source_field_code"
                        )
                        else None
                    ),
                    field_codes=tuple(
                        str(item).upper()
                        for item in row.get(
                            "field_codes",
                            (),
                        )
                    ),
                )
                for row in value["segments"]
            ),
        )


class SqlMetadataIdentifierGenerator:
    def __init__(
        self,
        *,
        connection_string: str,
        profile: IdentifierGenerationProfile,
        metadata_publication_id: int,
        combination_batch_id: int | None = None,
    ) -> None:
        self.connection_string = connection_string
        self.profile = profile
        self.metadata_publication_id = (
            metadata_publication_id
        )
        self.combination_batch_id = (
            combination_batch_id
        )
        self.series_regex = re.compile(
            profile.series_code_pattern
        )

    def generate(
        self,
        selections: dict[str, str],
    ) -> IdentifierGenerationResult:
        connection = pyodbc.connect(
            self.connection_string,
            autocommit=True,
        )

        try:
            cursor = connection.cursor()
            family_id = self._family_id(cursor)
            batch_id = (
                self.combination_batch_id
                or self._combination_batch(cursor)
            )
            resolved: list[
                ResolvedIdentifierSegment
            ] = []

            for segment in self.profile.segments:
                if segment.resolution_type == "ATTRIBUTE":
                    resolved.append(
                        self._attribute(
                            cursor,
                            family_id,
                            segment,
                            selections,
                        )
                    )
                elif segment.resolution_type == (
                    "ATTRIBUTE_SEQUENCE"
                ):
                    resolved.append(
                        self._attribute_sequence(
                            cursor,
                            family_id,
                            segment,
                            selections,
                        )
                    )
                elif segment.resolution_type == "COMBINATION":
                    resolved.append(
                        self._combination(
                            cursor,
                            batch_id,
                            segment,
                            selections,
                        )
                    )
                else:
                    raise IdentifierGenerationError(
                        "Unsupported resolution type "
                        f"{segment.resolution_type}."
                    )

            base = self._base(selections)
            segment_values = [
                item.segment_value
                for item in resolved
            ]

            part_number = (
                base
                + self.profile.part_separator
                + self.profile.part_separator.join(
                    segment_values
                )
            )
            sku = (
                f"{base}-V{self.profile.sku_version}-"
                + "".join(segment_values)
            )

            canonical = {
                "family_code": self.profile.family_code,
                "metadata_publication_id": (
                    self.metadata_publication_id
                ),
                "combination_batch_id": batch_id,
                "selections": {
                    key: selections[key]
                    for key in sorted(selections)
                },
            }
            signature = hashlib.sha256(
                json.dumps(
                    canonical,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")
            ).hexdigest()

            return IdentifierGenerationResult(
                valid=True,
                part_number=part_number,
                sku=sku,
                configuration_signature=signature,
                segments=tuple(resolved),
                validation_messages=(),
                metadata_trace={
                    "family_code": (
                        self.profile.family_code
                    ),
                    "metadata_publication_id": (
                        self.metadata_publication_id
                    ),
                    "combination_batch_id": batch_id,
                    "selection_count": len(selections),
                },
            )

        finally:
            connection.close()

    def _family_id(
        self,
        cursor: pyodbc.Cursor,
    ) -> int:
        row = cursor.execute(
            """
            SELECT PumpFamilyId
            FROM cfg.PumpFamily
            WHERE FamilyCode = ?;
            """,
            self.profile.family_code,
        ).fetchone()

        if row is None:
            raise IdentifierGenerationError(
                "Pump family was not found."
            )

        return int(row[0])

    def _combination_batch(
        self,
        cursor: pyodbc.Cursor,
    ) -> int:
        row = cursor.execute(
            """
            SELECT TOP (1) ImportBatchId
            FROM stg.SegmentCombinationImportBatch
            WHERE FamilyCode = ?
              AND Status IN ('Loaded', 'Validated')
            ORDER BY ImportBatchId DESC;
            """,
            self.profile.family_code,
        ).fetchone()

        if row is None:
            raise IdentifierGenerationError(
                "Combination batch was not found."
            )

        return int(row[0])

    def _lookup_attribute(
        self,
        cursor: pyodbc.Cursor,
        family_id: int,
        field_code: str,
        display_value: str,
    ):
        rows = cursor.execute(
            """
            SELECT TOP (2)
                AttributeValueId,
                IdentifierCode
            FROM cfg.AttributeValue
            WHERE MetadataPublicationId = ?
              AND PumpFamilyId = ?
              AND FieldCode = ?
              AND DisplayValue = ?
              AND IsActive = 1
            ORDER BY AttributeValueId;
            """,
            self.metadata_publication_id,
            family_id,
            field_code,
            display_value,
        ).fetchall()

        if len(rows) != 1:
            raise IdentifierGenerationError(
                f"Expected one attribute resolution for "
                f"{field_code}='{display_value}'; "
                f"found {len(rows)}."
            )

        return rows[0]

    def _attribute(
        self,
        cursor: pyodbc.Cursor,
        family_id: int,
        segment: IdentifierSegmentProfile,
        selections: dict[str, str],
    ) -> ResolvedIdentifierSegment:
        if not segment.field_code:
            raise IdentifierGenerationError(
                "Attribute field code is missing."
            )

        value = selections[segment.field_code]
        row = self._lookup_attribute(
            cursor,
            family_id,
            segment.field_code,
            value,
        )
        source_id = int(row.AttributeValueId)

        return ResolvedIdentifierSegment(
            segment_code=segment.segment_code,
            segment_value=str(row.IdentifierCode),
            source_id=source_id,
            source_ids=(source_id,),
            resolution_type="ATTRIBUTE",
        )

    def _attribute_sequence(
        self,
        cursor: pyodbc.Cursor,
        family_id: int,
        segment: IdentifierSegmentProfile,
        selections: dict[str, str],
    ) -> ResolvedIdentifierSegment:
        if (
            not segment.source_field_code
            or not segment.field_codes
        ):
            raise IdentifierGenerationError(
                "Attribute sequence profile is incomplete."
            )

        rows = [
            self._lookup_attribute(
                cursor,
                family_id,
                segment.source_field_code,
                selections[field_code],
            )
            for field_code in segment.field_codes
        ]

        source_ids = tuple(
            int(row.AttributeValueId)
            for row in rows
        )

        return ResolvedIdentifierSegment(
            segment_code=segment.segment_code,
            segment_value="".join(
                str(row.IdentifierCode)
                for row in rows
            ),
            source_id=None,
            source_ids=source_ids,
            resolution_type="ATTRIBUTE_SEQUENCE",
        )

    def _combination(
        self,
        cursor: pyodbc.Cursor,
        batch_id: int,
        segment: IdentifierSegmentProfile,
        selections: dict[str, str],
    ) -> ResolvedIdentifierSegment:
        predicates = [
            "ImportBatchId = ?",
            "FamilyCode = ?",
            "SegmentCode = ?",
        ]
        parameters: list[Any] = [
            batch_id,
            self.profile.family_code,
            segment.segment_code,
        ]

        for field_code in segment.selection_fields:
            predicates.append(
                "JSON_VALUE(SelectionsJson, ?) = ?"
            )
            parameters.extend(
                [
                    f'$."{field_code}"',
                    selections[field_code],
                ]
            )

        rows = cursor.execute(
            f"""
            SELECT TOP (2)
                SourceId,
                SegmentValue
            FROM stg.SegmentCombinationImport
            WHERE {' AND '.join(predicates)}
            ORDER BY SourceId;
            """,
            *parameters,
        ).fetchall()

        if len(rows) != 1:
            raise IdentifierGenerationError(
                f"Expected one combination resolution for "
                f"{segment.segment_code}; found "
                f"{len(rows)}."
            )

        source_id = int(rows[0].SourceId)

        return ResolvedIdentifierSegment(
            segment_code=segment.segment_code,
            segment_value=str(rows[0].SegmentValue),
            source_id=source_id,
            source_ids=(source_id,),
            resolution_type="COMBINATION",
        )

    def _base(
        self,
        selections: dict[str, str],
    ) -> str:
        value = selections[
            self.profile.series_field_code
        ]
        match = self.series_regex.search(value)

        if match is None:
            raise IdentifierGenerationError(
                "Series base identifier was not resolved."
            )

        return self.profile.base_prefix + match.group(1)

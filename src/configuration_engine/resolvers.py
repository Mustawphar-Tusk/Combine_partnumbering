from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pyodbc

from src.configuration_engine.models import (
    ResolvedConfigurationSegment,
)


class SegmentResolver(Protocol):
    def resolve(
        self,
        *,
        family_code: str,
        segment_code: str,
        payload,
    ) -> ResolvedConfigurationSegment | None: ...


@dataclass
class ResolverRegistry:
    _resolvers: dict[str, SegmentResolver]

    def __init__(self) -> None:
        self._resolvers = {}

    def register(
        self,
        resolution_type: str,
        resolver: SegmentResolver,
    ) -> None:
        key = resolution_type.strip().upper()
        if key in self._resolvers:
            raise ValueError(
                f"Resolver '{key}' is already registered."
            )
        self._resolvers[key] = resolver

    def get(self, resolution_type: str) -> SegmentResolver:
        key = resolution_type.strip().upper()
        try:
            return self._resolvers[key]
        except KeyError as exc:
            raise KeyError(
                f"No resolver registered for '{key}'."
            ) from exc


class SqlAttributeResolver:
    def __init__(
        self,
        connection_string: str,
        metadata_publication_id: int,
    ) -> None:
        self.connection_string = connection_string
        self.metadata_publication_id = metadata_publication_id

    def resolve(
        self,
        *,
        family_code: str,
        segment_code: str,
        payload,
    ) -> ResolvedConfigurationSegment | None:
        display_value = str(payload).strip()

        connection = pyodbc.connect(
            self.connection_string,
            autocommit=True,
        )

        try:
            rows = connection.cursor().execute(
                """
                SELECT TOP (2)
                    av.AttributeValueId,
                    av.IdentifierCode
                FROM cfg.AttributeValue AS av
                INNER JOIN cfg.PumpFamily AS pf
                    ON pf.PumpFamilyId = av.PumpFamilyId
                WHERE av.MetadataPublicationId = ?
                  AND pf.FamilyCode = ?
                  AND av.FieldCode = ?
                  AND av.DisplayValue = ?
                  AND av.IsActive = 1
                ORDER BY av.AttributeValueId;
                """,
                self.metadata_publication_id,
                family_code,
                segment_code,
                display_value,
            ).fetchall()

            if not rows:
                return None

            if len(rows) > 1:
                raise RuntimeError(
                    f"Multiple attribute values matched "
                    f"{segment_code}='{display_value}'."
                )

            return ResolvedConfigurationSegment(
                segment_code=segment_code,
                segment_value=str(rows[0].IdentifierCode),
                source_id=int(rows[0].AttributeValueId),
                resolution_type="ATTRIBUTE",
            )

        finally:
            connection.close()

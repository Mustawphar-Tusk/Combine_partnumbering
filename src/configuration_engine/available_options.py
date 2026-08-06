from __future__ import annotations

from dataclasses import dataclass

from src.configuration_engine.dependency_projection import (
    SqlFieldDependencyRepository,
)
from src.configuration_engine.projection import (
    SqlAttributeProjectionRepository,
    SqlConstraintProjectionRepository,
)
from src.configuration_engine.series_projection import (
    SqlSeriesConstraintRepository,
)
from src.configuration_engine.value_equivalences import (
    ValueEquivalenceProfile,
)
from src.configuration_engine.value_normalization import (
    canonical_engineering_value,
)


@dataclass(frozen=True)
class AvailableOptionsRequest:
    family_code: str
    target_field_code: str
    series_code: str | None = None
    segment_code: str | None = None
    current_segment_selections: dict[str, str] | None = None
    current_selections: dict[str, str] | None = None


@dataclass(frozen=True)
class AvailableOptionsResult:
    family_code: str
    target_field_code: str
    series_code: str | None
    segment_code: str | None
    values: tuple[str, ...]
    source_counts: dict[str, int]
    applied_filters: tuple[str, ...]


class AvailableOptionsService:
    def __init__(
        self,
        *,
        attribute_repository: SqlAttributeProjectionRepository,
        series_repository: SqlSeriesConstraintRepository,
        combination_repository: SqlConstraintProjectionRepository,
        attribute_fields: set[str],
        segment_field_map: dict[str, str],
        value_equivalences: (
            ValueEquivalenceProfile | None
        ) = None,
        dependency_repository: (
            SqlFieldDependencyRepository | None
        ) = None,
        attribute_field_aliases: (
            dict[str, str] | None
        ) = None,
    ) -> None:
        self.attribute_repository = attribute_repository
        self.series_repository = series_repository
        self.combination_repository = combination_repository
        self.attribute_fields = {
            field.strip().upper()
            for field in attribute_fields
        }
        self.segment_field_map = {
            field.strip().upper(): segment.strip().upper()
            for field, segment in segment_field_map.items()
        }
        self.value_equivalences = value_equivalences
        self.dependency_repository = dependency_repository
        self.attribute_field_aliases = {
            field.strip().upper(): source.strip().upper()
            for field, source in (
                attribute_field_aliases or {}
            ).items()
        }

    def available_options(
        self,
        request: AvailableOptionsRequest,
    ) -> AvailableOptionsResult:
        target = request.target_field_code.strip().upper()
        segment_context = (
            request.current_segment_selections or {}
        )
        full_context = request.current_selections or {}
        applied_filters: list[str] = []
        source_counts: dict[str, int] = {}
        sources: list[
            tuple[str, tuple[str, ...]]
        ] = []

        attribute_source_field = (
            self.attribute_field_aliases.get(
                target,
                target,
            )
        )

        if (
            target in self.attribute_fields
            or target in self.attribute_field_aliases
        ):
            rows = (
                self.attribute_repository
                .available_attribute_values(
                    family_code=request.family_code,
                    field_code=attribute_source_field,
                )
            )
            values = tuple(
                row.display_value
                for row in rows
            )
            source_counts["ATTRIBUTE"] = len(values)
            applied_filters.append("ATTRIBUTE")
            sources.append(("ATTRIBUTE", values))

        if request.series_code:
            rows = self.series_repository.available_values(
                family_code=request.family_code,
                series_code=request.series_code,
                field_code=target,
            )
            if rows:
                values = tuple(
                    row.option_value
                    for row in rows
                )
                source_counts["SERIES"] = len(values)
                applied_filters.append("SERIES")
                sources.append(("SERIES", values))

        segment_code = (
            request.segment_code.strip().upper()
            if request.segment_code
            else self.segment_field_map.get(target)
        )

        if segment_code:
            rows = (
                self.combination_repository
                .available_combination_values(
                    family_code=request.family_code,
                    segment_code=segment_code,
                    target_field_code=target,
                    current_selections=segment_context,
                )
            )
            values = tuple(
                row.display_value
                for row in rows
            )
            source_counts["COMBINATION"] = len(values)
            applied_filters.append("COMBINATION")
            sources.append(("COMBINATION", values))

        if (
            self.dependency_repository is not None
            and self.dependency_repository.applies_to(
                target
            )
        ):
            rows = (
                self.dependency_repository.available_values(
                    family_code=request.family_code,
                    target_field_code=target,
                    series_code=request.series_code,
                    current_selections=full_context,
                )
            )
            values = tuple(
                row.display_value
                for row in rows
            )
            source_counts["DEPENDENCY"] = len(values)
            applied_filters.append("DEPENDENCY")
            sources.append(("DEPENDENCY", values))

        if not sources:
            return AvailableOptionsResult(
                family_code=request.family_code,
                target_field_code=target,
                series_code=request.series_code,
                segment_code=segment_code,
                values=(),
                source_counts=source_counts,
                applied_filters=tuple(applied_filters),
            )

        primary_source_type, primary_values = next(
            (
                item
                for item in sources
                if item[0] == "COMBINATION"
            ),
            next(
                (
                    item
                    for item in sources
                    if item[0] == "DEPENDENCY"
                ),
                sources[0],
            ),
        )

        canonical_maps = [
            self._canonical_value_map(
                target_field_code=target,
                source_type=source_type,
                values=values,
                context=segment_context,
            )
            for source_type, values in sources
        ]

        allowed = set.intersection(
            *(set(mapping) for mapping in canonical_maps)
        )

        combination_map = next(
            (
                mapping
                for (source_type, _), mapping
                in zip(sources, canonical_maps)
                if source_type == "COMBINATION"
            ),
            None,
        )

        if (
            combination_map is not None
            and self.value_equivalences is not None
        ):
            for key, display_value in combination_map.items():
                if (
                    self.value_equivalences
                    .is_combination_passthrough(
                        field_code=target,
                        raw_value=display_value,
                    )
                ):
                    allowed.add(key)

        display_map = self._canonical_value_map(
            target_field_code=target,
            source_type=primary_source_type,
            values=primary_values,
            context=segment_context,
        )

        values = tuple(
            display_map[key]
            for key in sorted(
                allowed,
                key=lambda item: (
                    display_map[item].casefold()
                ),
            )
            if key in display_map
        )

        return AvailableOptionsResult(
            family_code=request.family_code,
            target_field_code=target,
            series_code=request.series_code,
            segment_code=segment_code,
            values=values,
            source_counts=source_counts,
            applied_filters=tuple(applied_filters),
        )

    def validate_selected_value(
        self,
        request: AvailableOptionsRequest,
        selected_value: str,
    ) -> bool:
        result = self.available_options(request)
        return selected_value in result.values

    def _canonical_value_map(
        self,
        *,
        target_field_code: str,
        source_type: str,
        values: tuple[str, ...],
        context: dict[str, str],
    ) -> dict[str, str]:
        result: dict[str, str] = {}

        for value in values:
            fallback = canonical_engineering_value(
                field_code=target_field_code,
                value=value,
                context=context,
                source_type=source_type,
            )

            if self.value_equivalences is None:
                key = fallback
            else:
                key = (
                    self.value_equivalences.canonical_key(
                        field_code=target_field_code,
                        raw_value=value,
                        fallback_key=fallback,
                    )
                )

            result.setdefault(key, value)

        return result

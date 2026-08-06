from __future__ import annotations

import json
from pathlib import Path

from src.configuration_engine.constraint_coverage import (
    ConstraintCoveragePolicy,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    runtime_dir = (
        PROJECT_ROOT
        / "config"
        / "runtime_profiles"
    )

    coverage_mapping = json.loads(
        (
            runtime_dir
            / "fybroc_dependency_coverage.json"
        ).read_text(encoding="utf-8")
    )
    navigation = json.loads(
        (
            runtime_dir
            / "fybroc_allowable_navigation.json"
        ).read_text(encoding="utf-8")
    )

    policy = ConstraintCoveragePolicy.from_mapping(
        coverage_mapping
    )
    field_order = tuple(
        navigation["field_order"]
    )
    policy.assert_field_order(field_order)

    counts: dict[str, int] = {}

    for source_type in (
        coverage_mapping["required_fields"].values()
    ):
        counts[source_type] = (
            counts.get(source_type, 0) + 1
        )

    print(
        json.dumps(
            {
                "family_code": policy.family_code,
                "field_count": len(field_order),
                "coverage_complete": True,
                "source_type_counts": counts,
                "unresolved_fields": [],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

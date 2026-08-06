from __future__ import annotations

from pathlib import Path

from src.compiler.series_constraint_compiler import (
    compile_series_constraints,
    save_report,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    report = compile_series_constraints(
        project_root=PROJECT_ROOT,
        discovery_path=(
            PROJECT_ROOT
            / "exports"
            / "workbook_discovery.json"
        ),
        profile_path=(
            PROJECT_ROOT
            / "config"
            / "constraint_profiles"
            / "fybroc_series_field_options.json"
        ),
    )

    save_report(
        report,
        PROJECT_ROOT / "exports",
    )

    print(f"Fields compiled: {report.field_count}")
    print(f"Unique field options: {report.option_count}")
    print(f"Series-option relations: {report.relation_count}")
    print(f"Issues recorded: {report.issue_count}")

    errors = [
        issue
        for issue in report.issues
        if issue.severity == "Error"
    ]

    if errors:
        raise SystemExit(
            f"Compilation completed with {len(errors)} error(s)."
        )


if __name__ == "__main__":
    main()

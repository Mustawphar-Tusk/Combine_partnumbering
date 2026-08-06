from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.compiler.option_constraint_compiler import (
    compile_option_constraints,
    save_csv,
    save_json,
)


def main() -> None:
    discovery_path = PROJECT_ROOT / "exports" / "workbook_discovery.json"
    profile_directory = (
        PROJECT_ROOT / "config" / "option_constraint_profiles"
    )
    output_path = (
        PROJECT_ROOT / "exports" / "option_constraint_candidates.json"
    )

    if not discovery_path.exists():
        raise SystemExit(
            "Workbook discovery output is missing. Run "
            "`python -m scripts.discover_workbooks` first."
        )

    report = compile_option_constraints(
        project_root=PROJECT_ROOT,
        discovery_path=discovery_path,
        profile_directory=profile_directory,
    )

    save_json(report, output_path)
    save_csv(report, PROJECT_ROOT / "exports")

    print(f"Options compiled: {report.option_count}")
    print(f"Dependencies compiled: {report.dependency_count}")
    print(f"Constraint candidates compiled: {report.constraint_count}")
    print(f"Legacy invalid markers recorded: {report.legacy_marker_count}")
    print(f"Issues recorded: {report.issue_count}")
    print(f"Report written to: {output_path}")

    errors = [
        issue for issue in report.issues if issue.severity == "Error"
    ]
    if errors:
        raise SystemExit(
            f"Compilation completed with {len(errors)} error issue(s)."
        )


if __name__ == "__main__":
    main()

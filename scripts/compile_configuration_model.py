from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.compiler.configuration_model import (
    compile_configuration_model,
    save_csv_exports,
    save_report,
)


def main() -> None:
    discovery_path = PROJECT_ROOT / "exports" / "workbook_discovery.json"
    profile_directory = PROJECT_ROOT / "config" / "compiler_profiles"
    output_path = PROJECT_ROOT / "exports" / "configuration_model_candidates.json"

    if not discovery_path.exists():
        raise SystemExit(
            "Workbook discovery output is missing. Run "
            "`python -m scripts.discover_workbooks` first."
        )

    report = compile_configuration_model(
        project_root=PROJECT_ROOT,
        discovery_path=discovery_path,
        profile_directory=profile_directory,
    )

    save_report(report, output_path)
    save_csv_exports(report, PROJECT_ROOT / "exports")

    print(f"Sections compiled: {report.section_count}")
    print(f"Fields compiled: {report.field_count}")
    print(f"Issues recorded: {report.issue_count}")
    print(f"Report written to: {output_path}")

    error_count = sum(
        1 for issue in report.issues if issue.severity == "Error"
    )
    if error_count:
        raise SystemExit(
            f"Compilation completed with {error_count} error issue(s)."
        )


if __name__ == "__main__":
    main()

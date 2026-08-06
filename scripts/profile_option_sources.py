from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.compiler.option_source_profiler import (
    profile_option_sources,
    save_csv,
    save_json,
)


def main() -> None:
    report = profile_option_sources(
        project_root=PROJECT_ROOT,
        discovery_path=PROJECT_ROOT
        / "exports"
        / "workbook_discovery.json",
        profile_path=PROJECT_ROOT
        / "config"
        / "option_source_profile.json",
    )

    output = PROJECT_ROOT / "exports" / "option_source_profile.json"
    save_json(report, output)
    save_csv(report, PROJECT_ROOT / "exports")

    print(f"Named ranges found: {report.named_range_count}")
    print(f"Validations found: {report.validation_count}")
    print(f"Option table candidates found: {report.option_table_count}")
    print(f"Issues recorded: {report.issue_count}")
    print(f"Report written to: {output}")

    errors = [
        issue for issue in report.issues
        if issue.severity == "Error"
    ]
    if errors:
        raise SystemExit(
            f"Profiling completed with {len(errors)} error(s)."
        )


if __name__ == "__main__":
    main()

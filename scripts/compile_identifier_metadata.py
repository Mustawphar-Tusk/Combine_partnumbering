from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.compiler.identifier_metadata_compiler import (
    compile_identifier_metadata,
    save_csv,
    save_json,
)


def main() -> None:
    report = compile_identifier_metadata(
        project_root=PROJECT_ROOT,
        discovery_path=PROJECT_ROOT / "exports" / "workbook_discovery.json",
        profile_directory=PROJECT_ROOT / "config" / "identifier_profiles",
    )

    output = PROJECT_ROOT / "exports" / "identifier_metadata_candidates.json"
    save_json(report, output)
    save_csv(report, PROJECT_ROOT / "exports")

    print(f"Models compiled: {report.model_count}")
    print(f"Identifier formats compiled: {report.format_count}")
    print(f"Segments compiled: {report.segment_count}")
    print(f"Issues recorded: {report.issue_count}")
    print(f"Report written to: {output}")

    errors = [issue for issue in report.issues if issue.severity == "Error"]
    if errors:
        raise SystemExit(f"Compilation completed with {len(errors)} error(s).")


if __name__ == "__main__":
    main()

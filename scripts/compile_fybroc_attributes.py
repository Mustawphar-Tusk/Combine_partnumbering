from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.compiler.attribute_metadata_compiler import (
    compile_attribute_metadata,
    save_csv,
    save_json,
)


def main() -> None:
    report = compile_attribute_metadata(
        project_root=PROJECT_ROOT,
        discovery_path=PROJECT_ROOT / "exports" / "workbook_discovery.json",
        profile_path=PROJECT_ROOT
        / "config"
        / "attribute_profiles"
        / "fybroc_attributes.json",
    )

    output = PROJECT_ROOT / "exports" / "fybroc_attribute_candidates.json"
    save_json(report, output)
    save_csv(report, PROJECT_ROOT / "exports")

    print(f"Fields compiled: {report.field_count}")
    print(f"Attribute values compiled: {report.value_count}")
    print(f"Issues recorded: {report.issue_count}")
    print(f"Report written to: {output}")

    errors = [issue for issue in report.issues if issue.severity == "Error"]
    if errors:
        raise SystemExit(
            f"Compilation completed with {len(errors)} error(s)."
        )


if __name__ == "__main__":
    main()

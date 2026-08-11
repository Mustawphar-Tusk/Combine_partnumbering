from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.compiler.dependency_tuple_compiler import (
    compile_dependency_tuples,
    save_dependency_outputs,
)


def main() -> None:
    profile = (
        PROJECT_ROOT
        / "config"
        / "dependency_profiles"
        / "dean.json"
    )

    report = compile_dependency_tuples(
        project_root=PROJECT_ROOT,
        profile_path=profile,
    )

    outputs = save_dependency_outputs(
        report,
        PROJECT_ROOT / "exports",
    )

    s = report["summary"]

    print("=" * 96)
    print("M023.3 — DEAN DEPENDENCY COMPILER")
    print("=" * 96)
    print(f"Workbook reads               : {s['workbook_reads']}")
    print(f"Source dependency tables     : {s['source_dependency_table_count']}")
    print(f"Compiled rules               : {s['compiled_rule_count']}")
    print(f"Ready rules                  : {s['ready_rule_count']}")
    print(f"Blocked rules                : {s['blocked_rule_count']}")
    print(f"Ready tuples                 : {s['ready_tuple_count']}")
    print(f"Review records               : {s['review_record_count']}")
    print(f"Errors                       : {s['error_count']}")
    print(f"Warnings                     : {s['warning_count']}")
    print(f"Publication gate             : {s['publication_gate']}")
    print()
    print("Rule semantics:")
    print(s["rule_semantics"])
    print()
    for label, path in outputs.items():
        print(f"{label:<10}: {path}")

    if s["error_count"]:
        raise SystemExit(
            "M023.3 dependency compilation completed with errors. "
            "Review exports/m023_dean_dependency_issues.csv."
        )


if __name__ == "__main__":
    main()

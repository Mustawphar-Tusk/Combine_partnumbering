from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.compiler.model_option_applicability_compiler import (
    compile_model_option_applicability,
    save_applicability_outputs,
)


def main() -> None:
    profile_path = (
        PROJECT_ROOT
        / "config"
        / "applicability_profiles"
        / "dean.json"
    )

    report = compile_model_option_applicability(
        project_root=PROJECT_ROOT,
        profile_path=profile_path,
    )

    outputs = save_applicability_outputs(
        report,
        PROJECT_ROOT / "exports",
    )

    s = report["summary"]

    print("=" * 96)
    print("M023.2 — DEAN APPLICABILITY COMPILER")
    print("=" * 96)
    print(f"Workbook reads                : {s['workbook_reads']}")
    print(f"Rev2 workbook reads           : {s['rev2_workbook_reads']}")
    print(f"Pump Options model rows       : {s['pump_options_model_rows']}")
    print(f"Accepted models               : {s['accepted_model_count']}")
    print(f"Blocked models                : {s['blocked_model_count']}")
    print(f"Matrix groups                 : {s['matrix_group_count']}")
    print(f"Compiled groups               : {s['compiled_group_count']}")
    print(f"Applicability candidates      : {s['candidate_count']}")
    print(f"Ready candidates              : {s['ready_candidate_count']}")
    print(f"Allowed candidates            : {s['allowed_candidate_count']}")
    print(f"Standard candidates           : {s['standard_candidate_count']}")
    print(f"Review records                : {s['review_record_count']}")
    print(f"Zero-allowed model/field pairs: {s['zero_allowed_model_field_pair_count']}")
    print(f"Errors                        : {s['error_count']}")
    print(f"Warnings                      : {s['warning_count']}")
    print(f"Info                          : {s['info_count']}")
    print(f"Publication gate              : {s['publication_gate']}")
    print()
    print("Marker counts:")
    print(json.dumps(s["marker_counts"], indent=2))
    print()
    print("Accepted model classifications:")
    print(json.dumps(s["model_classification_counts"], indent=2))
    print()
    for label, path in outputs.items():
        print(f"{label:<12}: {path}")

    if s["error_count"]:
        raise SystemExit(
            "M023.2 applicability compilation completed with errors. "
            "Review exports/m023_dean_applicability_issues.csv."
        )


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.compiler.configuration_source_reconciliation import (
    compile_configuration_source_reconciliation,
    save_reconciliation_outputs,
)


def main() -> None:
    profile_path = (
        PROJECT_ROOT
        / "config"
        / "reconciliation_profiles"
        / "dean.json"
    )

    report = compile_configuration_source_reconciliation(
        project_root=PROJECT_ROOT,
        profile_path=profile_path,
    )

    outputs = save_reconciliation_outputs(
        report,
        PROJECT_ROOT / "exports",
    )

    summary = report["summary"]

    print("=" * 92)
    print("M023.1 — DEAN SOURCE RECONCILIATION")
    print("=" * 92)
    print(f"Rev2 fields                : {summary['rev2_field_count']}")
    seq = summary['rev2_sequence_validation']
    print(f"Expected sequence gaps     : {seq['expected_sequence_gaps']}")
    print(f"Unexpected sequence gaps   : {seq['unexpected_missing_sequences']}")
    print(f"Logic option domains       : {summary['logic_option_domain_count']}")
    print(f"Logic option rows          : {summary['logic_option_row_count']}")
    print(f"Dependency tables          : {summary['dependency_table_count']}")
    print(f"Dependency rows            : {summary['dependency_row_count']}")
    print(f"Pump Options model rows    : {summary['pump_matrix_model_count']}")
    print(f"Pump Options field groups  : {summary['pump_matrix_group_count']}")
    print(f"Price Options field groups : {summary['price_matrix_group_count']}")
    print(f"Reconciled fields          : {summary['field_reconciliation_count']}")
    print(f"Rev2 model references      : {summary['rev2_model_reference_count']}")
    print(f"Reconciled model keys      : {summary['model_reconciliation_count']}")
    print(f"Issues                     : {summary['issue_count']}")
    print(f"Errors                     : {summary['error_count']}")
    print(f"Warnings                   : {summary['warning_count']}")
    print(f"Info                       : {summary['info_count']}")
    print()
    print("Field classifications:")
    print(json.dumps(summary["field_classification_counts"], indent=2))
    print()
    print("Model classifications:")
    print(json.dumps(summary["model_classification_counts"], indent=2))
    print()
    for label, path in outputs.items():
        print(f"{label:<14}: {path}")

    if summary["error_count"]:
        raise SystemExit(
            "M023.1 compilation completed with reconciliation errors. "
            "Review exports/m023_dean_reconciliation_issues.csv before publication."
        )


if __name__ == "__main__":
    main()

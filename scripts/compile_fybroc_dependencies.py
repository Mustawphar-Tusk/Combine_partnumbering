from __future__ import annotations

from pathlib import Path

from src.compiler.fybroc_dependency_compiler import (
    compile_dependencies,
    save_report,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    report = compile_dependencies(
        project_root=PROJECT_ROOT,
        profile_path=(
            PROJECT_ROOT
            / "config"
            / "dependency_profiles"
            / "fybroc_dependency_compiler.json"
        ),
    )

    save_report(report, PROJECT_ROOT / "exports")

    print(f"Dependency candidates: {report.candidate_count:,}")
    print(
        "Series/Size/Trim relations: "
        f"{report.trim_relation_count:,}"
    )
    print(
        "Motor/Modification relations: "
        f"{report.motor_modification_relation_count:,}"
    )
    print(f"Issues recorded: {report.issue_count:,}")

    errors = [
        issue
        for issue in report.issues
        if issue.severity == "Error"
    ]

    if errors:
        raise SystemExit(
            f"Compilation produced {len(errors)} error(s)."
        )


if __name__ == "__main__":
    main()

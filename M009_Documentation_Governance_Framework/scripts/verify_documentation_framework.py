from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "docs/README.md",
    "docs/architecture/SystemArchitecture.md",
    "docs/adr/README.md",
    "docs/progress/Dashboard.md",
    "docs/progress/MilestoneRegister.md",
    "docs/milestones/M009-Attribute-Metadata-Platform.md",
    "docs/modules/ConfigurationEngine.md",
    "docs/testing/TestingSummary.md",
    "docs/releases/v0.2.0.md",
    "docs/engineering-journal/2026-07.md",
]


def main() -> None:
    missing = [path for path in REQUIRED if not (PROJECT_ROOT / path).exists()]
    if missing:
        print("Documentation framework verification failed.")
        for path in missing:
            print(f"[MISSING] {path}")
        raise SystemExit(1)
    print("Documentation framework verified.")
    print(f"Required documents found: {len(REQUIRED)}")


if __name__ == "__main__":
    main()

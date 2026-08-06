from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "docs/README.md",
    "docs/progress/MilestoneRegister.md",
    "docs/milestones/M009-Attribute-Metadata-Platform.md",
    "docs/adr/ADR-0008-Metadata-Publication.md",
    "docs/modules/AttributeMetadataCompiler.md",
    "docs/modules/ResolverRegistry.md",
    "docs/releases/v0.2.0.md",
    "docs/engineering-journal/2026-07.md",
]


def main() -> None:
    missing = [
        item for item in REQUIRED
        if not (PROJECT_ROOT / item).exists()
    ]

    if missing:
        for item in missing:
            print(f"[MISSING] {item}")
        raise SystemExit(1)

    print("Documentation framework verified.")
    print(f"Required documents found: {len(REQUIRED)}")


if __name__ == "__main__":
    main()

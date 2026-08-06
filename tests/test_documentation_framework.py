from pathlib import Path


def test_documentation_framework_exists() -> None:
    root = Path(__file__).resolve().parents[1]

    required = [
        root / "docs" / "README.md",
        root / "docs" / "milestones" / "M009-Attribute-Metadata-Platform.md",
        root / "docs" / "adr" / "ADR-0008-Metadata-Publication.md",
    ]

    assert all(path.exists() for path in required)

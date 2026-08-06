from pathlib import Path


def test_documentation_framework_exists() -> None:
    project_root = Path(__file__).resolve().parents[1]
    required = [
        project_root / "docs" / "README.md",
        project_root / "docs" / "architecture" / "SystemArchitecture.md",
        project_root / "docs" / "adr" / "README.md",
        project_root / "docs" / "progress" / "Dashboard.md",
        project_root / "docs" / "milestones" / "M009-Attribute-Metadata-Platform.md",
        project_root / "docs" / "engineering-journal" / "2026-07.md",
    ]
    assert all(path.exists() for path in required)

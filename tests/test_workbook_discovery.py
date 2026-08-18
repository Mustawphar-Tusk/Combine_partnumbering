from pathlib import Path

from src.compiler.manifest_loader import load_all_manifests
from src.compiler.workbook_discovery import discover_all


def test_discovery_finds_expected_workbooks() -> None:
    root = Path.cwd()

    manifests = load_all_manifests(
        root / "config" / "workbook_manifests"
    )

    report = discover_all(
        root,
        manifests,
    )

    assert report.family_count == 2

    failures = [
        record
        for record in report.records
        if record.discovery_status in {
            "missing",
            "error",
        }
    ]

    assert not failures

    unclassified = [
        record
        for record in report.records
        if record.role == "unclassified"
    ]

    assert not unclassified

    discovered = [
        record
        for record in report.records
        if record.file_name
    ]

    assert discovered

    assert all(
        len(record.sha256) == 64
        for record in discovered
    )

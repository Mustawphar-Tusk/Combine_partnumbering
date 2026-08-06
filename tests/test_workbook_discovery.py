from pathlib import Path
from src.compiler.manifest_loader import load_all_manifests
from src.compiler.workbook_discovery import discover_all

def test_discovery_finds_expected_workbooks():
    root = Path.cwd()
    manifests = load_all_manifests(root / "config" / "workbook_manifests")
    report = discover_all(root, manifests)
    assert report.family_count == 2
    assert report.workbook_count == 5
    assert not [r for r in report.records if r.discovery_status in {"missing", "error"}]
    assert all(len(r.sha256) == 64 for r in report.records if r.file_name)

from pathlib import Path
from src.compiler.manifest_loader import load_all_manifests

def test_manifests_load():
    manifests = load_all_manifests(Path("config/workbook_manifests"))
    assert {m.family_code for m in manifests} == {"DEAN", "FYBROC"}

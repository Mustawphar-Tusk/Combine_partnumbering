from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class WorkbookRole:
    pattern: str
    role: str
    required: bool = True
    processing_order: int = 100

@dataclass(frozen=True)
class FamilyManifest:
    family_code: str
    family_name: str
    folder_name: str
    workbooks: tuple[WorkbookRole, ...]

def load_manifest(path: Path) -> FamilyManifest:
    data = json.loads(path.read_text(encoding="utf-8"))
    return FamilyManifest(
        family_code=data["family_code"].upper(),
        family_name=data["family_name"],
        folder_name=data["folder_name"],
        workbooks=tuple(
            WorkbookRole(
                pattern=item["pattern"],
                role=item["role"],
                required=item.get("required", True),
                processing_order=item.get("processing_order", 100),
            )
            for item in data["workbooks"]
        ),
    )

def load_all_manifests(directory: Path) -> tuple[FamilyManifest, ...]:
    manifests = tuple(load_manifest(path) for path in sorted(directory.glob("*.json")))
    if not manifests:
        raise FileNotFoundError(f"No manifests found in {directory}")
    return manifests

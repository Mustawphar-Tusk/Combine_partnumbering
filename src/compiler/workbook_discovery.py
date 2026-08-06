from __future__ import annotations
import hashlib, json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path
from openpyxl import load_workbook
from src.compiler.manifest_loader import FamilyManifest

SUPPORTED_EXTENSIONS = {".xlsx", ".xlsm", ".xltx", ".xltm"}

@dataclass(frozen=True)
class WorksheetRecord:
    name: str
    state: str
    index: int

@dataclass(frozen=True)
class WorkbookRecord:
    family_code: str
    family_name: str
    role: str
    processing_order: int
    required: bool
    file_name: str
    relative_path: str
    extension: str
    macro_enabled: bool
    size_bytes: int
    modified_utc: str
    sha256: str
    worksheets: tuple[WorksheetRecord, ...]
    discovery_status: str
    discovery_messages: tuple[str, ...]

@dataclass(frozen=True)
class DiscoveryReport:
    generated_utc: str
    workbook_root: str
    workbook_count: int
    family_count: int
    records: tuple[WorkbookRecord, ...]

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def _worksheets(path: Path) -> tuple[WorksheetRecord, ...]:
    wb = load_workbook(
        path,
        read_only=True,
        data_only=False,
        keep_vba=path.suffix.lower() in {".xlsm", ".xltm"},
        keep_links=True,
    )
    try:
        return tuple(
            WorksheetRecord(ws.title, ws.sheet_state, index)
            for index, ws in enumerate(wb.worksheets, start=1)
        )
    finally:
        wb.close()

def discover_family(project_root: Path, manifest: FamilyManifest) -> tuple[WorkbookRecord, ...]:
    family_dir = project_root / "workbooks" / manifest.folder_name
    files = sorted(
        p for p in family_dir.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    records = []
    matched = set()

    for path in files:
        role_matches = [
            role for role in manifest.workbooks
            if fnmatch(path.name.casefold(), role.pattern.casefold())
        ]
        if len(role_matches) > 1:
            raise ValueError(f"{path.name} matches multiple manifest patterns")

        role = role_matches[0] if role_matches else None
        messages = []
        if role:
            matched.add(role.pattern)
            role_name = role.role
            order = role.processing_order
            required = role.required
        else:
            role_name = "unclassified"
            order = 9999
            required = False
            messages.append("Workbook is not classified by the manifest.")

        try:
            sheets = _worksheets(path)
            status = "discovered"
        except Exception as exc:
            sheets = ()
            status = "error"
            messages.append(str(exc))

        stat = path.stat()
        records.append(
            WorkbookRecord(
                manifest.family_code,
                manifest.family_name,
                role_name,
                order,
                required,
                path.name,
                str(path.relative_to(project_root)),
                path.suffix.lower(),
                path.suffix.lower() in {".xlsm", ".xltm"},
                stat.st_size,
                datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                sha256_file(path),
                sheets,
                status,
                tuple(messages),
            )
        )

    for role in manifest.workbooks:
        if role.required and role.pattern not in matched:
            records.append(
                WorkbookRecord(
                    manifest.family_code,
                    manifest.family_name,
                    role.role,
                    role.processing_order,
                    True,
                    "",
                    "",
                    "",
                    False,
                    0,
                    "",
                    "",
                    (),
                    "missing",
                    (f"Required pattern not found: {role.pattern}",),
                )
            )

    return tuple(sorted(records, key=lambda r: (r.processing_order, r.file_name.casefold())))

def discover_all(project_root: Path, manifests) -> DiscoveryReport:
    manifests = tuple(manifests)
    records = tuple(
        record
        for manifest in manifests
        for record in discover_family(project_root, manifest)
    )
    return DiscoveryReport(
        datetime.now(timezone.utc).isoformat(),
        str(project_root / "workbooks"),
        sum(1 for r in records if r.file_name),
        len(manifests),
        records,
    )

def save_report(report: DiscoveryReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(asdict(report), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

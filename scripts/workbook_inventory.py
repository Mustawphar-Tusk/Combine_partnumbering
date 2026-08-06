from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkgrel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


@dataclass(frozen=True)
class SheetInfo:
    workbook: str
    workbook_sha256: str
    sheet_name: str
    sheet_state: str
    sheet_id: str
    relationship_id: str
    xml_path: str | None
    max_row: int | None
    max_column: int | None
    formula_count: int
    data_validation_count: int
    merged_range_count: int
    table_relationship_count: int


@dataclass(frozen=True)
class DefinedNameInfo:
    workbook: str
    name: str
    local_sheet_id: str | None
    hidden: bool
    refers_to: str


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def column_number(cell_ref: str) -> int:
    match = re.match(r"([A-Z]+)", cell_ref.upper())
    if not match:
        return 0
    result = 0
    for char in match.group(1):
        result = result * 26 + (ord(char) - 64)
    return result


def resolve_target(base: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    base_parts = base.split("/")[:-1]
    for part in target.split("/"):
        if part == "..":
            if base_parts:
                base_parts.pop()
        elif part not in ("", "."):
            base_parts.append(part)
    return "/".join(base_parts)


def relationship_map(archive: zipfile.ZipFile, rel_path: str, base_xml_path: str) -> dict[str, str]:
    if rel_path not in archive.namelist():
        return {}
    root = ET.fromstring(archive.read(rel_path))
    result: dict[str, str] = {}
    for rel in root.findall("pkgrel:Relationship", NS):
        rel_id = rel.attrib.get("Id")
        target = rel.attrib.get("Target")
        if rel_id and target:
            result[rel_id] = resolve_target(base_xml_path, target)
    return result


def inspect_sheet(archive: zipfile.ZipFile, xml_path: str) -> tuple[int | None, int | None, int, int, int, int]:
    if xml_path not in archive.namelist():
        return None, None, 0, 0, 0, 0

    max_row = max_col = None
    formula_count = data_validation_count = merged_range_count = table_relationship_count = 0
    main_ns = f"{{{NS['main']}}}"

    # Stream worksheet XML so very large calculation sheets do not need to be
    # materialized in memory. This keeps the extractor generic and scalable.
    with archive.open(xml_path) as stream:
        for event, elem in ET.iterparse(stream, events=("start", "end")):
            tag = elem.tag
            if event == "start" and tag == main_ns + "dimension":
                ref = elem.attrib.get("ref", "")
                end_ref = ref.split(":")[-1]
                row_match = re.search(r"(\d+)$", end_ref)
                if row_match:
                    max_row = int(row_match.group(1))
                max_col = column_number(end_ref) or None
            elif event == "start" and tag == main_ns + "dataValidations":
                data_validation_count = int(elem.attrib.get("count", "0"))
            elif event == "start" and tag == main_ns + "mergeCells":
                merged_range_count = int(elem.attrib.get("count", "0"))
            elif event == "start" and tag == main_ns + "tableParts":
                table_relationship_count = int(elem.attrib.get("count", "0"))
            elif event == "end" and tag == main_ns + "f":
                formula_count += 1
            if event == "end":
                elem.clear()

    return max_row, max_col, formula_count, data_validation_count, merged_range_count, table_relationship_count


def inspect_workbook(path: Path) -> dict:
    digest = sha256_file(path)
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        workbook_xml = "xl/workbook.xml"
        if workbook_xml not in names:
            raise ValueError(f"{path.name} is not a supported Open XML workbook")
        root = ET.fromstring(archive.read(workbook_xml))
        rels = relationship_map(archive, "xl/_rels/workbook.xml.rels", workbook_xml)

        sheets: list[SheetInfo] = []
        for sheet in root.findall("main:sheets/main:sheet", NS):
            rel_id = sheet.attrib.get(f"{{{NS['rel']}}}id", "")
            xml_path = rels.get(rel_id)
            # Large worksheets are inventoried without a deep cell scan during
            # the foundation pass. A later targeted extractor streams only the
            # authoritative sheets defined in workbook_roles.json.
            if xml_path and xml_path in names:
                info = archive.getinfo(xml_path)
                metrics = inspect_sheet(archive, xml_path) if info.file_size <= 5_000_000 else (None, None, 0, 0, 0, 0)
            else:
                metrics = (None, None, 0, 0, 0, 0)
            sheets.append(
                SheetInfo(
                    workbook=path.name,
                    workbook_sha256=digest,
                    sheet_name=sheet.attrib.get("name", ""),
                    sheet_state=sheet.attrib.get("state", "visible"),
                    sheet_id=sheet.attrib.get("sheetId", ""),
                    relationship_id=rel_id,
                    xml_path=xml_path,
                    max_row=metrics[0],
                    max_column=metrics[1],
                    formula_count=metrics[2],
                    data_validation_count=metrics[3],
                    merged_range_count=metrics[4],
                    table_relationship_count=metrics[5],
                )
            )

        defined_names: list[DefinedNameInfo] = []
        names_node = root.find("main:definedNames", NS)
        if names_node is not None:
            for node in names_node.findall("main:definedName", NS):
                defined_names.append(
                    DefinedNameInfo(
                        workbook=path.name,
                        name=node.attrib.get("name", ""),
                        local_sheet_id=node.attrib.get("localSheetId"),
                        hidden=node.attrib.get("hidden", "0") == "1",
                        refers_to=(node.text or "").strip(),
                    )
                )

        return {
            "workbook": {
                "file_name": path.name,
                "file_path": str(path),
                "file_size_bytes": path.stat().st_size,
                "sha256": digest,
                "has_vba_project": "xl/vbaProject.bin" in names,
                "has_external_links": any(name.startswith("xl/externalLinks/") for name in names),
                "sheet_count": len(sheets),
                "defined_name_count": len(defined_names),
                "inspected_at_utc": datetime.now(timezone.utc).isoformat(),
            },
            "sheets": [asdict(item) for item in sheets],
            "defined_names": [asdict(item) for item in defined_names],
        }


def write_csv(path: Path, rows: Iterable[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Dynamically inventory Open XML Excel workbooks without changing them.")
    parser.add_argument("workbooks", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    results = [inspect_workbook(path.resolve()) for path in args.workbooks]

    (args.output_dir / "workbook_inventory.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    workbook_rows = [item["workbook"] for item in results]
    sheet_rows = [row for item in results for row in item["sheets"]]
    name_rows = [row for item in results for row in item["defined_names"]]

    write_csv(args.output_dir / "workbooks.csv", workbook_rows, list(workbook_rows[0].keys()))
    write_csv(args.output_dir / "worksheets.csv", sheet_rows, list(sheet_rows[0].keys()))
    if name_rows:
        write_csv(args.output_dir / "defined_names.csv", name_rows, list(name_rows[0].keys()))

    print(json.dumps({
        "workbooks": len(workbook_rows),
        "worksheets": len(sheet_rows),
        "defined_names": len(name_rows),
        "output_dir": str(args.output_dir.resolve()),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

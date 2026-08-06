from __future__ import annotations

import csv
import json
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_DOC_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WORKBOOK_XML = "xl/workbook.xml"
WORKBOOK_RELS = "xl/_rels/workbook.xml.rels"


def _tag(local: str, namespace: str = NS_MAIN) -> str:
    return f"{{{namespace}}}{local}"


@dataclass(frozen=True)
class DefinedNameRecord:
    workbook: str
    family_code: str
    name: str
    refers_to: str
    local_sheet_id: int | None
    hidden: bool


@dataclass(frozen=True)
class WorksheetMetadata:
    workbook: str
    family_code: str
    sheet_name: str
    sheet_state: str
    sheet_index: int
    xml_path: str
    dimension_reference: str | None
    formula_count: int
    formula_samples: tuple[str, ...]
    merged_range_count: int
    merged_range_samples: tuple[str, ...]
    validation_count: int
    validation_samples: tuple[str, ...]
    table_relationship_count: int


@dataclass(frozen=True)
class WorkbookMetadata:
    workbook: str
    family_code: str
    relative_path: str
    macro_enabled: bool
    vba_project_present: bool
    external_link_count: int
    defined_names: tuple[DefinedNameRecord, ...]
    worksheets: tuple[WorksheetMetadata, ...]
    extraction_messages: tuple[str, ...]


@dataclass(frozen=True)
class MetadataReport:
    generated_utc: str
    workbook_count: int
    worksheet_count: int
    defined_name_count: int
    workbooks: tuple[WorkbookMetadata, ...]


def _read_xml(archive: zipfile.ZipFile, member: str) -> ET.Element:
    with archive.open(member) as handle:
        return ET.parse(handle).getroot()


def _relationship_targets(archive: zipfile.ZipFile) -> dict[str, str]:
    if WORKBOOK_RELS not in archive.namelist():
        return {}
    root = _read_xml(archive, WORKBOOK_RELS)
    result: dict[str, str] = {}
    for node in root:
        rel_id = node.attrib.get("Id")
        target = node.attrib.get("Target")
        if not rel_id or not target:
            continue
        target = target.replace("\\", "/")
        if target.startswith("/"):
            target = target.lstrip("/")
        elif not target.startswith("xl/"):
            target = f"xl/{target}"
        result[rel_id] = target
    return result


def _defined_names(root: ET.Element, workbook: str, family: str) -> tuple[DefinedNameRecord, ...]:
    parent = root.find(_tag("definedNames"))
    if parent is None:
        return ()
    records = []
    for node in parent.findall(_tag("definedName")):
        local = node.attrib.get("localSheetId")
        records.append(DefinedNameRecord(
            workbook=workbook,
            family_code=family,
            name=node.attrib.get("name", ""),
            refers_to=(node.text or "").strip(),
            local_sheet_id=int(local) if local is not None else None,
            hidden=node.attrib.get("hidden", "0") in {"1", "true", "True"},
        ))
    return tuple(records)


def _sheet_metadata(archive: zipfile.ZipFile, *, xml_path: str, workbook: str,
                    family: str, sheet_name: str, sheet_state: str,
                    sheet_index: int, sample_limit: int) -> WorksheetMetadata:
    dimension = None
    formula_count = merged_count = validation_count = table_count = 0
    formula_samples: list[str] = []
    merged_samples: list[str] = []
    validation_samples: list[str] = []

    with archive.open(xml_path) as handle:
        for event, elem in ET.iterparse(handle, events=("start", "end")):
            if event == "start" and elem.tag == _tag("dimension"):
                dimension = elem.attrib.get("ref")
            if event != "end":
                continue
            if elem.tag == _tag("f"):
                formula_count += 1
                if len(formula_samples) < sample_limit:
                    formula_samples.append((elem.text or "").strip())
            elif elem.tag == _tag("mergeCell"):
                merged_count += 1
                if len(merged_samples) < sample_limit:
                    merged_samples.append(elem.attrib.get("ref", ""))
            elif elem.tag == _tag("dataValidation"):
                validation_count += 1
                if len(validation_samples) < sample_limit:
                    validation_samples.append(json.dumps({
                        "type": elem.attrib.get("type"),
                        "sqref": elem.attrib.get("sqref"),
                        "operator": elem.attrib.get("operator"),
                        "allowBlank": elem.attrib.get("allowBlank"),
                    }, separators=(",", ":")))
            elif elem.tag == _tag("tablePart"):
                table_count += 1
            elem.clear()

    return WorksheetMetadata(
        workbook=workbook, family_code=family, sheet_name=sheet_name,
        sheet_state=sheet_state, sheet_index=sheet_index, xml_path=xml_path,
        dimension_reference=dimension, formula_count=formula_count,
        formula_samples=tuple(formula_samples), merged_range_count=merged_count,
        merged_range_samples=tuple(merged_samples), validation_count=validation_count,
        validation_samples=tuple(validation_samples), table_relationship_count=table_count,
    )


def extract_workbook_metadata(workbook_path: Path, family_code: str,
                              relative_path: str, sample_limit: int = 20) -> WorkbookMetadata:
    messages: list[str] = []
    with zipfile.ZipFile(workbook_path) as archive:
        names = set(archive.namelist())
        root = _read_xml(archive, WORKBOOK_XML)
        rels = _relationship_targets(archive)
        defined = _defined_names(root, workbook_path.name, family_code)
        worksheets: list[WorksheetMetadata] = []
        sheets_parent = root.find(_tag("sheets"))
        if sheets_parent is not None:
            for index, sheet in enumerate(sheets_parent.findall(_tag("sheet")), start=1):
                rel_id = sheet.attrib.get(_tag("id", NS_DOC_REL))
                xml_path = rels.get(rel_id or "", "")
                sheet_name = sheet.attrib.get("name", f"Sheet{index}")
                state = sheet.attrib.get("state", "visible")
                if not xml_path or xml_path not in names:
                    messages.append(f"Worksheet XML missing for {sheet_name} ({rel_id}).")
                    continue
                try:
                    worksheets.append(_sheet_metadata(
                        archive, xml_path=xml_path, workbook=workbook_path.name,
                        family=family_code, sheet_name=sheet_name, sheet_state=state,
                        sheet_index=index, sample_limit=sample_limit,
                    ))
                except Exception as exc:
                    messages.append(f"Metadata extraction failed for {sheet_name}: {exc}")

        external_count = sum(1 for name in names if name.startswith("xl/externalLinks/externalLink") and name.endswith(".xml"))
        return WorkbookMetadata(
            workbook=workbook_path.name, family_code=family_code,
            relative_path=relative_path,
            macro_enabled=workbook_path.suffix.casefold() in {".xlsm", ".xltm"},
            vba_project_present="xl/vbaProject.bin" in names,
            external_link_count=external_count, defined_names=defined,
            worksheets=tuple(worksheets), extraction_messages=tuple(messages),
        )


def extract_from_discovery(project_root: Path, discovery_path: Path,
                           sample_limit: int = 20) -> MetadataReport:
    discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
    workbooks = []
    for record in discovery["records"]:
        if not record.get("file_name") or record.get("discovery_status") != "discovered":
            continue
        relative = record["relative_path"]
        workbooks.append(extract_workbook_metadata(
            project_root / relative, record["family_code"], relative, sample_limit
        ))
    return MetadataReport(
        generated_utc=datetime.now(timezone.utc).isoformat(),
        workbook_count=len(workbooks),
        worksheet_count=sum(len(w.worksheets) for w in workbooks),
        defined_name_count=sum(len(w.defined_names) for w in workbooks),
        workbooks=tuple(workbooks),
    )


def save_metadata_report(report: MetadataReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(report), indent=2, ensure_ascii=False), encoding="utf-8")


def save_csv_exports(report: MetadataReport, export_directory: Path) -> None:
    export_directory.mkdir(parents=True, exist_ok=True)
    worksheet_rows = [asdict(s) for w in report.workbooks for s in w.worksheets]
    name_rows = [asdict(n) for w in report.workbooks for n in w.defined_names]
    _write_csv(export_directory / "worksheet_metadata.csv", worksheet_rows)
    _write_csv(export_directory / "defined_names.csv", name_rows)


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow({
                key: json.dumps(value, ensure_ascii=False) if isinstance(value, (tuple, list, dict)) else value
                for key, value in row.items()
            })

"""F100.5 - Fybroc Business Object Classification.

Roadmap anchor
--------------
docs/PROJECT_MASTER_ROADMAP.md, Section 6, Milestone F100
("Fybroc Source Inventory & Reconciliation").

F100.1 (FYBROC_SOURCE_FREEZE) already froze the 5 source workbooks and
their LEGACY_ACTIVE / NEW_CANDIDATE status.

F100.2 (FYBROC_STRUCTURAL_INVENTORY) already inventoried every sheet:
name, state, formula/table/data-validation counts, table names.

F100.3 / F100.4 already covered named ranges/external links/formulas
and VBA modules/procedures.

What is still open on the roadmap's own F100 "required inspection" list
is the *business-object* layer: which sheets are configuration fields,
option domains, constraints, dependencies, hierarchy, combination logic,
feasible constraints, motor constraints, nomenclature rules, identifier
mappings, pricing tables, pricing formulas, adders, testing rules, and
quote/specification mappings.

This step classifies every sheet in every one of the 5 workbooks into
that vocabulary (verbatim, from the roadmap) and produces the 5 named
F100 deliverables:

  FYBROC_SOURCE_INVENTORY          - master per-sheet catalog
  FYBROC_FIELD_INVENTORY           - configuration_fields / option_domains
  FYBROC_PRICING_SOURCE_INVENTORY  - pricing_tables / pricing_formulas / adders
  FYBROC_SOURCE_CONFLICT_REGISTER  - same tag/name across >1 workbook
                                      (flagged for F110/F120/F130, NOT resolved here)
  FYBROC_SOURCE_LINEAGE            - per-workbook rollup + F100.1 hash check

Explicitly OUT OF SCOPE for this step (per the roadmap, do not digress
into these here):
  - F110  V5 vs V6 nomenclature diff (this step only flags that both
          exist; it does not diff their contents)
  - F120  Rev0.3 configuration model (this step only classifies Rev0.3
          sheets; it does not compile items/constraints/hierarchy)
  - F130  Pricing/adders reconciliation (this step only flags pricing
          sheets exist; it does not reconcile amounts or precedence)
  - No cell values are read and no business/marker meaning is assigned.
    A sheet with zero tag matches is left NEEDS_ENGINEERING_REVIEW
    rather than guessed, consistent with the conservative posture
    already established in M023.2 / M023.3.

Inputs (must already exist - re-run F100.1/F100.2 first if missing):
  docs/evidence/F100/FYBROC_SOURCE_FREEZE.json
  docs/evidence/F100/FYBROC_STRUCTURAL_INVENTORY.json
  scripts/workbook_roles.json

Outputs:
  docs/evidence/F100/FYBROC_SOURCE_INVENTORY.{json,txt}
  docs/evidence/F100/FYBROC_FIELD_INVENTORY.{json,txt}
  docs/evidence/F100/FYBROC_PRICING_SOURCE_INVENTORY.{json,txt}
  docs/evidence/F100/FYBROC_SOURCE_CONFLICT_REGISTER.{json,txt}
  docs/evidence/F100/FYBROC_SOURCE_LINEAGE.{json,txt}

No workbook is opened or modified by this script.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STEP = "F100.5"
ROADMAP_VERSION = "1.0"
MILESTONE = "F100"

# ---------------------------------------------------------------------------
# Controlled vocabulary - taken verbatim from the roadmap's F100 "required
# inspection" list (business-object layer only; structural/VBA items are
# already covered by F100.2/F100.3/F100.4).
# ---------------------------------------------------------------------------
TAGS = [
    "configuration_fields",
    "option_domains",
    "constraints",
    "dependencies",
    "hierarchy",
    "combination_logic",
    "feasible_constraints",
    "motor_constraints",
    "nomenclature_rules",
    "identifier_mappings",
    "pricing_tables",
    "pricing_formulas",
    "adders",
    "testing_rules",
    "quote_specification_mappings",
]

# Tags that make a sheet part of FYBROC_FIELD_INVENTORY / FYBROC_PRICING_SOURCE_INVENTORY.
FIELD_TAGS = {"configuration_fields", "option_domains"}
PRICING_TAGS = {"pricing_tables", "pricing_formulas", "adders"}

CONFIDENCE_ESTABLISHED = "ESTABLISHED"
CONFIDENCE_HEURISTIC = "HEURISTIC"
CONFIDENCE_NONE = "NONE"

# ---------------------------------------------------------------------------
# ESTABLISHED tier, source 1: scripts/workbook_roles.json "authoritative_sheets".
# These role strings were already engineering-established by earlier
# milestones (M009-M013). We only translate them into the roadmap's F100
# vocabulary; we do not re-derive them.
# ---------------------------------------------------------------------------
ROLE_STRING_TAGS: dict[str, list[str]] = {
    "series_constraint_definitions": ["constraints"],
    "allowed_and_disallowed_configurations": ["option_domains", "configuration_fields"],
    "ordered_dynamic_configuration_workflow": ["configuration_fields", "hierarchy"],
    "attribute_hex_mapping": ["nomenclature_rules", "identifier_mappings", "configuration_fields"],
    "pump_option_hex_mapping": [
        "nomenclature_rules",
        "identifier_mappings",
        "option_domains",
        "configuration_fields",
    ],
    "seal_assembly_hex_mapping": ["nomenclature_rules", "identifier_mappings", "configuration_fields"],
    "option_hex_mapping": ["nomenclature_rules", "identifier_mappings", "option_domains"],
    "motor_assembly_hex_mapping": ["nomenclature_rules", "identifier_mappings", "motor_constraints"],
    "fybroc_configuration_pricing": ["pricing_tables", "pricing_formulas"],
    "horizontal_specification_output": ["quote_specification_mappings"],
    "vertical_specification_output": ["quote_specification_mappings"],
    "fybroc_customer_quote_template": ["quote_specification_mappings"],
    "selection_to_datasheet_mapping": ["quote_specification_mappings", "configuration_fields"],
}

# ---------------------------------------------------------------------------
# ESTABLISHED tier, source 2: facts stated directly in a milestone doc but not
# (yet) mirrored into workbook_roles.json. Keyed by
# (workbook file_name, normalized sheet name).
# ---------------------------------------------------------------------------
MILESTONE_KNOWN: dict[tuple[str, str], tuple[list[str], str]] = {
    ("Fybroc Attributes and Constraints.xlsx", "main"): (
        ["constraints"],
        "docs/milestones/M013-Fybroc-Series-Constraint-Matrix.md "
        "(\"MAIN is the authoritative applicability matrix\")",
    ),
    ("Fybroc Attributes and Constraints.xlsx", "full list"): (
        ["option_domains", "configuration_fields"],
        "docs/milestones/M013-Fybroc-Series-Constraint-Matrix.md "
        "(\"FULL LIST is a collection of per-field allowed-value columns\")",
    ),
    # F100.5.1 correction: these 7 sheets are each one series' detailed
    # configuration breakdown; MAIN is the consolidated overall-series view
    # built on top of them (MAIN's own CONCAT/INDIRECT formulas reference
    # these sheets by name). Not leftover/orphaned sheets.
    ("Fybroc Attributes and Constraints.xlsx", "1500"): (
        ["constraints", "configuration_fields"],
        "docs/milestones/F100_5_1_SERIES_SHEET_CLASSIFICATION_CORRECTION.md",
    ),
    ("Fybroc Attributes and Constraints.xlsx", "1530"): (
        ["constraints", "configuration_fields"],
        "docs/milestones/F100_5_1_SERIES_SHEET_CLASSIFICATION_CORRECTION.md",
    ),
    ("Fybroc Attributes and Constraints.xlsx", "1600"): (
        ["constraints", "configuration_fields"],
        "docs/milestones/F100_5_1_SERIES_SHEET_CLASSIFICATION_CORRECTION.md",
    ),
    ("Fybroc Attributes and Constraints.xlsx", "1630"): (
        ["constraints", "configuration_fields"],
        "docs/milestones/F100_5_1_SERIES_SHEET_CLASSIFICATION_CORRECTION.md",
    ),
    ("Fybroc Attributes and Constraints.xlsx", "2530"): (
        ["constraints", "configuration_fields"],
        "docs/milestones/F100_5_1_SERIES_SHEET_CLASSIFICATION_CORRECTION.md",
    ),
    ("Fybroc Attributes and Constraints.xlsx", "3000"): (
        ["constraints", "configuration_fields"],
        "docs/milestones/F100_5_1_SERIES_SHEET_CLASSIFICATION_CORRECTION.md",
    ),
    ("Fybroc Attributes and Constraints.xlsx", "5500"): (
        ["constraints", "configuration_fields"],
        "docs/milestones/F100_5_1_SERIES_SHEET_CLASSIFICATION_CORRECTION.md",
    ),
    ("Price Estimator-Fybroc.xlsm", "newrules 5 2 23"): (
        ["dependencies"],
        "docs/milestones/F100_5_2_NEWRULES_CLASSIFICATION_CORRECTION.md "
        "(confirmed via cfg.FieldOptionDependency.SourceWorksheet in the "
        "live active metadata publication)",
    ),
}

# ---------------------------------------------------------------------------
# HEURISTIC tier: keyword match against normalized sheet name + table names.
# Order does not matter - all matching tags are collected, not "first wins".
# Keep entries specific; a bare short token (e.g. a single letter) is
# deliberately excluded to avoid false positives.
# ---------------------------------------------------------------------------
KEYWORD_TAGS: list[tuple[str, list[str]]] = [
    ("feasible_constraints", ["feasible"]),
    ("motor_constraints", ["motor", "teco", "baldor", "toshiba"]),
    ("dependencies", ["depend", "codepend"]),
    ("constraints", ["constraint", "applicab", "allowed"]),
    ("hierarchy", ["hierarchy"]),
    ("combination_logic", ["combine", "combination"]),
    ("nomenclature_rules", ["nomenclature", "smart number", "hex"]),
    ("identifier_mappings", ["identifier", "part number", "sku", "smart number"]),
    ("pricing_tables", ["price", "pricing", "pricebook", "rom data"]),
    ("adders", ["adder"]),
    ("testing_rules", ["test"]),
    (
        "quote_specification_mappings",
        ["quote", "spec", "datasheet", "nameplate", "plaintag", "formal"],
    ),
    (
        "configuration_fields",
        [
            "option", "attribute", "material", "trim", "seal", "impeller",
            "baseplate", "coupling", "size", "series", "mod", "aux", "item",
            "setting",
        ],
    ),
    ("option_domains", ["option", "selection", "attribute"]),
]


def normalize(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def compact(text: str) -> str:
    """Whitespace-insensitive key, so config entries like 'SmartNumber' still
    match an actual sheet named 'Smart Number'."""
    return normalize(text).replace(" ", "")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(
            f"Required input is missing: {path}\n"
            f"Run the earlier F100 steps first (F100.1 source freeze, "
            f"F100.2 structural inventory) before running {STEP}."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def git_info(repo_root: Path) -> tuple[str, bool]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True,
            text=True, check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=repo_root, capture_output=True,
            text=True, check=True,
        ).stdout
        return commit, (status.strip() == "")
    except Exception:
        return "unknown", False


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_authoritative_sheets(workbook_roles_path: Path) -> dict[str, dict[str, str]]:
    """file_name -> {compact_sheet_name: role_string}

    Keyed by the whitespace-insensitive 'compact' form because
    workbook_roles.json spells some sheets without spaces (e.g.
    "SmartNumber") while the actual workbook sheet is "Smart Number".
    """
    if not workbook_roles_path.exists():
        return {}
    data = json.loads(workbook_roles_path.read_text(encoding="utf-8"))
    result: dict[str, dict[str, str]] = {}
    for family in data.get("families", {}).values():
        for file_name, wb in family.get("workbooks", {}).items():
            sheets = wb.get("authoritative_sheets", {})
            result[file_name] = {compact(k): v for k, v in sheets.items()}
    return result


def classify_sheet(
    file_name: str,
    sheet_name: str,
    table_names: list[str],
    known_sheets: dict[str, str],
) -> tuple[list[str], str, str]:
    norm_sheet = normalize(sheet_name)
    compact_sheet = compact(sheet_name)

    # Tier 1: milestone-established fact. Matched whitespace-insensitively
    # since MILESTONE_KNOWN keys are hand-typed and may not byte-match an
    # actual worksheet name (e.g. trailing/leading space quirks in Excel).
    for (known_file, known_sheet_name), (tags, citation) in MILESTONE_KNOWN.items():
        if known_file == file_name and compact(known_sheet_name) == compact_sheet:
            return sorted(set(tags)), CONFIDENCE_ESTABLISHED, citation

    # Tier 2: workbook_roles.json authoritative_sheets. Matched
    # whitespace-insensitively because the config spells some sheets without
    # spaces (e.g. "SmartNumber") while the workbook sheet is "Smart Number".
    role_string = known_sheets.get(compact_sheet)
    if role_string and role_string in ROLE_STRING_TAGS:
        return (
            sorted(set(ROLE_STRING_TAGS[role_string])),
            CONFIDENCE_ESTABLISHED,
            f"scripts/workbook_roles.json (role: {role_string})",
        )

    # Tier 3: keyword heuristic over sheet name + table names.
    haystack = " ".join([norm_sheet] + [normalize(t) for t in table_names])
    matched_tags: set[str] = set()
    matched_keywords: set[str] = set()
    for tag, keywords in KEYWORD_TAGS:
        for kw in keywords:
            if kw in haystack:
                matched_tags.add(tag)
                matched_keywords.add(kw)

    # "$" is a meaningful pricing/cost signal but normalize() strips
    # punctuation, so it is checked against the raw sheet name separately.
    if "$" in sheet_name:
        matched_tags.add("pricing_tables")
        matched_keywords.add("$ in sheet name")

    if matched_tags:
        basis = "keyword match: " + ", ".join(sorted(matched_keywords))
        return sorted(matched_tags), CONFIDENCE_HEURISTIC, basis

    # Tier 4: nothing matched.
    return [], CONFIDENCE_NONE, "no established mapping or keyword match"


def build_inventory(repo_root: Path, evidence_dir: Path, workbook_roles_path: Path) -> dict[str, Any]:
    freeze = load_json(evidence_dir / "FYBROC_SOURCE_FREEZE.json")
    structural = load_json(evidence_dir / "FYBROC_STRUCTURAL_INVENTORY.json")
    known_by_workbook = load_authoritative_sheets(workbook_roles_path)

    freeze_by_name = {s["file_name"]: s for s in freeze.get("sources", [])}
    structural_by_name = {w["file_name"]: w for w in structural.get("workbooks", [])}

    commit, clean = git_info(repo_root)
    generated = datetime.now(timezone.utc).isoformat()

    sources_out: list[dict[str, Any]] = []
    tag_index: dict[str, list[dict[str, str]]] = {tag: [] for tag in TAGS}
    name_index: dict[str, list[dict[str, str]]] = {}

    total_sheets = 0
    classified_sheets = 0

    file_order = [w["file_name"] for w in structural.get("workbooks", [])]

    for file_name in file_order:
        freeze_row = freeze_by_name.get(file_name, {})
        struct_row = structural_by_name.get(file_name, {})
        status = freeze_row.get("source_generation", "UNKNOWN")
        role = freeze_row.get("role", struct_row.get("role", "unknown"))
        frozen_sha256 = freeze_row.get("sha256")

        relative_path = freeze_row.get("relative_path")
        recomputed_sha256 = None
        sha256_match: bool | None = None
        if relative_path:
            # F100.1 recorded this with Windows-style backslashes; normalize
            # so the path resolves the same on any host.
            wb_path = repo_root / relative_path.replace("\\", "/")
            recomputed_sha256 = sha256_file(wb_path)
            if recomputed_sha256 is not None and frozen_sha256 is not None:
                sha256_match = recomputed_sha256 == frozen_sha256

        known_sheets = known_by_workbook.get(file_name, {})

        sheets_out: list[dict[str, Any]] = []
        for sheet in struct_row.get("sheets", []):
            sheet_name = sheet.get("sheet_name", "")
            table_names = [t.get("name", "") for t in sheet.get("tables", []) if t.get("name")]
            tags, confidence, basis = classify_sheet(file_name, sheet_name, table_names, known_sheets)

            total_sheets += 1
            if tags:
                classified_sheets += 1

            row = {
                "workbook": file_name,
                "source_generation": status,
                "sheet_name": sheet_name,
                "sheet_state": sheet.get("sheet_state", "visible"),
                "formula_count": sheet.get("formula_count", 0),
                "table_count": sheet.get("table_count", 0),
                "table_names": table_names,
                "tags": tags,
                "confidence": confidence,
                "basis": basis,
            }
            sheets_out.append(row)

            for tag in tags:
                tag_index[tag].append(
                    {"workbook": file_name, "source_generation": status, "sheet_name": sheet_name}
                )

            norm_name = normalize(sheet_name)
            name_index.setdefault(norm_name, []).append(
                {
                    "workbook": file_name,
                    "source_generation": status,
                    "sheet_name": sheet_name,
                    "formula_count": sheet.get("formula_count", 0),
                    "table_count": sheet.get("table_count", 0),
                }
            )

        sources_out.append(
            {
                "file_name": file_name,
                "source_generation": status,
                "role": role,
                "sha256_frozen_f100_1": frozen_sha256,
                "sha256_recomputed": recomputed_sha256,
                "sha256_matches_f100_1_freeze": sha256_match,
                "sheet_count": len(sheets_out),
                "classified_sheet_count": sum(1 for s in sheets_out if s["tags"]),
                "needs_review_sheet_count": sum(1 for s in sheets_out if not s["tags"]),
                "sheets": sheets_out,
            }
        )

    # --- Conflict register -------------------------------------------------
    conflicts: list[dict[str, Any]] = []

    # (a) Same tag present in both a LEGACY_ACTIVE and a NEW_CANDIDATE workbook.
    for tag, entries in tag_index.items():
        legacy = [e for e in entries if e["source_generation"] == "LEGACY_ACTIVE"]
        candidate = [e for e in entries if e["source_generation"] == "NEW_CANDIDATE"]
        if legacy and candidate:
            conflicts.append(
                {
                    "conflict_type": "TAG_PRESENT_IN_LEGACY_AND_CANDIDATE",
                    "tag": tag,
                    "legacy_active": legacy,
                    "new_candidate": candidate,
                    "note": (
                        "Same business-object category exists in both a "
                        "LEGACY_ACTIVE and a NEW_CANDIDATE workbook. Reconcile "
                        "in F110/F120/F130 - not resolved by F100."
                    ),
                }
            )

    # (b) Same normalized sheet name across 2+ different workbooks.
    for norm_name, entries in name_index.items():
        distinct_workbooks = {e["workbook"] for e in entries}
        if len(distinct_workbooks) > 1:
            conflicts.append(
                {
                    "conflict_type": "SAME_SHEET_NAME_ACROSS_WORKBOOKS",
                    "normalized_sheet_name": norm_name,
                    "occurrences": entries,
                    "note": (
                        "The same sheet name appears in more than one "
                        "workbook. Structural shape (formula/table counts) "
                        "may differ - reconcile in F110/F120, not resolved "
                        "by F100."
                    ),
                }
            )

    result = {
        "step": STEP,
        "roadmap_version": ROADMAP_VERSION,
        "milestone": MILESTONE,
        "generated_utc": generated,
        "git_commit": commit,
        "git_working_tree_clean": clean,
        "source_count": len(sources_out),
        "total_sheet_count": total_sheets,
        "classified_sheet_count": classified_sheets,
        "needs_review_sheet_count": total_sheets - classified_sheets,
        "sources": sources_out,
        "conflicts": conflicts,
    }
    return result


# ---------------------------------------------------------------------------
# Output writers - one JSON + one human-readable TXT per named deliverable.
# ---------------------------------------------------------------------------

def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _banner(title: str) -> str:
    line = "=" * 140
    return f"{line}\r\n{title}\r\n{line}\r\n\r\n"


def write_source_inventory(evidence_dir: Path, inventory: dict[str, Any]) -> None:
    payload = {
        "artifact": "FYBROC_SOURCE_INVENTORY",
        "roadmap_version": ROADMAP_VERSION,
        "milestone": MILESTONE,
        "step": STEP,
        "generated_utc": inventory["generated_utc"],
        "git_commit": inventory["git_commit"],
        "git_working_tree_clean": inventory["git_working_tree_clean"],
        "source_count": inventory["source_count"],
        "total_sheet_count": inventory["total_sheet_count"],
        "classified_sheet_count": inventory["classified_sheet_count"],
        "needs_review_sheet_count": inventory["needs_review_sheet_count"],
        "sources": [
            {
                "file_name": s["file_name"],
                "source_generation": s["source_generation"],
                "role": s["role"],
                "sheet_count": s["sheet_count"],
                "classified_sheet_count": s["classified_sheet_count"],
                "needs_review_sheet_count": s["needs_review_sheet_count"],
                "sheets": s["sheets"],
            }
            for s in inventory["sources"]
        ],
    }
    _write_json(evidence_dir / "FYBROC_SOURCE_INVENTORY.json", payload)

    lines = [_banner("F100.5 - FYBROC SOURCE INVENTORY (business-object classification)")]
    lines.append(
        f"Git commit               : {inventory['git_commit']}\r\n"
        f"Git clean                : {inventory['git_working_tree_clean']}\r\n"
        f"Workbooks                : {inventory['source_count']}\r\n"
        f"Total sheets             : {inventory['total_sheet_count']}\r\n"
        f"Classified sheets        : {inventory['classified_sheet_count']}\r\n"
        f"Needs engineering review : {inventory['needs_review_sheet_count']}\r\n\r\n"
    )
    for s in inventory["sources"]:
        lines.append(_banner(s["file_name"]))
        lines.append(
            f"Generation : {s['source_generation']}\r\n"
            f"Role       : {s['role']}\r\n"
            f"Sheets     : {s['sheet_count']}   "
            f"Classified : {s['classified_sheet_count']}   "
            f"Needs review : {s['needs_review_sheet_count']}\r\n\r\n"
        )
        lines.append(
            f"{'SHEET':<28}{'STATE':<10}{'CONFIDENCE':<13}{'TAGS'}\r\n"
            + "-" * 140 + "\r\n"
        )
        for sh in s["sheets"]:
            tags_display = ", ".join(sh["tags"]) if sh["tags"] else "(NEEDS_ENGINEERING_REVIEW)"
            lines.append(
                f"{sh['sheet_name']:<28}{sh['sheet_state']:<10}{sh['confidence']:<13}{tags_display}\r\n"
                f"{'':<28}{'':<10}{'':<13}basis: {sh['basis']}\r\n"
            )
        lines.append("\r\n")
    (evidence_dir / "FYBROC_SOURCE_INVENTORY.txt").write_text("".join(lines), encoding="utf-8")


def write_field_inventory(evidence_dir: Path, inventory: dict[str, Any]) -> None:
    rows = []
    for s in inventory["sources"]:
        for sh in s["sheets"]:
            if FIELD_TAGS.intersection(sh["tags"]):
                rows.append(
                    {
                        "workbook": s["file_name"],
                        "source_generation": s["source_generation"],
                        "sheet_name": sh["sheet_name"],
                        "tags": sh["tags"],
                        "confidence": sh["confidence"],
                        "basis": sh["basis"],
                        "table_names": sh["table_names"],
                    }
                )
    payload = {
        "artifact": "FYBROC_FIELD_INVENTORY",
        "roadmap_version": ROADMAP_VERSION,
        "milestone": MILESTONE,
        "step": STEP,
        "generated_utc": inventory["generated_utc"],
        "git_commit": inventory["git_commit"],
        "row_count": len(rows),
        "rows": rows,
    }
    _write_json(evidence_dir / "FYBROC_FIELD_INVENTORY.json", payload)

    lines = [_banner("F100.5 - FYBROC FIELD INVENTORY (configuration_fields / option_domains)")]
    lines.append(f"Rows : {len(rows)}\r\n\r\n")
    for r in rows:
        lines.append(
            f"{r['workbook']} [{r['source_generation']}] :: {r['sheet_name']}\r\n"
            f"    tags  : {', '.join(r['tags'])}\r\n"
            f"    basis : {r['basis']}\r\n"
        )
    (evidence_dir / "FYBROC_FIELD_INVENTORY.txt").write_text("".join(lines), encoding="utf-8")


def write_pricing_inventory(evidence_dir: Path, inventory: dict[str, Any]) -> None:
    rows = []
    for s in inventory["sources"]:
        for sh in s["sheets"]:
            if PRICING_TAGS.intersection(sh["tags"]):
                rows.append(
                    {
                        "workbook": s["file_name"],
                        "source_generation": s["source_generation"],
                        "sheet_name": sh["sheet_name"],
                        "tags": sh["tags"],
                        "confidence": sh["confidence"],
                        "basis": sh["basis"],
                        "formula_count": sh["formula_count"],
                        "table_names": sh["table_names"],
                    }
                )
    payload = {
        "artifact": "FYBROC_PRICING_SOURCE_INVENTORY",
        "roadmap_version": ROADMAP_VERSION,
        "milestone": MILESTONE,
        "step": STEP,
        "generated_utc": inventory["generated_utc"],
        "git_commit": inventory["git_commit"],
        "row_count": len(rows),
        "rows": rows,
    }
    _write_json(evidence_dir / "FYBROC_PRICING_SOURCE_INVENTORY.json", payload)

    lines = [_banner("F100.5 - FYBROC PRICING SOURCE INVENTORY (pricing_tables / pricing_formulas / adders)")]
    lines.append(f"Rows : {len(rows)}\r\n\r\n")
    for r in rows:
        lines.append(
            f"{r['workbook']} [{r['source_generation']}] :: {r['sheet_name']}\r\n"
            f"    tags     : {', '.join(r['tags'])}\r\n"
            f"    formulas : {r['formula_count']}\r\n"
            f"    basis    : {r['basis']}\r\n"
        )
    (evidence_dir / "FYBROC_PRICING_SOURCE_INVENTORY.txt").write_text("".join(lines), encoding="utf-8")


def write_conflict_register(evidence_dir: Path, inventory: dict[str, Any]) -> None:
    conflicts = inventory["conflicts"]
    payload = {
        "artifact": "FYBROC_SOURCE_CONFLICT_REGISTER",
        "roadmap_version": ROADMAP_VERSION,
        "milestone": MILESTONE,
        "step": STEP,
        "generated_utc": inventory["generated_utc"],
        "git_commit": inventory["git_commit"],
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
    }
    _write_json(evidence_dir / "FYBROC_SOURCE_CONFLICT_REGISTER.json", payload)

    lines = [_banner("F100.5 - FYBROC SOURCE CONFLICT REGISTER (flagged, not resolved)")]
    lines.append(f"Conflict candidates : {len(conflicts)}\r\n\r\n")
    for c in conflicts:
        if c["conflict_type"] == "TAG_PRESENT_IN_LEGACY_AND_CANDIDATE":
            lines.append(f"[TAG] {c['tag']}\r\n")
            for e in c["legacy_active"]:
                lines.append(f"    LEGACY_ACTIVE  : {e['workbook']} :: {e['sheet_name']}\r\n")
            for e in c["new_candidate"]:
                lines.append(f"    NEW_CANDIDATE  : {e['workbook']} :: {e['sheet_name']}\r\n")
        else:
            lines.append(f"[SHEET NAME] {c['normalized_sheet_name']}\r\n")
            for e in c["occurrences"]:
                lines.append(
                    f"    {e['workbook']} [{e['source_generation']}] :: {e['sheet_name']}  "
                    f"(formulas={e['formula_count']}, tables={e['table_count']})\r\n"
                )
        lines.append(f"    note: {c['note']}\r\n\r\n")
    (evidence_dir / "FYBROC_SOURCE_CONFLICT_REGISTER.txt").write_text("".join(lines), encoding="utf-8")


def write_lineage(evidence_dir: Path, inventory: dict[str, Any]) -> None:
    rows = []
    for s in inventory["sources"]:
        tag_counts: dict[str, int] = {tag: 0 for tag in TAGS}
        for sh in s["sheets"]:
            for tag in sh["tags"]:
                tag_counts[tag] += 1
        rows.append(
            {
                "file_name": s["file_name"],
                "source_generation": s["source_generation"],
                "role": s["role"],
                "sha256_frozen_f100_1": s["sha256_frozen_f100_1"],
                "sha256_recomputed": s["sha256_recomputed"],
                "sha256_matches_f100_1_freeze": s["sha256_matches_f100_1_freeze"],
                "sheet_count": s["sheet_count"],
                "classified_sheet_count": s["classified_sheet_count"],
                "needs_review_sheet_count": s["needs_review_sheet_count"],
                "tag_counts": tag_counts,
            }
        )
    payload = {
        "artifact": "FYBROC_SOURCE_LINEAGE",
        "roadmap_version": ROADMAP_VERSION,
        "milestone": MILESTONE,
        "step": STEP,
        "generated_utc": inventory["generated_utc"],
        "git_commit": inventory["git_commit"],
        "sources": rows,
    }
    _write_json(evidence_dir / "FYBROC_SOURCE_LINEAGE.json", payload)

    lines = [_banner("F100.5 - FYBROC SOURCE LINEAGE")]
    for r in rows:
        integrity = (
            "MATCH" if r["sha256_matches_f100_1_freeze"] is True
            else "MISMATCH - INVESTIGATE" if r["sha256_matches_f100_1_freeze"] is False
            else "NOT CHECKED"
        )
        lines.append(_banner(r["file_name"]))
        lines.append(
            f"Generation      : {r['source_generation']}\r\n"
            f"Role            : {r['role']}\r\n"
            f"F100.1 hash     : {integrity}\r\n"
            f"Sheets          : {r['sheet_count']}  "
            f"Classified: {r['classified_sheet_count']}  "
            f"Needs review: {r['needs_review_sheet_count']}\r\n"
        )
        nonzero = {k: v for k, v in r["tag_counts"].items() if v}
        if nonzero:
            lines.append("Tag counts      :\r\n")
            for tag, count in nonzero.items():
                lines.append(f"    {tag:<28}: {count}\r\n")
        lines.append("\r\n")
    (evidence_dir / "FYBROC_SOURCE_LINEAGE.txt").write_text("".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="F100.5 Fybroc business-object classification")
    default_root = Path(__file__).resolve().parent.parent
    parser.add_argument("--repo-root", type=Path, default=default_root)
    parser.add_argument(
        "--evidence-dir", type=Path, default=None,
        help="defaults to <repo-root>/docs/evidence/F100",
    )
    parser.add_argument(
        "--workbook-roles", type=Path, default=None,
        help="defaults to <repo-root>/scripts/workbook_roles.json",
    )
    args = parser.parse_args()

    repo_root: Path = args.repo_root.resolve()
    evidence_dir: Path = (args.evidence_dir or (repo_root / "docs" / "evidence" / "F100")).resolve()
    workbook_roles_path: Path = (args.workbook_roles or (repo_root / "scripts" / "workbook_roles.json")).resolve()

    inventory = build_inventory(repo_root, evidence_dir, workbook_roles_path)

    write_source_inventory(evidence_dir, inventory)
    write_field_inventory(evidence_dir, inventory)
    write_pricing_inventory(evidence_dir, inventory)
    write_conflict_register(evidence_dir, inventory)
    write_lineage(evidence_dir, inventory)

    summary = {
        "step": STEP,
        "output_dir": str(evidence_dir),
        "source_count": inventory["source_count"],
        "total_sheet_count": inventory["total_sheet_count"],
        "classified_sheet_count": inventory["classified_sheet_count"],
        "needs_review_sheet_count": inventory["needs_review_sheet_count"],
        "conflict_count": len(inventory["conflicts"]),
        "hash_mismatches": [
            s["file_name"] for s in inventory["sources"]
            if s["sha256_matches_f100_1_freeze"] is False
        ],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
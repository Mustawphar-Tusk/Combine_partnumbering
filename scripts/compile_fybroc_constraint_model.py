"""F120.3 - Fybroc Rev0.3 Constraint Model Compiler.

Roadmap anchor
--------------
docs/PROJECT_MASTER_ROADMAP.md, Section 6, Milestone F120
("Fybroc Rev0.3 Configuration Model") - "Constraints", "Constraint Index",
"Feasible Constraints" from the required sources.

Two distinct structures are compiled here:

1. COMBINATION MATRIX (Constraints sheet, rows 5-39)
   A 34-field × 34-field pairwise combination grid. Each row is one
   "target" field; cols 4-5 are the two context fields (list1, list2);
   cols 6-13 are series codes (1500..5530); col 17 is the Combination?
   verdict; col 18 is the answer/table reference. The grid also carries
   per-size applicability in cols 47+ (size codes mapped to the field row).

2. CONSTRAINT INDEX (Constraint Index sheet, rows 3-27)
   21 named constraint entries, each with: Option1, Option2, Option3,
   TableName, Description. Entries without a TableName are series-
   derived rules (documented but not a resolved lookup table).

3. FEASIBLE CONSTRAINTS (Feasible Constraints sheet)
   The actual constraint lookup tables (ConstraintTable1, 4, 5, 7, 8,
   9, 10, 12, 16, 18, 19, 20, 21, 22, 23, 24, 25, 27, 28, 29).
   Each table block starts with a header in row 4 and column headers
   in row 5. Data runs from row 6 until the column block empties.
   The column width of each block is determined by the number of
   header columns in row 5.

FYBROC_CONSTRAINT_MODEL.json is the output consumed by:
  - compile_fybroc_impellertrim_dependency_diff.py  (F120.5c)
  - future FYBROC_CONSTRAINT_DIFF, FYBROC_DEPENDENCY_DIFF steps

No workbook is opened in write mode. Nothing is written back.

Inputs:
  workbooks/Fybroc/Fybroc Configuration Rev0.3.xlsx  (read-only)

Outputs:
  docs/evidence/F120/FYBROC_CONSTRAINT_MODEL.{json,txt}
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import openpyxl
except ImportError as exc:
    raise SystemExit(
        "openpyxl is required - run with the project's own .venv interpreter."
    ) from exc

STEP = "F120.3"
ROADMAP_VERSION = "1.0"
MILESTONE = "F120"
WORKBOOK_REL = "workbooks/Fybroc/Fybroc Configuration Rev0.3.xlsx"

# Constraints sheet layout constants
CONSTRAINTS_HEADER_ROW = 5
CONSTRAINTS_DATA_START = 6
CONSTRAINTS_DATA_END = 39          # 34 field rows (rows 6-39)
COL_FIELD = 2                      # target field name
COL_LIST1 = 4                      # context field 1
COL_LIST2 = 5                      # context field 2
COL_SERIES_START = 6               # 1500
COL_SERIES_END = 13                # 5530 (8 series)
COL_ANY_YES = 14
COL_ALL_NO = 15
COL_IGNORE = 16
COL_COMBINATION = 17               # Combination? verdict
COL_ANSWER = 18                    # answer / table reference
COL_SIZES_START = 47               # Alt_Size codes start here

# Constraint Index sheet layout
CI_HEADER_ROW = 5                  # Option1 / Option2 / Option3 / Table Name / Description
CI_DATA_START = 6
CI_COL_OPT1 = 3
CI_COL_OPT2 = 4
CI_COL_OPT3 = 5
CI_COL_TABLE = 6
CI_COL_DESC = 7

# Feasible Constraints sheet layout
FC_TABLE_NAME_ROW = 4              # table names
FC_HEADER_ROW = 5                  # column headers for each table block
FC_DATA_START = 6


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


def _str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


# ---------------------------------------------------------------------------
# Section 1 – Combination Matrix
# ---------------------------------------------------------------------------

def compile_combination_matrix(ws_constraints) -> dict[str, Any]:
    """Compile the 34-field pairwise combination grid from the Constraints sheet."""

    # Read series column headers (row 5, cols 6-13)
    series_codes = []
    for c in range(COL_SERIES_START, COL_SERIES_END + 1):
        v = _str(ws_constraints.cell(row=CONSTRAINTS_HEADER_ROW, column=c).value)
        if v:
            series_codes.append(v)

    # Read size codes from first data row (row 6), cols 47+
    size_codes = []
    for c in range(COL_SIZES_START, ws_constraints.max_column + 1):
        v = ws_constraints.cell(row=CONSTRAINTS_DATA_START, column=c).value
        if v is None:
            break
        s = str(v).strip()
        if s and s != "#VALUE!":
            size_codes.append(s)

    # Build per-field size applicability map: for each field row,
    # which Alt_Size codes does this field apply to?
    # Each cell in cols 47+ tells us the size code if that field applies to it.
    # The size code in each column is constant (read from row 6 as the reference row).
    # For each field row, the cell value is the size code if applicable, or blank/#VALUE!.
    size_col_map: dict[int, str] = {}  # col -> size_code (from row 6)
    for i, size in enumerate(size_codes):
        size_col_map[COL_SIZES_START + i] = size

    rows = []
    for r in range(CONSTRAINTS_DATA_START, CONSTRAINTS_DATA_END + 1):
        field = _str(ws_constraints.cell(row=r, column=COL_FIELD).value)
        if not field:
            continue

        list1 = _str(ws_constraints.cell(row=r, column=COL_LIST1).value)
        list2 = _str(ws_constraints.cell(row=r, column=COL_LIST2).value)

        # Per-series verdicts
        series_verdicts: dict[str, str] = {}
        for i, series in enumerate(series_codes):
            v = _str(ws_constraints.cell(row=r, column=COL_SERIES_START + i).value)
            series_verdicts[series] = v or ""

        any_yes = _str(ws_constraints.cell(row=r, column=COL_ANY_YES).value)
        all_no = _str(ws_constraints.cell(row=r, column=COL_ALL_NO).value)
        ignore = _str(ws_constraints.cell(row=r, column=COL_IGNORE).value)
        combination = _str(ws_constraints.cell(row=r, column=COL_COMBINATION).value)
        answer = _str(ws_constraints.cell(row=r, column=COL_ANSWER).value)

        # Applicable sizes: cells in cols 47+ where the cell value is not None/#VALUE!
        applicable_sizes = []
        for col, size_code in size_col_map.items():
            v = ws_constraints.cell(row=r, column=col).value
            if v is not None and str(v).strip() not in ("#VALUE!", ""):
                applicable_sizes.append(size_code)

        rows.append({
            "field": field,
            "list1": list1,
            "list2": list2,
            "series_verdicts": series_verdicts,
            "any_yes": any_yes,
            "all_no_combination": all_no,
            "ignore_combination": ignore,
            "combination_verdict": combination,
            "answer_ref": answer,
            "applicable_sizes": applicable_sizes,
        })

    return {
        "series_codes": series_codes,
        "size_codes": size_codes,
        "field_count": len(rows),
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# Section 2 – Constraint Index
# ---------------------------------------------------------------------------

def compile_constraint_index(ws_ci) -> list[dict[str, Any]]:
    """Compile the named constraint entries from the Constraint Index sheet."""
    entries = []
    for r in range(CI_DATA_START, ws_ci.max_row + 1):
        opt1 = _str(ws_ci.cell(row=r, column=CI_COL_OPT1).value)
        opt2 = _str(ws_ci.cell(row=r, column=CI_COL_OPT2).value)
        if not opt1 and not opt2:
            break
        entries.append({
            "option1": opt1,
            "option2": opt2,
            "option3": _str(ws_ci.cell(row=r, column=CI_COL_OPT3).value),
            "table_name": _str(ws_ci.cell(row=r, column=CI_COL_TABLE).value),
            "description": _str(ws_ci.cell(row=r, column=CI_COL_DESC).value),
            "resolved_table": None,  # filled in by Section 3
        })
    return entries


# ---------------------------------------------------------------------------
# Section 3 – Feasible Constraints (lookup tables)
# ---------------------------------------------------------------------------

def compile_feasible_constraints(ws_fc) -> dict[str, dict[str, Any]]:
    """
    Compile all ConstraintTable blocks from the Feasible Constraints sheet.

    Returns a dict keyed by table_name -> {headers, rows}.
    Each table block in row 4 anchors a column group.
    Row 5 contains column headers for that group.
    Data runs from row 6 until all columns in the group are None.
    """
    # Find all table name anchors in row 4
    table_anchors: list[tuple[int, str]] = []
    for c in range(1, ws_fc.max_column + 1):
        v = _str(ws_fc.cell(row=FC_TABLE_NAME_ROW, column=c).value)
        if v and v.startswith("ConstraintTable"):
            table_anchors.append((c, v))

    tables: dict[str, dict[str, Any]] = {}

    for idx, (start_col, table_name) in enumerate(table_anchors):
        # Determine the end column: next anchor - 1, or max_column
        end_col = (table_anchors[idx + 1][0] - 1
                   if idx + 1 < len(table_anchors)
                   else ws_fc.max_column)

        # Read column headers from row 5
        headers = []
        for c in range(start_col, end_col + 1):
            h = _str(ws_fc.cell(row=FC_HEADER_ROW, column=c).value)
            if h:
                headers.append((c, h))
            else:
                break  # headers are contiguous

        if not headers:
            continue

        header_cols = [c for c, _ in headers]
        header_names = [h for _, h in headers]

        # Read data rows
        data_rows = []
        for r in range(FC_DATA_START, ws_fc.max_row + 1):
            row_vals = [_str(ws_fc.cell(row=r, column=c).value) for c in header_cols]
            if all(v is None for v in row_vals):
                break
            if any(v is not None for v in row_vals):
                data_rows.append(dict(zip(header_names, row_vals)))

        tables[table_name] = {
            "start_col": start_col,
            "headers": header_names,
            "row_count": len(data_rows),
            "rows": data_rows,
        }

    return tables


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_model(repo_root: Path) -> dict[str, Any]:
    commit, clean = git_info(repo_root)

    wb = openpyxl.load_workbook(
        str(repo_root / WORKBOOK_REL), read_only=True, data_only=True
    )

    combination_matrix = compile_combination_matrix(wb["Constraints"])
    constraint_index = compile_constraint_index(wb["Constraint Index"])
    feasible_tables = compile_feasible_constraints(wb["Feasible Constraints"])

    wb.close()

    # Resolve: attach feasible table data to each constraint index entry
    for entry in constraint_index:
        tname = entry.get("table_name")
        if tname and tname in feasible_tables:
            entry["resolved_table"] = feasible_tables[tname]

    return {
        "step": STEP,
        "roadmap_version": ROADMAP_VERSION,
        "milestone": MILESTONE,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit,
        "git_working_tree_clean": clean,
        "combination_matrix": combination_matrix,
        "constraint_index": constraint_index,
        "feasible_tables": {
            name: {"headers": t["headers"], "row_count": t["row_count"]}
            for name, t in feasible_tables.items()
        },
    }


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def _banner(title: str) -> str:
    line = "=" * 140
    return f"{line}\r\n{title}\r\n{line}\r\n\r\n"


def write_outputs(evidence_dir: Path, result: dict[str, Any]) -> None:
    payload = {"artifact": "FYBROC_CONSTRAINT_MODEL", **result}
    (evidence_dir / "FYBROC_CONSTRAINT_MODEL.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    cm = result["combination_matrix"]
    ci = result["constraint_index"]
    ft = result["feasible_tables"]

    lines = [_banner("F120.3 - FYBROC CONSTRAINT MODEL (Combination Matrix + Constraint Index + Feasible Tables)")]
    lines.append(
        f"Git commit  : {result['git_commit']}\r\n"
        f"Git clean   : {result['git_working_tree_clean']}\r\n\r\n"
        f"Series codes       : {', '.join(cm['series_codes'])}\r\n"
        f"Distinct sizes     : {len(cm['size_codes'])}\r\n"
        f"Combination fields : {cm['field_count']}\r\n"
        f"Constraint index   : {len(ci)} entries\r\n"
        f"Feasible tables    : {len(ft)} tables\r\n\r\n"
    )

    # Combination matrix summary
    lines.append(_banner("COMBINATION MATRIX"))
    for row in cm["rows"]:
        combo = row["combination_verdict"] or "—"
        ans = f"  -> {row['answer_ref']}" if row["answer_ref"] else ""
        lines.append(
            f"  {row['field']:<35} list1={row['list1'] or '—':<30} list2={row['list2'] or '—':<30} "
            f"combination={combo}{ans}\r\n"
        )
    lines.append("\r\n")

    # Constraint index
    lines.append(_banner("CONSTRAINT INDEX"))
    for entry in ci:
        tname = entry.get("table_name") or "NO TABLE (series-derived)"
        rt = entry.get("resolved_table")
        resolved = f"  [{rt['row_count']} rows]" if rt else "  [NOT RESOLVED]"
        lines.append(
            f"  {tname:<25} {entry['option1'] or '—'} x {entry['option2'] or '—'}"
            f"{' x ' + entry['option3'] if entry['option3'] else ''}"
            f"{resolved}\r\n"
            f"    {entry['description'] or ''}\r\n\r\n"
        )

    # Feasible tables summary
    lines.append(_banner("FEASIBLE CONSTRAINT TABLES"))
    for tname, info in ft.items():
        lines.append(
            f"  {tname:<25} headers={info['headers']}  rows={info['row_count']}\r\n"
        )

    (evidence_dir / "FYBROC_CONSTRAINT_MODEL.txt").write_text(
        "".join(lines), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="F120.3 Fybroc Constraint Model compiler")
    default_root = Path(__file__).resolve().parent.parent
    parser.add_argument("--repo-root", type=Path, default=default_root)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    args = parser.parse_args()

    repo_root: Path = args.repo_root.resolve()
    evidence_dir: Path = (
        args.evidence_dir or (repo_root / "docs" / "evidence" / "F120")
    ).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)

    result = build_model(repo_root)
    write_outputs(evidence_dir, result)

    cm = result["combination_matrix"]
    ci = result["constraint_index"]
    ft = result["feasible_tables"]
    resolved = sum(1 for e in ci if e.get("resolved_table"))

    print(json.dumps({
        "step": STEP,
        "output_dir": str(evidence_dir),
        "combination_fields": cm["field_count"],
        "size_codes": len(cm["size_codes"]),
        "constraint_index_entries": len(ci),
        "feasible_tables": len(ft),
        "resolved_index_entries": resolved,
        "feasible_table_row_counts": {
            name: info["row_count"] for name, info in ft.items()
        },
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

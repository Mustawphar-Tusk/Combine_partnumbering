"""F120.4 - Fybroc Rev0.3 Motor Constraints + Combine Variables Compiler.

Roadmap anchor
--------------
docs/PROJECT_MASTER_ROADMAP.md, Section 6, Milestone F120
("Fybroc Rev0.3 Configuration Model") - the last two of the eight
required sources: Motor Constraints, Combine Variables.

Verified structure (not assumed):

  Motor Constraints - NOT built with real Excel Table objects (unlike
      Feasible Constraints' 29 named tables). Instead: 6 series-group
      blocks laid out side by side (columns 2, 20, 34, 48, 62, 76),
      scoped to "1500 and 1600", "1530 and 1630", "2530", "3000",
      "5500", "5530" respectively - the same 8-of-10-series coverage
      gap already found in the Constraints sheet (7500/8500 have no
      motor constraint rules defined). Each block has the same 4
      mini-tables: Alt_Size x Frame_Size, Alt_Size x MotorHpRpm,
      Frame_Size x MotorHpRpm, MotorHpRpm x Motor_Type - each with an
      "Allowed?" column. Each mini-table's row extent is read
      dynamically (scanned until blank), not assumed fixed, since nothing
      about this workbook so far has had uniform row counts.

  Combine Variables - not a constraint source; its own header states
      "This table is to make the pricing tables easier to figure out
      and is a good reference." Four combination-key lookup tables:
      F_MotorHpRPM -> (MotorHp, MotorRPM), MotorType -> (5 decomposed
      motor spec fields), Motor Mfg -> Motor Option (sourcing/supply
      arrangement per manufacturer), Wetted Hardware -> Shaft Material.

No workbook is opened in write mode. Nothing is written back.

Inputs:
  workbooks/Fybroc/Fybroc Configuration Rev0.3.xlsx  (read-only)

Outputs:
  docs/evidence/F120/FYBROC_MOTOR_CONSTRAINT_MODEL.{json,txt}
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
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "openpyxl is required (it's already a pinned project dependency - "
        "run this with the project's own .venv interpreter)."
    ) from exc

STEP = "F120.4"
ROADMAP_VERSION = "1.0"
MILESTONE = "F120"
WORKBOOK_REL = "workbooks/Fybroc/Fybroc Configuration Rev0.3.xlsx"

MOTOR_GROUP_ROW = 2
MOTOR_HEADER_ROW = 5
MOTOR_DATA_START_ROW = 6
MOTOR_MAX_SCAN_ROW = 210  # verified: last populated row is 199
# Verified group starting columns and their scope labels.
MOTOR_GROUPS = [(2, "1500 and 1600"), (20, "1530 and 1630"), (34, "2530"),
                (48, "3000"), (62, "5500"), (76, "5530")]
# Each group has 4 mini-tables at a fixed +0/+4/+8/+12 column offset from
# the group's start column, each spanning 3 columns (dim1, dim2, Allowed?).
MINI_TABLE_OFFSETS = [0, 4, 8, 12]

CV_HEADER_ROW = 3
CV_DATA_START_ROW = 4
CV_MAX_SCAN_ROW = 85  # verified: last populated row is 77
COMBINE_TABLES = [
    {"name": "MotorHpRpm_to_HpAndRpm", "key_col": 5, "value_cols": [6, 7]},
    {"name": "MotorType_decomposition", "key_col": 10, "value_cols": [12, 13, 14, 15, 16, 17]},
    {"name": "MotorMfg_to_MotorOption", "key_col": 19, "value_cols": [20]},
    {"name": "WettedHardware_to_ShaftMaterial", "key_col": 24, "value_cols": [25]},
]


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


def compile_motor_constraints(ws) -> list[dict[str, Any]]:
    blocks = []
    for group_start_col, series_label in MOTOR_GROUPS:
        for offset in MINI_TABLE_OFFSETS:
            c1, c2, c3 = group_start_col + offset, group_start_col + offset + 1, group_start_col + offset + 2
            h1 = ws.cell(row=MOTOR_HEADER_ROW, column=c1).value
            h2 = ws.cell(row=MOTOR_HEADER_ROW, column=c2).value
            h3 = ws.cell(row=MOTOR_HEADER_ROW, column=c3).value
            if h1 is None:
                continue  # defensive: skip if a mini-table isn't where expected
            rows = []
            for row in range(MOTOR_DATA_START_ROW, MOTOR_MAX_SCAN_ROW + 1):
                v1 = ws.cell(row=row, column=c1).value
                if v1 is None:
                    break  # dynamic extent: stop at first blank, not a fixed count
                rows.append({
                    str(h1): v1,
                    str(h2): ws.cell(row=row, column=c2).value,
                    str(h3): ws.cell(row=row, column=c3).value,
                })
            blocks.append({
                "series_scope": series_label,
                "dimension1": h1, "dimension2": h2,
                "row_count": len(rows), "rows": rows,
            })
    return blocks


def compile_combine_variables(ws) -> list[dict[str, Any]]:
    tables = []
    for spec in COMBINE_TABLES:
        key_col = spec["key_col"]
        value_cols = spec["value_cols"]
        key_header = ws.cell(row=CV_HEADER_ROW, column=key_col).value
        value_headers = [ws.cell(row=CV_HEADER_ROW, column=c).value for c in value_cols]
        rows = []
        for row in range(CV_DATA_START_ROW, CV_MAX_SCAN_ROW + 1):
            key_val = ws.cell(row=row, column=key_col).value
            if key_val is None:
                break
            entry = {"key": key_val}
            for header, c in zip(value_headers, value_cols):
                entry[str(header)] = ws.cell(row=row, column=c).value
            rows.append(entry)
        tables.append({
            "table": spec["name"], "key_field": key_header,
            "value_fields": value_headers, "row_count": len(rows), "rows": rows,
        })
    return tables


def build_model(repo_root: Path) -> dict[str, Any]:
    commit, clean = git_info(repo_root)
    wb = openpyxl.load_workbook(str(repo_root / WORKBOOK_REL), read_only=True, data_only=True)
    motor_blocks = compile_motor_constraints(wb["Motor Constraints"])
    combine_tables = compile_combine_variables(wb["Combine Variables"])
    wb.close()

    return {
        "step": STEP, "roadmap_version": ROADMAP_VERSION, "milestone": MILESTONE,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit, "git_working_tree_clean": clean,
        "motor_constraint_block_count": len(motor_blocks),
        "motor_constraint_blocks": motor_blocks,
        "combine_variable_table_count": len(combine_tables),
        "combine_variable_tables": combine_tables,
    }


def _banner(title: str) -> str:
    line = "=" * 140
    return f"{line}\r\n{title}\r\n{line}\r\n\r\n"


def write_outputs(evidence_dir: Path, result: dict[str, Any]) -> None:
    payload = {"artifact": "FYBROC_MOTOR_CONSTRAINT_MODEL", **result}
    (evidence_dir / "FYBROC_MOTOR_CONSTRAINT_MODEL.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )

    lines = [_banner("F120.4 - FYBROC MOTOR CONSTRAINT + COMBINE VARIABLES MODEL")]
    lines.append(
        f"Git commit  : {result['git_commit']}\r\nGit clean   : {result['git_working_tree_clean']}\r\n\r\n"
        f"Motor constraint blocks : {result['motor_constraint_block_count']}\r\n"
        f"Combine variable tables : {result['combine_variable_table_count']}\r\n\r\n"
    )

    lines.append(_banner("MOTOR CONSTRAINTS"))
    for b in result["motor_constraint_blocks"]:
        lines.append(f"[{b['series_scope']}] {b['dimension1']} x {b['dimension2']} ({b['row_count']} rows)\r\n")
        for r in b["rows"][:8]:
            lines.append(f"    {r}\r\n")
        if b["row_count"] > 8:
            lines.append(f"    ... ({b['row_count'] - 8} more rows, see JSON)\r\n")
        lines.append("\r\n")

    lines.append(_banner("COMBINE VARIABLES (reference lookups, not authoritative constraints)"))
    for t in result["combine_variable_tables"]:
        lines.append(f"[{t['table']}] {t['key_field']} -> {t['value_fields']} ({t['row_count']} rows)\r\n")
        for r in t["rows"][:8]:
            lines.append(f"    {r}\r\n")
        if t["row_count"] > 8:
            lines.append(f"    ... ({t['row_count'] - 8} more rows, see JSON)\r\n")
        lines.append("\r\n")

    (evidence_dir / "FYBROC_MOTOR_CONSTRAINT_MODEL.txt").write_text("".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="F120.4 Fybroc motor constraint + combine variables compiler")
    default_root = Path(__file__).resolve().parent.parent
    parser.add_argument("--repo-root", type=Path, default=default_root)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    args = parser.parse_args()

    repo_root: Path = args.repo_root.resolve()
    evidence_dir: Path = (args.evidence_dir or (repo_root / "docs" / "evidence" / "F120")).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)

    result = build_model(repo_root)
    write_outputs(evidence_dir, result)

    print(json.dumps({
        "step": STEP, "output_dir": str(evidence_dir),
        "motor_constraint_block_count": result["motor_constraint_block_count"],
        "combine_variable_table_count": result["combine_variable_table_count"],
        "total_motor_constraint_rows": sum(b["row_count"] for b in result["motor_constraint_blocks"]),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
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
# Blocks have DIFFERENT lengths (the Alt_Size x F_MotorHpRpm blocks extend to
# ~row 530, far past the Alt_Size x F_Frame_Size blocks). A fixed cap here
# previously truncated the longer blocks and dropped real motor constraints.
# We now stop dynamically at the first blank in each block's key column, with a
# generous safety bound only to avoid runaway scans.
MOTOR_MAX_SCAN_ROW = 1000  # safety bound; real blocks end at a blank key cell well before this
# Verified group starting columns and their scope labels.
MOTOR_GROUPS = [(2, "1500 and 1600"), (20, "1530 and 1630"), (34, "2530"),
                (48, "3000"), (62, "5500"), (76, "5530")]
# Each group has 4 mini-tables at a fixed +0/+4/+8/+12 column offset from
# the group's start column, each spanning 3 columns (dim1, dim2, Allowed?).
MINI_TABLE_OFFSETS = [0, 4, 8, 12]

CV_HEADER_ROW = 3
CV_DATA_START_ROW = 4
CV_MAX_SCAN_ROW = 130  # safety bound; real columns end at a blank cell before this

# Two kinds of tables live on the Combine Variables sheet:
#
#  (a) key_value tables: a composite key column parsed into component columns,
#      genuinely ROW-ALIGNED (e.g. "1-1200" -> Hp 1, RPM 1200). Verified against
#      V6 and the workbook. ONLY MotorHpRpm is a real row-aligned mapping - its
#      key column (E) is a composite that formulas split via TEXTBEFORE/TEXTAFTER
#      (F4=TEXTBEFORE(E4,"-"), G4=TEXTAFTER(E4,"-")).
#
#  (b) value_domains: regions where each column is an INDEPENDENT list of valid
#      values for one attribute (the attribute's domain), NOT a row-aligned
#      mapping. This includes:
#        - the "MotorType" region (cols 10-17), mirroring the V6 ' Motor Assy'
#          display of the same motor attributes as independent domain columns;
#        - Motor Mfg (col 19/S) and Motor Option (col 20/T);
#        - Wetted Hardware (col 24/X) and Shaft Material (col 25/Y).
#      Motor Mfg/Option and Wetted Hardware/Shaft Material were PREVIOUSLY
#      mislabeled as key->value mappings (MotorMfg_to_MotorOption,
#      WettedHardware_to_ShaftMaterial). Verified against the workbook they are
#      NOT paired: each is an ArrayFormula spill from the QATable
#      (=CHOOSECOLS(FILTER(QATable[],QATable[Question]=<hdr>),2)), the paired
#      columns have DIFFERENT lengths (Mfg=4 vs Option=3; Wetted=2 vs Shaft=12),
#      and both members are separate QATable Questions. The false pairing had
#      produced a phantom "Toshiba -> (blank)" and would have wrongly filtered
#      Motor Option to empty. See docs/evidence/F120/
#      FYBROC_CONSTRAINT_EXTRACTION_ALIGNMENT.md.
COMBINE_KEY_VALUE_TABLES = [
    {"name": "MotorHpRpm_to_HpAndRpm", "key_col": 5, "value_cols": [6, 7]},
]
# Each entry: independent per-attribute value lists. domain_cols read
# top-to-first-blank independently (each column is one attribute's domain).
COMBINE_VALUE_DOMAIN_TABLES = [
    {"name": "MotorType_domains",
     "domain_cols": [10, 12, 13, 14, 15, 16, 17]},
    {"name": "MotorMfgOption_domains",
     "domain_cols": [19, 20]},
    {"name": "WettedHardwareShaft_domains",
     "domain_cols": [24, 25]},
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


def compile_combine_variables(ws) -> dict[str, Any]:
    """Compile the Combine Variables sheet into two model kinds.

    key_value_tables : row-aligned composite-key -> component-value mappings.
    value_domain_tables : independent per-attribute value-domain lists (the
        MotorType region), each column read top-to-first-blank independently.
    """
    key_value_tables = []
    for spec in COMBINE_KEY_VALUE_TABLES:
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
        key_value_tables.append({
            "table": spec["name"], "key_field": key_header,
            "value_fields": value_headers, "row_count": len(rows), "rows": rows,
        })

    value_domain_tables = []
    for spec in COMBINE_VALUE_DOMAIN_TABLES:
        domains = []
        for c in spec["domain_cols"]:
            header = ws.cell(row=CV_HEADER_ROW, column=c).value
            if header is None:
                continue
            values = []
            for row in range(CV_DATA_START_ROW, CV_MAX_SCAN_ROW + 1):
                v = ws.cell(row=row, column=c).value
                if v is None:
                    break  # each attribute domain ends at its first blank
                values.append(v)
            domains.append({
                "attribute": str(header),
                "value_count": len(values),
                "values": values,
            })
        value_domain_tables.append({
            "table": spec["name"],
            "attribute_count": len(domains),
            "domains": domains,
        })

    return {
        "key_value_tables": key_value_tables,
        "value_domain_tables": value_domain_tables,
    }


def build_model(repo_root: Path) -> dict[str, Any]:
    commit, clean = git_info(repo_root)
    wb = openpyxl.load_workbook(str(repo_root / WORKBOOK_REL), read_only=True, data_only=True)
    motor_blocks = compile_motor_constraints(wb["Motor Constraints"])
    combine = compile_combine_variables(wb["Combine Variables"])
    wb.close()

    return {
        "step": STEP, "roadmap_version": ROADMAP_VERSION, "milestone": MILESTONE,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit, "git_working_tree_clean": clean,
        "motor_constraint_block_count": len(motor_blocks),
        "motor_constraint_blocks": motor_blocks,
        "combine_variable_table_count": len(combine["key_value_tables"]),
        "combine_variable_tables": combine["key_value_tables"],
        "combine_value_domain_table_count": len(combine["value_domain_tables"]),
        "combine_value_domain_tables": combine["value_domain_tables"],
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

    lines.append(_banner("COMBINE VARIABLES - key->value lookups (composite key decomposition)"))
    for t in result["combine_variable_tables"]:
        lines.append(f"[{t['table']}] {t['key_field']} -> {t['value_fields']} ({t['row_count']} rows)\r\n")
        for r in t["rows"][:8]:
            lines.append(f"    {r}\r\n")
        if t["row_count"] > 8:
            lines.append(f"    ... ({t['row_count'] - 8} more rows, see JSON)\r\n")
        lines.append("\r\n")

    lines.append(_banner("COMBINE VARIABLES - value domains (independent per-attribute value lists)"))
    for t in result.get("combine_value_domain_tables", []):
        lines.append(f"[{t['table']}] {t['attribute_count']} attribute domains\r\n")
        for dom in t["domains"]:
            preview = ", ".join(str(v) for v in dom["values"][:10])
            more = "" if dom["value_count"] <= 10 else f" ... (+{dom['value_count'] - 10} more)"
            lines.append(f"    {dom['attribute']} ({dom['value_count']}): {preview}{more}\r\n")
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
        "combine_value_domain_table_count": result.get("combine_value_domain_table_count", 0),
        "total_motor_constraint_rows": sum(b["row_count"] for b in result["motor_constraint_blocks"]),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
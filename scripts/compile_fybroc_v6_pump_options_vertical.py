"""F110.5b - Fybroc Nomenclature V6 Pump Options Vertical Compiler.

Roadmap anchor
--------------
docs/PROJECT_MASTER_ROADMAP.md, Section 6, Milestone F110
("V5 to V6 Nomenclature Reconciliation") - combination rules, source
fields, orientation behavior.

The "Pump Options - Vertical" sheet in Nomenclature_V6.xlsm defines
the full combination matrix for all vertical pump option fields.

DISPLAY SECTION (rows 1-12, cols C-M):
  Row 2 = field names, rows 3-9 = valid options per field:
    Col D : Shaft Material
    Col E : Sleeve
    Col F : Wetted Hardware
    Col G : Pump Elastomers
    Col H : Flush
    Col I : Cyclone Separator
    Col J : Impeller Balance
    Col K : Vapor Seal
    Col L : Strainer
    Col M : Flush Material (display only)

DATA SECTION (rows 13-23053, cols C-Q):
  Row 13  = column headers
  Rows 14+= one row per unique combination of all 9 fields
    Col C  : concatenated key (VLOOKUP key)
    Col D  : Shaft Material
    Col E  : Impeller Sleeve
    Col F  : Wetted Hardware
    Col G  : Pump Elastomers
    Col H  : Flush
    Col I  : Flush Options
    Col J  : Impeller Balance
    Col K  : Vapor Protection
    Col L  : Strainer
    Col M  : Hex-Code (part number token)
    Col N  : ID (sequential integer)
    Col P  : Shaft Material label (derived)
    Col Q  : Flush abbreviation (derived)

Total rows: 23,040 combinations (rows 14-23053).

KEY DIFFERENCES vs Horizontal:
  - 9 fields (vs 12 horizontal)
  - No Casing Drains, Suction Discharge, Bearing Option, Casing Hardware,
    Gland Hardware, Frame Hardware
  - Adds: Wetted Hardware, Vapor Protection, Strainer, Flush Options
  - Sleeve field = Impeller Sleeve (different from horizontal)
  - Flush Options is a separate field (cyclone separator variant)

No workbook is opened in write mode. Nothing is written back.

Inputs:
  workbooks/Fybroc/Nomenclature_V6.xlsm  (read-only)

Outputs:
  docs/evidence/F110/FYBROC_V6_PUMP_OPTIONS_VERTICAL.{json,txt}
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

STEP = "F110.5b"
ROADMAP_VERSION = "1.0"
MILESTONE = "F110"
WORKBOOK_REL = "workbooks/Fybroc/Nomenclature_V6.xlsm"
SHEET = "Pump Options - Vertical"

# Display section
DISPLAY_HEADER_ROW = 2
DISPLAY_DATA_START = 3
DISPLAY_DATA_END   = 9
DISPLAY_COL_START  = 4   # col D
DISPLAY_COL_END    = 13  # col M

# Data section
DATA_HEADER_ROW = 13
DATA_START_ROW  = 14
DATA_END_ROW    = 23053

# Column indices (1-based)
COL_KEY            = 3   # C
COL_SHAFT_MATERIAL = 4   # D
COL_SLEEVE         = 5   # E
COL_WETTED_HW      = 6   # F
COL_PUMP_ELAST     = 7   # G
COL_FLUSH          = 8   # H
COL_FLUSH_OPTIONS  = 9   # I
COL_IMP_BALANCE    = 10  # J
COL_VAPOR_PROTECT  = 11  # K
COL_STRAINER       = 12  # L
COL_HEX_CODE       = 13  # M
COL_ID             = 14  # N
COL_SHAFT_LABEL    = 16  # P
COL_FLUSH_ABBREV   = 17  # Q

FIELD_COLS = [
    (COL_SHAFT_MATERIAL, "Shaft Material"),
    (COL_SLEEVE,         "Impeller Sleeve"),
    (COL_WETTED_HW,      "Wetted Hardware"),
    (COL_PUMP_ELAST,     "Pump Elastomers"),
    (COL_FLUSH,          "Flush"),
    (COL_FLUSH_OPTIONS,  "Flush Options"),
    (COL_IMP_BALANCE,    "Impeller Balance"),
    (COL_VAPOR_PROTECT,  "Vapor Protection"),
    (COL_STRAINER,       "Strainer"),
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


def _str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def compile_display_section(ws) -> dict[str, list[str]]:
    fields: dict[int, str] = {}
    for c in range(DISPLAY_COL_START, DISPLAY_COL_END + 1):
        v = _str(ws.cell(row=DISPLAY_HEADER_ROW, column=c).value)
        if v:
            fields[c] = v

    options: dict[str, list[str]] = {name: [] for name in fields.values()}
    for r in range(DISPLAY_DATA_START, DISPLAY_DATA_END + 1):
        for col, field_name in fields.items():
            v = _str(ws.cell(row=r, column=col).value)
            if v:
                options[field_name].append(v)
    return options


def compile_data_section(ws) -> dict[str, Any]:
    BASE = COL_KEY  # col C = index 0

    field_values: dict[str, set] = {name: set() for _, name in FIELD_COLS}
    hex_codes: set[str] = set()
    sample_rows: list[dict] = []
    total = 0

    for row_tuple in ws.iter_rows(
        min_row=DATA_START_ROW, max_row=DATA_END_ROW,
        min_col=COL_KEY, max_col=COL_FLUSH_ABBREV,
        values_only=True,
    ):
        hex_code = _str(row_tuple[COL_HEX_CODE - BASE])
        if hex_code is None:
            break

        total += 1
        hex_codes.add(hex_code)

        row_data: dict[str, Any] = {}
        for col, name in FIELD_COLS:
            v = _str(row_tuple[col - BASE])
            row_data[name] = v
            if v:
                field_values[name].add(v)

        if total <= 20:
            sample_rows.append({
                "id": row_tuple[COL_ID - BASE],
                "hex_code": hex_code,
                "shaft_label": _str(row_tuple[COL_SHAFT_LABEL - BASE]),
                "flush_abbrev": _str(row_tuple[COL_FLUSH_ABBREV - BASE]),
                **row_data,
            })

    sorted_hex = sorted(hex_codes)
    return {
        "total_combinations": total,
        "distinct_hex_codes": len(hex_codes),
        "hex_code_range": {
            "first": sorted_hex[0] if sorted_hex else None,
            "last": sorted_hex[-1] if sorted_hex else None,
        },
        "distinct_values_per_field": {
            name: sorted(vals) for name, vals in field_values.items()
        },
        "sample_rows": sample_rows,
    }


def build_model(repo_root: Path) -> dict[str, Any]:
    commit, clean = git_info(repo_root)

    wb = openpyxl.load_workbook(
        str(repo_root / WORKBOOK_REL), read_only=True, data_only=True
    )
    ws = wb[SHEET]

    display = compile_display_section(ws)
    data    = compile_data_section(ws)

    wb.close()

    return {
        "step": STEP,
        "roadmap_version": ROADMAP_VERSION,
        "milestone": MILESTONE,
        "source_workbook": WORKBOOK_REL,
        "sheet": SHEET,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit,
        "git_working_tree_clean": clean,
        "fields": [name for _, name in FIELD_COLS],
        "field_options": display,
        "combination_matrix": data,
        "lookup_key_col": "C (concatenated all field values)",
        "hex_code_col": "M",
        "part_number_role": (
            "The hex-code in col M is the Pump Options segment token "
            "embedded in the Fybroc vertical part number. "
            "Smart Number uses VLOOKUP(concat_key, col_C, col_M)."
        ),
        "vs_horizontal": {
            "field_count_vertical": len(FIELD_COLS),
            "field_count_horizontal": 12,
            "vertical_only_fields": [
                "Wetted Hardware", "Flush Options",
                "Vapor Protection", "Strainer",
            ],
            "horizontal_only_fields": [
                "Casing Drains", "Suction Discharge", "Casing Hardware",
                "Bearing Option", "Frame Hardware", "Gland Hardware",
                "Cyclone Separator",
            ],
            "shared_fields": [
                "Shaft Material", "Sleeve/Impeller Sleeve",
                "Pump Elastomers", "Flush", "Impeller Balance",
            ],
        },
    }


def _banner(title: str) -> str:
    line = "=" * 120
    return f"{line}\r\n{title}\r\n{line}\r\n\r\n"


def write_outputs(evidence_dir: Path, result: dict[str, Any]) -> None:
    payload = {"artifact": "FYBROC_V6_PUMP_OPTIONS_VERTICAL", **result}
    (evidence_dir / "FYBROC_V6_PUMP_OPTIONS_VERTICAL.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    cm = result["combination_matrix"]
    lines = [_banner("F110.5b - FYBROC V6 PUMP OPTIONS VERTICAL")]
    lines.append(
        f"Git commit           : {result['git_commit']}\r\n"
        f"Git clean            : {result['git_working_tree_clean']}\r\n\r\n"
        f"Fields               : {len(result['fields'])}\r\n"
        f"Total combinations   : {cm['total_combinations']:,}\r\n"
        f"Distinct hex-codes   : {cm['distinct_hex_codes']:,}\r\n"
        f"Hex-code range       : {cm['hex_code_range']['first']} -> {cm['hex_code_range']['last']}\r\n"
        f"Lookup key col       : {result['lookup_key_col']}\r\n"
        f"Hex-code col         : {result['hex_code_col']}\r\n\r\n"
    )

    lines.append(_banner("FIELD OPTIONS"))
    for field, opts in result["field_options"].items():
        lines.append(f"  {field}:\r\n")
        for opt in opts:
            lines.append(f"    - {opt}\r\n")
        lines.append("\r\n")

    lines.append(_banner("DISTINCT VALUES PER FIELD (from full matrix)"))
    for field, vals in cm["distinct_values_per_field"].items():
        lines.append(f"  {field} ({len(vals)}):\r\n")
        for v in vals:
            lines.append(f"    {v}\r\n")
        lines.append("\r\n")

    v = result["vs_horizontal"]
    lines.append(_banner("VERTICAL vs HORIZONTAL DIFFERENCES"))
    lines.append(f"  Vertical fields  : {v['field_count_vertical']}\r\n")
    lines.append(f"  Horizontal fields: {v['field_count_horizontal']}\r\n\r\n")
    lines.append("  Vertical-only fields:\r\n")
    for f in v["vertical_only_fields"]:
        lines.append(f"    + {f}\r\n")
    lines.append("\r\n  Horizontal-only fields:\r\n")
    for f in v["horizontal_only_fields"]:
        lines.append(f"    - {f}\r\n")
    lines.append("\r\n  Shared fields:\r\n")
    for f in v["shared_fields"]:
        lines.append(f"    = {f}\r\n")
    lines.append("\r\n")

    lines.append(_banner("SAMPLE ROWS (first 20)"))
    for row in cm["sample_rows"]:
        lines.append(
            f"  ID={row['id']:>6}  hex={row['hex_code']}  "
            f"shaft={row.get('shaft_label') or '—'}  flush={row.get('flush_abbrev') or '—'}\r\n"
        )
        for _, fname in FIELD_COLS:
            lines.append(f"    {fname:<28} = {row.get(fname) or '—'}\r\n")
        lines.append("\r\n")

    (evidence_dir / "FYBROC_V6_PUMP_OPTIONS_VERTICAL.txt").write_text(
        "".join(lines), encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="F110.5b Fybroc V6 Pump Options Vertical compiler")
    default_root = Path(__file__).resolve().parent.parent
    parser.add_argument("--repo-root", type=Path, default=default_root)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    args = parser.parse_args()

    repo_root: Path = args.repo_root.resolve()
    evidence_dir: Path = (
        args.evidence_dir or (repo_root / "docs" / "evidence" / "F110")
    ).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)

    result = build_model(repo_root)
    write_outputs(evidence_dir, result)

    cm = result["combination_matrix"]
    print(json.dumps({
        "step": STEP,
        "output_dir": str(evidence_dir),
        "fields": result["fields"],
        "total_combinations": cm["total_combinations"],
        "distinct_hex_codes": cm["distinct_hex_codes"],
        "hex_code_range": cm["hex_code_range"],
        "vs_horizontal": result["vs_horizontal"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

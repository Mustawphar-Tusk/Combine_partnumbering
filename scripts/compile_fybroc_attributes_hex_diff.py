"""F110.2a - Fybroc V5/V6 Attributes Hex-Code Diff.

Roadmap anchor
--------------
docs/PROJECT_MASTER_ROADMAP.md, Section 6, Milestone F110
("V5 to V6 Nomenclature Reconciliation") - the "identifier codes" item on
F110's required-analysis list.

This is the first slice of F110.2 (identifier segment / hex code diff),
covering only the `Attributes` sheet - the smallest, best-understood
hex-mapping sheet. Pump Options, Seal Assembly, Options, and Motor Assy
are separate, larger follow-up slices (F110.2b+), not covered here.

Column layout was verified directly against both real workbooks before
writing this (not assumed from V5's known layout applied to V6), because
F110.1 already showed V6's Attributes sheet has one fewer column than
V5's, and a direct header check revealed the shift is NOT uniform:

  - Size, Pump_Material, Impeller_Trim, Motor Modifications, Inch,
    Decimal: same field, same hex-code meaning, shifted by exactly one
    column in V6. Directly comparable - covered by this script.
  - Series: NOT comparable as a like-for-like hex diff. V5 encodes
    series+flange combination as a single hex letter (e.g.
    "1500 (ANSI)" -> "A"). V6 splits this into a bare series number and
    a separate, non-hex "Flange Type" descriptor (e.g. "1500" / "ANSI").
    Treated here as its own flagged item, not value-compared.
  - Testing: present in V5's Attributes (columns 21/22) hex table.
    ABSENT from V6's Attributes sheet entirely - consistent with F110.1
    already showing V6 has a new, dedicated `Testing` sheet. Flagged
    here as "moved, not diffed" and pointed at F110.4, not compared.

Value names are matched using the same normalization already established
for this exact purpose (strip a trailing "*" default-value marker,
"_" <-> " "), per fybroc_hex_code_explorer.py's own documented handling
of the known V5 "VR-1*" vs "VR-1" naming quirk - reused here, not
re-derived, so a cosmetic naming fix doesn't show up as a false
DEPRECATED+NEW pair.

No workbook is opened in write mode. Nothing is written back to either
workbook.

Inputs:
  workbooks/Fybroc/Fybroc Nomenclature_V5.xlsm  (read-only)
  workbooks/Fybroc/Nomenclature_V6.xlsm         (read-only)

Outputs:
  docs/evidence/F110/FYBROC_ATTRIBUTES_HEX_DIFF.{json,txt}
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

STEP = "F110.2a"
ROADMAP_VERSION = "1.0"
MILESTONE = "F110"

V5_WORKBOOK_REL = "workbooks/Fybroc/Fybroc Nomenclature_V5.xlsm"
V6_WORKBOOK_REL = "workbooks/Fybroc/Nomenclature_V6.xlsm"

HEADER_ROW = 7
DATA_START_ROW = 8
DATA_END_ROW = 523  # per F100.2's structural inventory: max_row for Attributes in both V5 and V6

# ---------------------------------------------------------------------------
# Verified (not assumed) column positions: (name_col, code_col), 1-indexed.
# Confirmed against both real workbooks' row 7 header text and row 8-12
# sample data before writing this script.
# ---------------------------------------------------------------------------
COMPARABLE_FIELDS: dict[str, dict[str, tuple[int, int]]] = {
    "Size":                 {"v5": (9, 10),  "v6": (10, 11)},
    "Pump_Material":        {"v5": (12, 13), "v6": (13, 14)},
    "Impeller_Trim":        {"v5": (15, 16), "v6": (16, 17)},
    "Motor_Modifications":  {"v5": (18, 19), "v6": (19, 20)},
    "Inch":                 {"v5": (29, 30), "v6": (23, 24)},
    "Decimal":              {"v5": (32, 33), "v6": (26, 27)},
}

# Fields deliberately NOT value-compared here - see module docstring.
FLAGGED_FIELDS = {
    "Series": (
        "V5 encodes series+flange combination as a single hex letter "
        "(e.g. '1500 (ANSI)' -> 'A'). V6 splits this into a bare series "
        "number and a separate, non-hex 'Flange Type' descriptor. Not a "
        "like-for-like hex comparison - needs its own dedicated look at "
        "where (if anywhere) V6 now derives a series+flange hex code."
    ),
    "Testing": (
        "Present in V5's Attributes hex table (columns 21/22). Absent "
        "from V6's Attributes sheet entirely. Consistent with F110.1's "
        "finding that V6 has a new, dedicated Testing sheet - see F110.4, "
        "not compared here."
    ),
}


def normalize_value(value: Any) -> str:
    """Bridges the known V5 default-value-marker quirk ('VR-1*') and
    underscore-vs-space spelling, exactly as fybroc_hex_code_explorer.py
    already established for this same purpose - reused, not re-derived."""
    text = str(value).strip()
    if text.endswith("*"):
        text = text[:-1].strip()
    return text.replace("_", " ").strip().lower()


def read_hex_table(path: Path, name_col: int, code_col: int) -> dict[str, tuple[Any, Any]]:
    """normalized_name -> (raw_name, hex_code). Last non-blank row wins if a
    name repeats (shouldn't happen, but don't silently drop a duplicate)."""
    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    try:
        ws = wb["Attributes"]
        result: dict[str, tuple[Any, Any]] = {}
        for row in range(DATA_START_ROW, DATA_END_ROW + 1):
            name = ws.cell(row=row, column=name_col).value
            if name is None or str(name).strip() == "":
                continue
            code = ws.cell(row=row, column=code_col).value
            result[normalize_value(name)] = (name, code)
        return result
    finally:
        wb.close()


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


def diff_field(repo_root: Path, field_name: str, v5_cols: tuple[int, int], v6_cols: tuple[int, int]) -> dict[str, Any]:
    v5_path = repo_root / V5_WORKBOOK_REL
    v6_path = repo_root / V6_WORKBOOK_REL
    v5_table = read_hex_table(v5_path, *v5_cols)
    v6_table = read_hex_table(v6_path, *v6_cols)

    all_keys = sorted(set(v5_table) | set(v6_table))
    rows = []
    counts = {"UNCHANGED": 0, "CHANGED": 0, "NEW": 0, "DEPRECATED": 0}
    for key in all_keys:
        in_v5 = key in v5_table
        in_v6 = key in v6_table
        if in_v5 and in_v6:
            v5_name, v5_code = v5_table[key]
            v6_name, v6_code = v6_table[key]
            classification = "UNCHANGED" if v5_code == v6_code else "CHANGED"
        elif in_v5:
            v5_name, v5_code = v5_table[key]
            v6_name, v6_code = None, None
            classification = "DEPRECATED"
        else:
            v5_name, v5_code = None, None
            v6_name, v6_code = v6_table[key]
            classification = "NEW"
        counts[classification] += 1
        rows.append({
            "value": v5_name if v5_name is not None else v6_name,
            "v5_name_raw": v5_name,
            "v5_hex_code": v5_code,
            "v6_name_raw": v6_name,
            "v6_hex_code": v6_code,
            "classification": classification,
        })

    return {"field": field_name, "row_count": len(rows), "classification_counts": counts, "rows": rows}


def build_diff(repo_root: Path) -> dict[str, Any]:
    commit, clean = git_info(repo_root)
    generated = datetime.now(timezone.utc).isoformat()

    fields = [diff_field(repo_root, name, cols["v5"], cols["v6"]) for name, cols in COMPARABLE_FIELDS.items()]

    total_counts: dict[str, int] = {}
    for f in fields:
        for cls, n in f["classification_counts"].items():
            total_counts[cls] = total_counts.get(cls, 0) + n

    return {
        "step": STEP,
        "roadmap_version": ROADMAP_VERSION,
        "milestone": MILESTONE,
        "generated_utc": generated,
        "git_commit": commit,
        "git_working_tree_clean": clean,
        "sheet": "Attributes",
        "comparable_field_count": len(fields),
        "total_classification_counts": total_counts,
        "fields": fields,
        "flagged_not_compared": [
            {"field": name, "reason": reason} for name, reason in FLAGGED_FIELDS.items()
        ],
    }


def _banner(title: str) -> str:
    line = "=" * 140
    return f"{line}\r\n{title}\r\n{line}\r\n\r\n"


def write_outputs(evidence_dir: Path, result: dict[str, Any]) -> None:
    payload = {"artifact": "FYBROC_ATTRIBUTES_HEX_DIFF", **result}
    (evidence_dir / "FYBROC_ATTRIBUTES_HEX_DIFF.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )

    lines = [_banner("F110.2a - FYBROC ATTRIBUTES HEX-CODE DIFF")]
    lines.append(
        f"Git commit  : {result['git_commit']}\r\n"
        f"Git clean   : {result['git_working_tree_clean']}\r\n"
        f"Sheet       : Attributes (both workbooks)\r\n"
        f"Fields diffed: {result['comparable_field_count']}\r\n\r\n"
    )
    lines.append("TOTAL CLASSIFICATION COUNTS\r\n" + "-" * 140 + "\r\n")
    for cls, count in sorted(result["total_classification_counts"].items()):
        lines.append(f"  {cls:<15}: {count}\r\n")
    lines.append("\r\n")

    lines.append(_banner("FLAGGED - NOT VALUE-COMPARED"))
    for item in result["flagged_not_compared"]:
        lines.append(f"[{item['field']}]\r\n    {item['reason']}\r\n\r\n")

    for f in result["fields"]:
        lines.append(_banner(f"FIELD: {f['field']}"))
        lines.append(f"Rows: {f['row_count']}   " + "  ".join(
            f"{k}={v}" for k, v in f["classification_counts"].items() if v
        ) + "\r\n\r\n")
        for r in f["rows"]:
            if r["classification"] == "UNCHANGED":
                continue  # keep the report focused on what actually differs
            lines.append(
                f"  {r['classification']:<12} {r['value']!r:<30} "
                f"v5={r['v5_hex_code']!r}  v6={r['v6_hex_code']!r}\r\n"
            )
        lines.append("\r\n")

    (evidence_dir / "FYBROC_ATTRIBUTES_HEX_DIFF.txt").write_text("".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="F110.2a Fybroc Attributes hex-code diff")
    default_root = Path(__file__).resolve().parent.parent
    parser.add_argument("--repo-root", type=Path, default=default_root)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    args = parser.parse_args()

    repo_root: Path = args.repo_root.resolve()
    evidence_dir: Path = (args.evidence_dir or (repo_root / "docs" / "evidence" / "F110")).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)

    result = build_diff(repo_root)
    write_outputs(evidence_dir, result)

    print(json.dumps({
        "step": STEP,
        "output_dir": str(evidence_dir),
        "comparable_field_count": result["comparable_field_count"],
        "total_classification_counts": result["total_classification_counts"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
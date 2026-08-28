"""F120.1 - Fybroc Rev0.3 Items + Hierarchy Compiler.

Roadmap anchor
--------------
docs/PROJECT_MASTER_ROADMAP.md, Section 6, Milestone F120
("Fybroc Rev0.3 Configuration Model") - the first two of the eight
required sources: Items, Hierarchy.

What these sheets actually are (verified by direct inspection, not
assumed from sheet names):

  Items - a per-(series, item) field-applicability table. Row 2 has
      Series / Item / Alt_Size, then 34 F_-prefixed field-flag columns;
      an 'X' means that field applies to that series+item combination.
      97 data rows total.

      Columns 66-88 hold a second, cross-referencing structure (an X/
      blank presence flag per series, and a parallel block with the
      *actual item code* at each row position). Row 1 of that block
      contains an explicit engineering warning:

        "HAVE TO DISTINGUISH BETWEEN SOME PARTS, SOME DON'T REPRESENT
        THE SAME THING. FOR EXAMPLE, 89 IS DIFFERENT ON 1500 THAN 5500"

      i.e. the same row position does NOT mean the same item across
      series. This step deliberately does NOT attempt to compile that
      cross-reference block - its exact semantics aren't fully clear
      yet, and given the explicit warning above, guessing here is
      worse than leaving it undocumented. The main Items table (Series
      + Item + field flags) is unambiguous and is what this step
      compiles. Items are always matched by their actual Item code
      string, never by row position, precisely because of that warning.

  Hierarchy - groups individual field names into 8 categories: Pump
      Options, Impeller, Mechanical Seal, Motor, Baseplate, Mounting
      plate, Vertical, Other. (Only 4 of these 8 were visible in an
      earlier, narrower check - confirmed the full set by reading the
      full header row before compiling.) Baseplate and Mounting plate
      being separate categories here independently confirms the F110
      finding that V6's Options-Vertical uses "Mounting Plate Option"
      instead of "Baseplate Option" - not a naming coincidence, a
      deliberate structural distinction already present in Rev0.3.

No workbook is opened in write mode. Nothing is written back.

Inputs:
  workbooks/Fybroc/Fybroc Configuration Rev0.3.xlsx  (read-only)

Outputs:
  docs/evidence/F120/FYBROC_ITEMS_HIERARCHY_MODEL.{json,txt}
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

STEP = "F120.1"
ROADMAP_VERSION = "1.0"
MILESTONE = "F120"
WORKBOOK_REL = "workbooks/Fybroc/Fybroc Configuration Rev0.3.xlsx"

ITEMS_HEADER_ROW = 2
ITEMS_DATA_START_ROW = 3
# The main Items table is much longer than an earlier fixed cap of 99 assumed.
# It runs continuously (col A = "{series}_{item}" key) to row 469 (467 rows).
# The 99 cap dropped ~370 item records, skewing per-series coverage. We now
# read dynamically: stop at the first blank key cell in col A, bounded only by
# a generous safety limit.
ITEMS_KEY_COL = 1  # col A: "{series}_{item}" composite key marks a real row
ITEMS_MAX_SCAN_ROW = 20000  # safety bound; real table ends at a blank key well before this
ITEMS_MAIN_TABLE_LAST_COL = 39  # verified: F_Vapor_Seal is the last field-flag column

HIERARCHY_GROUPS = [
    # (header_col, header_row, field_list_col, last_verified_row)
    ("Pump Options", 1, 2, 13),
    ("Impeller", 4, 5, 14),
    ("Mechanical Seal", 7, 8, 10),
    ("Motor", 10, 11, 12),
    ("Baseplate", 13, 14, 7),
    ("Mounting plate", 16, 17, 2),
    ("Vertical", 19, 20, 7),
    ("Other", 22, 23, 3),
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


def compile_items(ws) -> dict[str, Any]:
    headers = {}
    for c in range(2, ITEMS_MAIN_TABLE_LAST_COL + 1):
        v = ws.cell(row=ITEMS_HEADER_ROW, column=c).value
        if v:
            headers[c] = v
    field_cols = {c: name for c, name in headers.items() if name.startswith("F_")}

    rows = []
    series_seen: set[str] = set()
    for row in range(ITEMS_DATA_START_ROW, ITEMS_MAX_SCAN_ROW + 1):
        # The composite key in col A marks a real item row; a blank key is the
        # true end of the main table.
        key = ws.cell(row=row, column=ITEMS_KEY_COL).value
        if key is None or str(key).strip() == "":
            break
        series = ws.cell(row=row, column=2).value
        item = ws.cell(row=row, column=3).value
        if series is None or item is None:
            continue
        series = str(series).strip()
        item = str(item).strip()
        series_seen.add(series)
        applicable_fields = [
            name for c, name in field_cols.items()
            if ws.cell(row=row, column=c).value == "X"
        ]
        rows.append({
            "series": series,
            "item": item,
            "applicable_fields": applicable_fields,
            "applicable_field_count": len(applicable_fields),
        })

    return {
        "field_count": len(field_cols),
        "field_names": sorted(field_cols.values()),
        "series_found": sorted(series_seen, key=lambda s: (len(s), s)),
        "row_count": len(rows),
        "rows": rows,
        "not_compiled": (
            "Columns 66-88 (per-series item-code cross-reference block) - "
            "see module docstring. Row 1 of that block contains an explicit "
            "engineering warning that row position does not align items "
            "across series; not compiled here to avoid guessing at "
            "semantics that aren't fully clear yet."
        ),
    }


def compile_hierarchy(ws) -> dict[str, Any]:
    groups = []
    for group_name, header_col, field_col, last_row in HIERARCHY_GROUPS:
        fields = []
        for row in range(2, last_row + 1):
            v = ws.cell(row=row, column=field_col).value
            if v is not None and str(v).strip() != "":
                fields.append(str(v).strip())
        groups.append({"group": group_name, "field_count": len(fields), "fields": fields})
    return {"group_count": len(groups), "groups": groups}


def build_model(repo_root: Path) -> dict[str, Any]:
    commit, clean = git_info(repo_root)
    wb = openpyxl.load_workbook(str(repo_root / WORKBOOK_REL), read_only=True, data_only=True)
    items = compile_items(wb["Items"])
    hierarchy = compile_hierarchy(wb["Hierarchy"])
    wb.close()

    return {
        "step": STEP, "roadmap_version": ROADMAP_VERSION, "milestone": MILESTONE,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit, "git_working_tree_clean": clean,
        "items": items, "hierarchy": hierarchy,
    }


def _banner(title: str) -> str:
    line = "=" * 140
    return f"{line}\r\n{title}\r\n{line}\r\n\r\n"


def write_outputs(evidence_dir: Path, result: dict[str, Any]) -> None:
    payload = {"artifact": "FYBROC_ITEMS_HIERARCHY_MODEL", **result}
    (evidence_dir / "FYBROC_ITEMS_HIERARCHY_MODEL.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    lines = [_banner("F120.1 - FYBROC ITEMS + HIERARCHY MODEL")]
    lines.append(f"Git commit  : {result['git_commit']}\r\nGit clean   : {result['git_working_tree_clean']}\r\n\r\n")

    items = result["items"]
    lines.append(_banner("ITEMS - per-(series, item) field applicability"))
    lines.append(
        f"Fields (F_ prefixed) : {items['field_count']}\r\n"
        f"Series found          : {', '.join(items['series_found'])}\r\n"
        f"Total (series,item) rows : {items['row_count']}\r\n\r\n"
        f"NOT compiled: {items['not_compiled']}\r\n\r\n"
    )
    lines.append(f"{'SERIES':<10}{'ITEM':<10}{'FIELD COUNT':<14}FIELDS\r\n" + "-" * 140 + "\r\n")
    for r in items["rows"]:
        lines.append(f"{r['series']:<10}{r['item']:<10}{r['applicable_field_count']:<14}{', '.join(r['applicable_fields'])}\r\n")
    lines.append("\r\n")

    hierarchy = result["hierarchy"]
    lines.append(_banner("HIERARCHY - field groupings"))
    for g in hierarchy["groups"]:
        lines.append(f"[{g['group']}] ({g['field_count']} fields)\r\n")
        for f in g["fields"]:
            lines.append(f"    {f}\r\n")
        lines.append("\r\n")

    (evidence_dir / "FYBROC_ITEMS_HIERARCHY_MODEL.txt").write_text("".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="F120.1 Fybroc Items + Hierarchy compiler")
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
        "items_field_count": result["items"]["field_count"],
        "items_series_found": result["items"]["series_found"],
        "items_row_count": result["items"]["row_count"],
        "hierarchy_group_count": result["hierarchy"]["group_count"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
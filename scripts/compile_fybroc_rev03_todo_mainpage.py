"""F120.6 - Fybroc Rev0.3 To Do + Main Page + Hierarchy + Combine Variables Compiler.

Roadmap anchor
--------------
docs/PROJECT_MASTER_ROADMAP.md, Section 6, Milestone F120
("Fybroc Rev0.3 Configuration Model") - Items, Hierarchy, Combine Variables.

This compiles four structural sheets from Fybroc Configuration Rev0.3:

1. TO DO SHEET
   Engineering notes: completed items, pending items, and the full
   Horizontal + Vertical spec sheet question lists (field ordering).

2. MAIN PAGE
   Cross-reference matrix: per-series field lists from Selections,
   Items, and Constraints, showing where field lists do/don't match.
   
3. HIERARCHY
   Configuration field ordering and dependency chain for all series.

4. COMBINE VARIABLES
   Composite variable definitions (motor type, motor hp+rpm, etc.)

Inputs:
  workbooks/Fybroc/Fybroc Configuration Rev0.3.xlsx  (read-only)

Outputs:
  docs/evidence/F120/FYBROC_REV03_CONFIGURATION_STRUCTURE.{json,txt}
"""
from __future__ import annotations
import argparse, json, subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
try:
    import openpyxl
except ImportError as exc:
    raise SystemExit("openpyxl required") from exc

STEP = "F120.6"; ROADMAP_VERSION = "1.0"; MILESTONE = "F120"
WORKBOOK_REL = "workbooks/Fybroc/Fybroc Configuration Rev0.3.xlsx"

def git_info(repo_root):
    try:
        c = subprocess.run(["git","rev-parse","HEAD"], cwd=repo_root, capture_output=True, text=True, check=True).stdout.strip()
        s = subprocess.run(["git","status","--porcelain"], cwd=repo_root, capture_output=True, text=True, check=True).stdout
        return c, (s.strip() == "")
    except: return "unknown", False

def _s(v):
    if v is None: return None
    s = str(v).strip(); return s if s else None

# ---------------------------------------------------------------------------
# Section 1 - To Do
# ---------------------------------------------------------------------------
def compile_todo(ws) -> dict[str, Any]:
    completed = []; pending = []
    h_questions = []; v_questions = []

    for r in range(3, ws.max_row + 1):
        date = ws.cell(row=r, column=2).value
        item = _s(ws.cell(row=r, column=3).value)
        field_code = _s(ws.cell(row=r, column=4).value)
        v_item = _s(ws.cell(row=r, column=10).value)
        v_code = _s(ws.cell(row=r, column=11).value)

        # To-do items (rows 3-13 area)
        if item and r <= 13:
            if date:
                completed.append({"date": str(date)[:10], "item": item})
            else:
                pending.append(item)

        # Horizontal questions (col 2=seq, col 3=name, col 4=field_code)
        seq = ws.cell(row=r, column=2).value
        if isinstance(seq, (int, float)) and item and r >= 18:
            h_questions.append({"seq": int(seq), "question": item, "field_code": field_code})

        # Vertical questions (col 9=seq, col 10=name, col 11=field_code)
        v_seq = ws.cell(row=r, column=9).value
        if isinstance(v_seq, (int, float)) and v_item and r >= 18:
            v_questions.append({"seq": int(v_seq), "question": v_item, "field_code": v_code})

    return {
        "completed_items": completed,
        "pending_items": pending,
        "horizontal_questions": sorted(h_questions, key=lambda x: x["seq"]),
        "vertical_questions": sorted(v_questions, key=lambda x: x["seq"]),
        "horizontal_question_count": len(h_questions),
        "vertical_question_count": len(v_questions),
    }

# ---------------------------------------------------------------------------
# Section 2 - Main Page
# ---------------------------------------------------------------------------
def compile_main_page(ws) -> dict[str, Any]:
    # Row 2-4: descriptions of Items/Selections/Constraints
    descriptions = {}
    for r in range(2, 5):
        name = _s(ws.cell(row=r, column=2).value)
        desc = _s(ws.cell(row=r, column=3).value)
        if name and desc:
            descriptions[name] = desc

    # Row 14: series headers
    series_cols = {}
    for c in range(7, ws.max_column + 1, 2):
        series = _s(ws.cell(row=14, column=c).value)
        if series:
            series_cols[series] = c

    # Row 13: "Lists do not match" indicators per series
    mismatch_indicators = []
    for c in range(2, ws.max_column + 1):
        v = _s(ws.cell(row=13, column=c).value)
        if v and "do not match" in v.lower():
            mismatch_indicators.append(c)

    # Col 2-3: "ALL" column (all fields from Selections, Items)
    all_selections = []; all_items = []; all_constraints = []
    for r in range(16, ws.max_row + 1):
        sel = _s(ws.cell(row=r, column=2).value)
        itm = _s(ws.cell(row=r, column=3).value)
        con = _s(ws.cell(row=r, column=4).value)
        if sel: all_selections.append(sel)
        if itm: all_items.append(itm)
        if con: all_constraints.append(con)

    # Per-series field lists
    per_series = {}
    for series, start_col in series_cols.items():
        sel_col = start_col
        items_col = start_col + 1
        sel_fields = []; item_fields = []
        for r in range(16, ws.max_row + 1):
            sv = _s(ws.cell(row=r, column=sel_col).value)
            iv = _s(ws.cell(row=r, column=items_col).value)
            if sv: sel_fields.append(sv)
            if iv: item_fields.append(iv)
        per_series[series] = {
            "from_selections": sel_fields,
            "from_items": item_fields,
            "selections_count": len(sel_fields),
            "items_count": len(item_fields),
            "match": sel_fields == item_fields,
        }

    return {
        "descriptions": descriptions,
        "all_selections_fields": all_selections,
        "all_items_fields": all_items,
        "all_constraints_fields": all_constraints,
        "all_selections_count": len(all_selections),
        "all_items_count": len(all_items),
        "all_constraints_count": len(all_constraints),
        "series_field_lists": per_series,
        "series_count": len(per_series),
        "mismatch_column_count": len(mismatch_indicators),
    }

# ---------------------------------------------------------------------------
# Section 3 - Hierarchy (already compiled in F120.1, reference only)
# ---------------------------------------------------------------------------
def compile_hierarchy(ws) -> dict[str, Any]:
    """Compile the Hierarchy sheet field ordering."""
    # Row 1 = header, data starts row 2
    headers = [_s(ws.cell(row=1, column=c).value) for c in range(1, ws.max_column + 1)]
    headers = [h for h in headers if h]

    rows = []
    for r in range(2, ws.max_row + 1):
        row_data = {}
        empty = True
        for c in range(1, min(len(headers)+1, ws.max_column+1)):
            v = _s(ws.cell(row=r, column=c).value)
            if c <= len(headers):
                row_data[headers[c-1]] = v
            if v: empty = False
        if not empty:
            rows.append(row_data)

    return {
        "headers": headers,
        "row_count": len(rows),
        "rows": rows[:50],  # first 50 for reference
    }

# ---------------------------------------------------------------------------
# Section 4 - Combine Variables (already compiled in F120.4, reference)
# ---------------------------------------------------------------------------
def compile_combine_variables(ws) -> dict[str, Any]:
    """Compile the Combine Variables sheet structure."""
    # Scan for section headers and data patterns
    sections = []
    current_section = None

    for r in range(1, ws.max_row + 1):
        row_data = [_s(ws.cell(row=r, column=c).value) for c in range(1, min(ws.max_column+1, 20))]
        non_none = [(i, v) for i, v in enumerate(row_data) if v]
        if not non_none:
            if current_section and current_section.get("rows"):
                sections.append(current_section)
                current_section = None
            continue
        if current_section is None:
            current_section = {"start_row": r, "header": row_data, "rows": []}
        else:
            current_section["rows"].append({"row": r, "values": [v for _, v in non_none]})

    if current_section and current_section.get("rows"):
        sections.append(current_section)

    return {
        "section_count": len(sections),
        "sections": [
            {
                "start_row": s["start_row"],
                "header_sample": [v for v in s["header"] if v][:10],
                "data_rows": len(s["rows"]),
            }
            for s in sections
        ],
    }

# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------
def build_model(repo_root):
    commit, clean = git_info(repo_root)
    wb = openpyxl.load_workbook(str(repo_root / WORKBOOK_REL), read_only=True, data_only=True)

    todo = compile_todo(wb["To do"])
    main_page = compile_main_page(wb["Main Page"])
    hierarchy = compile_hierarchy(wb["Hierarchy"])
    combine_vars = compile_combine_variables(wb["Combine Variables"])

    wb.close()

    return {
        "step": STEP, "roadmap_version": ROADMAP_VERSION, "milestone": MILESTONE,
        "source_workbook": WORKBOOK_REL,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit, "git_working_tree_clean": clean,
        "todo": todo,
        "main_page": main_page,
        "hierarchy": hierarchy,
        "combine_variables": combine_vars,
    }

def _banner(title):
    return f"{'='*120}\r\n{title}\r\n{'='*120}\r\n\r\n"

def write_outputs(evidence_dir, result):
    payload = {"artifact": "FYBROC_REV03_CONFIGURATION_STRUCTURE", **result}
    (evidence_dir / "FYBROC_REV03_CONFIGURATION_STRUCTURE.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    td = result["todo"]; mp = result["main_page"]
    hi = result["hierarchy"]; cv = result["combine_variables"]

    out = [_banner("F120.6 - FYBROC REV0.3 CONFIGURATION STRUCTURE")]
    out.append(f"Git commit  : {result['git_commit']}\r\nGit clean   : {result['git_working_tree_clean']}\r\n\r\n")

    out.append(_banner("1. TO DO SHEET"))
    out.append("COMPLETED:\r\n")
    for c in td["completed_items"]:
        out.append(f"  [{c['date']}] {c['item']}\r\n")
    out.append("\r\nPENDING:\r\n")
    for p in td["pending_items"]:
        out.append(f"  - {p}\r\n")
    out.append(f"\r\nHORIZONTAL QUESTIONS ({td['horizontal_question_count']}):\r\n")
    for q in td["horizontal_questions"]:
        out.append(f"  {q['seq']:>2}. {q['question']:<35} -> {q['field_code'] or '—'}\r\n")
    out.append(f"\r\nVERTICAL QUESTIONS ({td['vertical_question_count']}):\r\n")
    for q in td["vertical_questions"]:
        out.append(f"  {q['seq']:>2}. {q['question']:<35} -> {q['field_code'] or '—'}\r\n")

    out.append("\r\n" + _banner("2. MAIN PAGE"))
    out.append("DESCRIPTIONS:\r\n")
    for name, desc in mp["descriptions"].items():
        out.append(f"  {name}: {desc}\r\n")
    out.append(f"\r\nALL fields: {mp['all_selections_count']} selections, {mp['all_items_count']} items, {mp['all_constraints_count']} constraints\r\n")
    out.append(f"Mismatch indicators: {mp['mismatch_column_count']} columns marked 'Lists do not match'\r\n")
    out.append(f"Series analyzed: {mp['series_count']}\r\n\r\n")
    for series, info in mp["series_field_lists"].items():
        match_str = "MATCH" if info["match"] else "MISMATCH"
        out.append(f"  {series}: {info['selections_count']} sel / {info['items_count']} items [{match_str}]\r\n")

    out.append("\r\n" + _banner("3. HIERARCHY"))
    out.append(f"Headers: {hi['headers']}\r\nRow count: {hi['row_count']}\r\n\r\n")

    out.append(_banner("4. COMBINE VARIABLES"))
    out.append(f"Sections: {cv['section_count']}\r\n\r\n")
    for s in cv["sections"]:
        out.append(f"  Row {s['start_row']}: {s['header_sample']}  ({s['data_rows']} data rows)\r\n")

    (evidence_dir / "FYBROC_REV03_CONFIGURATION_STRUCTURE.txt").write_text("".join(out), encoding="utf-8")

def main():
    p = argparse.ArgumentParser(); root = Path(__file__).resolve().parent.parent
    p.add_argument("--repo-root", type=Path, default=root)
    p.add_argument("--evidence-dir", type=Path, default=None)
    a = p.parse_args(); repo_root = a.repo_root.resolve()
    ev = (a.evidence_dir or (repo_root / "docs" / "evidence" / "F120")).resolve()
    ev.mkdir(parents=True, exist_ok=True)
    result = build_model(repo_root)
    write_outputs(ev, result)
    td = result["todo"]; mp = result["main_page"]
    print(json.dumps({"step": STEP, "output_dir": str(ev),
        "todo_completed": len(td["completed_items"]), "todo_pending": len(td["pending_items"]),
        "h_questions": td["horizontal_question_count"], "v_questions": td["vertical_question_count"],
        "main_page_series": mp["series_count"], "main_page_all_selections": mp["all_selections_count"],
        "hierarchy_rows": result["hierarchy"]["row_count"],
        "combine_variable_sections": result["combine_variables"]["section_count"]}, indent=2))
    return 0

if __name__ == "__main__": raise SystemExit(main())

"""F120.7 - Fybroc Rev0.3 Pricing Sheets Compiler.

Roadmap anchor
--------------
docs/PROJECT_MASTER_ROADMAP.md, Section 6, Milestone F120/F130
("Fybroc Rev0.3 Configuration Model" / "Fybroc Pricing & Adders").

Compiles the pricing sheets from Fybroc Configuration Rev0.3:

  - Pricing Index (60 rows): catalog of all pricing table definitions
  - 1500 Pricing (2854 rows x 127 cols): multiple side-by-side pricing
    tables for 1500-series horizontal pumps
  - 5500 Pricing (52,445 rows x 71 cols): pricing tables for 5500-series
    vertical pumps (base includes Setting dimension)
  - Sheet3 (scratch/reference data)

This compiler captures the Pricing Index structure, identifies all
pricing table blocks in 1500/5500 sheets, and reports summary statistics
(table count, row counts, price ranges, keys). Full pricing data export
for F130 will build on this foundation.

Inputs:
  workbooks/Fybroc/Fybroc Configuration Rev0.3.xlsx  (read-only)

Outputs:
  docs/evidence/F120/FYBROC_REV03_PRICING_STRUCTURE.{json,txt}
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

STEP = "F120.7"; ROADMAP_VERSION = "1.0"; MILESTONE = "F120"
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
# Pricing Index
# ---------------------------------------------------------------------------
def compile_pricing_index(ws) -> list[dict]:
    """Extract the pricing table catalog."""
    entries = []
    for r in range(3, ws.max_row + 1):
        opt1 = _s(ws.cell(row=r, column=3).value)
        opt2 = _s(ws.cell(row=r, column=4).value)
        opt3 = _s(ws.cell(row=r, column=5).value)
        opt4 = _s(ws.cell(row=r, column=6).value)
        desc = _s(ws.cell(row=r, column=7).value)
        if opt1 or desc:
            entries.append({
                "key1": opt1, "key2": opt2, "key3": opt3, "key4": opt4,
                "description": desc,
            })
    return entries

# ---------------------------------------------------------------------------
# 1500 Pricing - identify table blocks by scanning row 3-5 area for headers
# ---------------------------------------------------------------------------
def compile_1500_pricing(ws) -> dict[str, Any]:
    """Scan the 1500 Pricing sheet for table blocks."""
    # The sheet has multiple tables side-by-side in column groups.
    # Row 3 has table descriptions, row 5 has column headers.
    # Identify table start columns by scanning row 3 for description text.
    table_blocks = []

    # Scan row 3 for table descriptions (these span the width)
    r3_descs = []
    for c in range(2, ws.max_column + 1):
        v = _s(ws.cell(row=3, column=c).value)
        if v:
            r3_descs.append((c, v))

    # Scan row 5 for column headers
    r5_headers = []
    for c in range(2, ws.max_column + 1):
        v = _s(ws.cell(row=5, column=c).value)
        if v:
            r5_headers.append((c, v))

    # Build table blocks: each description in row 3 starts a block
    # The block's columns are those with headers in row 5 until the next block
    for i, (start_col, desc) in enumerate(r3_descs):
        # Find end col (next description start - 1, or max)
        end_col = (r3_descs[i+1][0] - 1 if i+1 < len(r3_descs) else ws.max_column)

        # Get headers for this block
        block_headers = [(c, h) for c, h in r5_headers if start_col <= c <= end_col]

        # Count data rows for the first column in block (cap at 200 for speed)
        data_count = 0
        if block_headers:
            first_data_col = block_headers[0][0]
            for r in range(6, min(ws.max_row + 1, 206)):
                if ws.cell(row=r, column=first_data_col).value is not None:
                    data_count += 1
                else:
                    break
            if data_count >= 200:
                data_count = ws.max_row - 5  # full sheet estimate

        # Sample first 3 data rows
        samples = []
        if block_headers:
            for r in range(6, min(9, ws.max_row + 1)):
                row_vals = {h: _s(ws.cell(row=r, column=c).value) for c, h in block_headers}
                if any(v for v in row_vals.values()):
                    samples.append(row_vals)

        table_blocks.append({
            "start_col": start_col,
            "description": desc,
            "headers": [h for _, h in block_headers],
            "data_rows": data_count,
            "sample_rows": samples,
        })

    return {
        "sheet_dimensions": {"max_row": ws.max_row, "max_col": ws.max_column},
        "status": _s(ws.cell(row=1, column=3).value),
        "table_blocks": table_blocks,
        "table_count": len(table_blocks),
    }

# ---------------------------------------------------------------------------
# 5500 Pricing
# ---------------------------------------------------------------------------
def compile_5500_pricing(ws) -> dict[str, Any]:
    """Scan 5500 Pricing for table blocks - headers and structure only."""
    table_blocks = []

    # Row 5 headers - identify table blocks by consecutive header groups
    r5_headers = []
    for c in range(2, ws.max_column + 1):
        v = _s(ws.cell(row=5, column=c).value)
        if v:
            r5_headers.append((c, v))

    # Row 1-4 descriptions
    descs = {}
    for r in range(1, 5):
        for c in range(2, ws.max_column + 1):
            v = _s(ws.cell(row=r, column=c).value)
            if v and c not in descs:
                descs[c] = v

    # Group headers into table blocks (separated by gaps)
    blocks = []
    current_block = []
    for i, (c, h) in enumerate(r5_headers):
        if current_block and c - r5_headers[i-1][0] > 1:
            blocks.append(current_block)
            current_block = []
        current_block.append((c, h))
    if current_block:
        blocks.append(current_block)

    for block in blocks:
        start_col = block[0][0]
        headers = [h for _, h in block]
        desc = descs.get(start_col, descs.get(start_col - 1, ""))

        # Sample first 3 data rows only
        samples = []
        for r in range(6, 9):
            row_vals = {h: _s(ws.cell(row=r, column=c).value) for c, h in block}
            if any(v for v in row_vals.values()):
                samples.append(row_vals)

        table_blocks.append({
            "start_col": start_col,
            "description": desc,
            "headers": headers,
            "data_rows_estimated": ws.max_row - 5,
            "sample_rows": samples,
        })

    return {
        "sheet_dimensions": {"max_row": ws.max_row, "max_col": ws.max_column},
        "table_blocks": table_blocks,
        "table_count": len(table_blocks),
    }

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def build_model(repo_root):
    commit, clean = git_info(repo_root)
    wb = openpyxl.load_workbook(str(repo_root / WORKBOOK_REL), read_only=True, data_only=True)

    pricing_index = compile_pricing_index(wb["Pricing Index"])
    p1500 = compile_1500_pricing(wb["1500 Pricing"])
    p5500 = compile_5500_pricing(wb["5500 Pricing"])

    wb.close()

    return {
        "step": STEP, "roadmap_version": ROADMAP_VERSION, "milestone": MILESTONE,
        "source_workbook": WORKBOOK_REL,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit, "git_working_tree_clean": clean,
        "pricing_index": {
            "entry_count": len(pricing_index),
            "entries": pricing_index,
        },
        "pricing_1500": p1500,
        "pricing_5500": p5500,
    }

def _banner(title):
    return f"{'='*120}\r\n{title}\r\n{'='*120}\r\n\r\n"

def write_outputs(evidence_dir, result):
    payload = {"artifact": "FYBROC_REV03_PRICING_STRUCTURE", **result}
    (evidence_dir / "FYBROC_REV03_PRICING_STRUCTURE.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    pi = result["pricing_index"]
    p1 = result["pricing_1500"]
    p5 = result["pricing_5500"]

    out = [_banner("F120.7 - FYBROC REV0.3 PRICING STRUCTURE")]
    out.append(f"Git commit  : {result['git_commit']}\r\nGit clean   : {result['git_working_tree_clean']}\r\n\r\n")

    out.append(_banner("PRICING INDEX"))
    out.append(f"Entries: {pi['entry_count']}\r\n\r\n")
    for e in pi["entries"]:
        keys = " x ".join(filter(None, [e["key1"], e["key2"], e["key3"], e["key4"]]))
        out.append(f"  {keys:<60} {e['description'] or ''}\r\n")

    out.append("\r\n" + _banner("1500 PRICING"))
    out.append(f"Status: {p1['status']}\r\n")
    out.append(f"Sheet: {p1['sheet_dimensions']['max_row']} rows x {p1['sheet_dimensions']['max_col']} cols\r\n")
    out.append(f"Table blocks: {p1['table_count']}\r\n\r\n")
    for tb in p1["table_blocks"]:
        out.append(f"  Col {tb['start_col']}: {tb['description']}\r\n")
        out.append(f"    Headers: {tb['headers']}\r\n")
        out.append(f"    Data rows: {tb['data_rows']}\r\n\r\n")

    out.append(_banner("5500 PRICING"))
    out.append(f"Sheet: {p5['sheet_dimensions']['max_row']} rows x {p5['sheet_dimensions']['max_col']} cols\r\n")
    out.append(f"Table blocks: {p5['table_count']}\r\n\r\n")
    for tb in p5["table_blocks"]:
        out.append(f"  Col {tb['start_col']}: {tb['description']}\r\n")
        out.append(f"    Headers: {tb['headers']}\r\n")
        out.append(f"    Data rows (est): {tb['data_rows_estimated']}\r\n\r\n")

    (evidence_dir / "FYBROC_REV03_PRICING_STRUCTURE.txt").write_text("".join(out), encoding="utf-8")

def main():
    p = argparse.ArgumentParser(); root = Path(__file__).resolve().parent.parent
    p.add_argument("--repo-root", type=Path, default=root)
    p.add_argument("--evidence-dir", type=Path, default=None)
    a = p.parse_args(); repo_root = a.repo_root.resolve()
    ev = (a.evidence_dir or (repo_root / "docs" / "evidence" / "F120")).resolve()
    ev.mkdir(parents=True, exist_ok=True)
    result = build_model(repo_root)
    write_outputs(ev, result)
    pi = result["pricing_index"]; p1 = result["pricing_1500"]; p5 = result["pricing_5500"]
    print(json.dumps({"step": STEP, "output_dir": str(ev),
        "pricing_index_entries": pi["entry_count"],
        "p1500_table_blocks": p1["table_count"], "p1500_status": p1["status"],
        "p5500_table_blocks": p5["table_count"],
        "p1500_dimensions": p1["sheet_dimensions"],
        "p5500_dimensions": p5["sheet_dimensions"]}, indent=2))
    return 0

if __name__ == "__main__": raise SystemExit(main())

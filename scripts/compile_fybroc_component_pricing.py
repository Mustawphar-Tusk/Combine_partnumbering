"""F130.3 - Fybroc Price Estimator Component Pricing Compiler.

Roadmap anchor
--------------
docs/PROJECT_MASTER_ROADMAP.md, Section 6, Milestone F130.

Compiles the component pricing sheets from Price Estimator-Fybroc.xlsm:

  1. COUPLING - Part number lookup by Group/RPM x Motor Frame (248 rows)
  2. BASEPLATE - Price + part number by Series/Option x Motor Frame (367 rows)
  3. M-$ - Motor pricing tables (TEFC, SD enclosures, H/V orientations)

Each component contributes to the total configured pump price and is
selected based on the pump configuration (series, size, motor selection).

Inputs:
  workbooks/Fybroc/Price Estimator-Fybroc.xlsm  (read-only)

Outputs:
  docs/evidence/F130/FYBROC_COMPONENT_PRICING.{json,txt}
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

STEP = "F130.3"; ROADMAP_VERSION = "1.1"; MILESTONE = "F130"
WORKBOOK_REL = "workbooks/Fybroc/Price Estimator-Fybroc.xlsm"


def git_info(repo_root):
    try:
        c = subprocess.run(["git","rev-parse","HEAD"], cwd=repo_root, capture_output=True, text=True, check=True).stdout.strip()
        s = subprocess.run(["git","status","--porcelain"], cwd=repo_root, capture_output=True, text=True, check=True).stdout
        return c, (s.strip() == "")
    except: return "unknown", False

def _s(v):
    if v is None: return None
    s = str(v).strip(); return s if s else None


def compile_coupling(ws) -> dict[str, Any]:
    """Coupling: Group/RPM rows x Motor Frame columns -> coupling part numbers."""
    # Row 4 = frame headers (143T, 145T, ..., cols 3+)
    frames = []
    for c in range(3, 40):
        v = _s(ws.cell(row=4, column=c).value)
        if v:
            frames.append((c, v))

    # Data rows 5+ until blank in col 1
    rows = []
    for r in range(5, min(ws.max_row + 1, 50)):
        model = _s(ws.cell(row=r, column=1).value)
        rpm = ws.cell(row=r, column=2).value
        if not model:
            break
        couplings = {}
        for c, frame in frames:
            v = _s(ws.cell(row=r, column=c).value)
            if v:
                couplings[frame] = v
        rows.append({"model": model, "rpm": rpm, "couplings": couplings})

    return {
        "sheet": "Coupling",
        "frame_columns": [f for _, f in frames],
        "frame_count": len(frames),
        "data_rows": len(rows),
        "rows": rows,
    }


def compile_baseplate(ws) -> dict[str, Any]:
    """Baseplate: Series/Option rows x Motor Frame columns -> prices + part numbers."""
    # Row 5 = frame headers (cols 2+)
    frames = []
    for c in range(2, 25):
        v = _s(ws.cell(row=5, column=c).value)
        if v:
            frames.append((c, v))

    # Data rows - alternating price ($ - ...) and part number rows
    sections = []
    current_series = _s(ws.cell(row=5, column=1).value)  # "1500"

    for r in range(6, min(ws.max_row + 1, 100)):
        label = _s(ws.cell(row=r, column=1).value)
        if not label:
            continue
        # Check if this is a new series header
        if label in ("1530", "1600", "1630", "2530", "3000", "5500"):
            current_series = label
            continue
        # Read row values
        vals = {}
        for c, frame in frames:
            v = ws.cell(row=r, column=c).value
            if v is not None:
                vals[frame] = v
        sections.append({
            "series": current_series,
            "label": label,
            "is_price_row": label.startswith("$"),
            "sample_values": dict(list(vals.items())[:5]),
        })

    return {
        "sheet": "Baseplate",
        "frame_columns": [f for _, f in frames],
        "frame_count": len(frames),
        "total_rows": len(sections),
        "series_found": sorted(set(s["series"] for s in sections)),
        "rows": sections[:40],  # first 40 for reference
    }


def compile_motor_pricing(ws) -> dict[str, Any]:
    """M-$ motor pricing: multiple side-by-side tables by enclosure/orientation."""
    # Scan row 1-2 for table block titles, row 7-8 for table IDs/headers
    blocks = []

    # Row 1 descriptions
    r1_descs = [(c, _s(ws.cell(row=1, column=c).value))
                for c in range(1, 50)
                if ws.cell(row=1, column=c).value]

    # Row 7 table IDs
    r7_ids = [(c, _s(ws.cell(row=7, column=c).value))
              for c in range(1, 50)
              if ws.cell(row=7, column=c).value]

    # Row 8 column headers
    r8_headers = [(c, _s(ws.cell(row=8, column=c).value))
                  for c in range(1, 50)
                  if ws.cell(row=8, column=c).value]

    # Group by table blocks (row 7 has identifiers like 'HorTFrameTEncPeff')
    for col, table_id in r7_ids:
        # Find description from row 1 nearest to this col
        desc = ""
        for dc, dv in r1_descs:
            if dc <= col:
                desc = dv
        # Get headers in this block's vicinity
        block_headers = [h for c, h in r8_headers if col <= c < col + 7]
        # Count data rows
        data_count = 0
        for r in range(9, min(ws.max_row + 1, 280)):
            if ws.cell(row=r, column=col).value is not None:
                data_count += 1
            else:
                break

        blocks.append({
            "col": col,
            "table_id": table_id,
            "description": desc,
            "headers": block_headers,
            "data_rows": data_count,
        })

    return {
        "sheet": "M-$",
        "dimensions": {"max_row": ws.max_row, "max_col": ws.max_column},
        "table_blocks": blocks,
        "block_count": len(blocks),
    }


def build_model(repo_root):
    commit, clean = git_info(repo_root)
    wb = openpyxl.load_workbook(str(repo_root / WORKBOOK_REL), read_only=True, data_only=True)

    coupling = compile_coupling(wb["Coupling"])
    baseplate = compile_baseplate(wb["Baseplate"])
    motor = compile_motor_pricing(wb["M-$"])

    wb.close()

    return {
        "step": STEP, "roadmap_version": ROADMAP_VERSION, "milestone": MILESTONE,
        "source_workbook": WORKBOOK_REL,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit, "git_working_tree_clean": clean,
        "coupling": coupling,
        "baseplate": baseplate,
        "motor_pricing": motor,
    }


def _banner(title):
    return f"{'='*120}\r\n{title}\r\n{'='*120}\r\n\r\n"

def write_outputs(evidence_dir, result):
    payload = {"artifact": "FYBROC_COMPONENT_PRICING", **result}
    (evidence_dir / "FYBROC_COMPONENT_PRICING.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    cp = result["coupling"]; bp = result["baseplate"]; mp = result["motor_pricing"]
    out = [_banner("F130.3 - FYBROC COMPONENT PRICING")]
    out.append(f"Git commit  : {result['git_commit']}\r\nGit clean   : {result['git_working_tree_clean']}\r\n\r\n")

    out.append(_banner("COUPLING"))
    out.append(f"Frames: {cp['frame_count']} ({', '.join(cp['frame_columns'][:10])}...)\r\n")
    out.append(f"Data rows: {cp['data_rows']}\r\n\r\n")
    for r in cp["rows"][:10]:
        out.append(f"  {r['model']:<25} RPM={r['rpm']}  (sample: {dict(list(r['couplings'].items())[:3])})\r\n")

    out.append("\r\n" + _banner("BASEPLATE"))
    out.append(f"Frames: {bp['frame_count']} ({', '.join(bp['frame_columns'][:10])}...)\r\n")
    out.append(f"Series found: {bp['series_found']}\r\n")
    out.append(f"Total rows: {bp['total_rows']}\r\n\r\n")
    for r in bp["rows"][:15]:
        out.append(f"  [{r['series']}] {r['label']:<50} price_row={r['is_price_row']}\r\n")

    out.append("\r\n" + _banner("MOTOR PRICING (M-$)"))
    out.append(f"Dimensions: {mp['dimensions']}\r\n")
    out.append(f"Table blocks: {mp['block_count']}\r\n\r\n")
    for b in mp["table_blocks"]:
        out.append(f"  Col {b['col']}: {b['table_id']:<30} desc={b['description']:<40} headers={b['headers']} rows={b['data_rows']}\r\n")

    (evidence_dir / "FYBROC_COMPONENT_PRICING.txt").write_text("".join(out), encoding="utf-8")


def main():
    p = argparse.ArgumentParser(); root = Path(__file__).resolve().parent.parent
    p.add_argument("--repo-root", type=Path, default=root)
    p.add_argument("--evidence-dir", type=Path, default=None)
    a = p.parse_args(); repo_root = a.repo_root.resolve()
    ev = (a.evidence_dir or (repo_root / "docs" / "evidence" / "F130")).resolve()
    ev.mkdir(parents=True, exist_ok=True)
    result = build_model(repo_root)
    write_outputs(ev, result)
    print(json.dumps({
        "step": STEP, "output_dir": str(ev),
        "coupling_rows": result["coupling"]["data_rows"],
        "coupling_frames": result["coupling"]["frame_count"],
        "baseplate_series": result["baseplate"]["series_found"],
        "baseplate_rows": result["baseplate"]["total_rows"],
        "motor_blocks": result["motor_pricing"]["block_count"],
    }, indent=2))
    return 0

if __name__ == "__main__": raise SystemExit(main())

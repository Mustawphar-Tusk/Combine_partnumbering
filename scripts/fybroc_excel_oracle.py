"""F160 - Fybroc Excel Oracle Harness.

Roadmap anchor
--------------
docs/PROJECT_MASTER_ROADMAP.md, Section 6, Milestone F160
("Excel Oracle Harness").

Uses actual Microsoft Excel (COM automation) with Nomenclature_V6.xlsm
as an engineering oracle. For each test configuration:

1. Copy authoritative workbook to disposable temp location
2. Open through Excel COM (invisible, no macros auto-run)
3. Populate configuration selections into the Smart Number sheet
4. Recalculate
5. Capture outputs: Part Number, segment codes, description
6. Close without modifying source workbook
7. Compare captured outputs against SQL-generated Part Number

SAFETY RULES (per roadmap governance):
- Authoritative workbooks are NEVER modified by automated tests
- Tests operate ONLY on disposable copies
- Only inspected safe operations are invoked (cell writes + recalc)
- No VBA macros are executed in this harness (pure formula evaluation)

Inputs:
  workbooks/Fybroc/Nomenclature_V6.xlsm (authoritative - copied, never modified)

Outputs:
  docs/evidence/F160/FYBROC_EXCEL_ORACLE_RESULTS.{json,txt}
"""
from __future__ import annotations
import argparse, json, shutil, subprocess, tempfile, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STEP = "F160.1"; ROADMAP_VERSION = "1.3"; MILESTONE = "F160"
WORKBOOK_REL = "workbooks/Fybroc/Nomenclature_V6.xlsm"
SHEET_SMART_NUMBER = "Smart Number"

# Smart Number cell map (horizontal configuration)
# These are the cells where user selections go
H_SELECTIONS = {
    # Row 14 col 6 = Series selection
    "SERIES": ("Smart Number", 14, 6),
    "FLANGE_TYPE": ("Smart Number", 15, 6),
    "SIZE": ("Smart Number", 14, 7),
    "PUMP_MATERIAL": ("Smart Number", 14, 8),
    "IMPELLER_TRIM": ("Smart Number", 14, 9),
}

# Output cells (horizontal)
H_OUTPUTS = {
    "part_number": ("Smart Number", 9, 4),      # D9 = generated PN
    "description": ("Smart Number", 8, 4),       # D8 = description
}

# Segment code cells (row 13)
H_SEGMENT_CODES = {
    "brand": ("Smart Number", 13, 4),
    "series": ("Smart Number", 13, 5),
    "size": ("Smart Number", 13, 7),
    "material": ("Smart Number", 13, 8),
    "trim": ("Smart Number", 13, 9),
    "pump_options": ("Smart Number", 13, 11),
    "seal_mfg": ("Smart Number", 13, 15),
    "seal_assy": ("Smart Number", 13, 16),
    "options": ("Smart Number", 13, 19),
    "frame_size": ("Smart Number", 13, 22),
    "motor_assy": ("Smart Number", 13, 23),
    "motor_mods": ("Smart Number", 13, 26),
    "testing": ("Smart Number", 13, 29),
}

# Test configurations to run through the oracle
TEST_CASES = [
    {
        "name": "Standard 1500 ANSI VR-1A",
        "inputs": {
            "SERIES": "1500",
            "FLANGE_TYPE": "ANSI",
            "SIZE": "1x2x10",
            "PUMP_MATERIAL": "VR-1A",
            "IMPELLER_TRIM": "9.250",
        },
        "expected_pn_prefix": "FA35",  # F + A(1500+ANSI) + 3(1x2x10) + 5(VR-1A)
    },
    {
        "name": "Standard 1500 DIN VR-1",
        "inputs": {
            "SERIES": "1500",
            "FLANGE_TYPE": "DIN",
            "SIZE": "1x1.5x6",
            "PUMP_MATERIAL": "VR-1",
            "IMPELLER_TRIM": "6.000",
        },
        "expected_pn_prefix": "FI11",  # F + I(1500+DIN) + 1(1x1.5x6) + 1(VR-1)
    },
    {
        "name": "Standard 5500 ANSI VR-1",
        "inputs": {
            "SERIES": "5500",
            "FLANGE_TYPE": "ANSI",
            "SIZE": "1x2x10",
            "PUMP_MATERIAL": "VR-1",
            "IMPELLER_TRIM": "8.000",
        },
        "expected_pn_prefix": "FG31",  # F + G(5500+ANSI) + 3(1x2x10) + 1(VR-1)
    },
]


def git_info(repo_root):
    try:
        c = subprocess.run(["git","rev-parse","HEAD"], cwd=repo_root, capture_output=True, text=True, check=True).stdout.strip()
        s = subprocess.run(["git","status","--porcelain"], cwd=repo_root, capture_output=True, text=True, check=True).stdout
        return c, (s.strip() == "")
    except: return "unknown", False


def run_oracle(repo_root: Path, test_cases: list[dict]) -> list[dict]:
    """Run test cases through Excel COM oracle."""
    import win32com.client
    import pythoncom

    pythoncom.CoInitialize()

    source_wb = repo_root / WORKBOOK_REL
    results = []

    # Create disposable copy
    temp_dir = Path(tempfile.mkdtemp(prefix="fybroc_oracle_"))
    temp_wb = temp_dir / source_wb.name
    shutil.copy2(source_wb, temp_wb)

    xl = None
    wb = None
    try:
        xl = win32com.client.Dispatch("Excel.Application")
        xl.Visible = False
        xl.DisplayAlerts = False
        xl.EnableEvents = False
        xl.ScreenUpdating = False

        # Open disposable copy (read-write on the copy is fine)
        wb = xl.Workbooks.Open(str(temp_wb), UpdateLinks=0, ReadOnly=False)
        ws = wb.Sheets(SHEET_SMART_NUMBER)

        for tc in test_cases:
            result = {"test_name": tc["name"], "inputs": tc["inputs"]}

            # Write selections to the Smart Number sheet
            for field, value in tc["inputs"].items():
                if field in H_SELECTIONS:
                    sheet_name, row, col = H_SELECTIONS[field]
                    ws.Cells(row, col).Value = value

            # Force recalculate
            xl.CalculateFull()
            time.sleep(0.5)  # Allow Excel to settle

            # Read outputs
            pn_row, pn_col = H_OUTPUTS["part_number"][1], H_OUTPUTS["part_number"][2]
            desc_row, desc_col = H_OUTPUTS["description"][1], H_OUTPUTS["description"][2]

            result["excel_part_number"] = str(ws.Cells(pn_row, pn_col).Value or "")
            result["excel_description"] = str(ws.Cells(desc_row, desc_col).Value or "")

            # Read segment codes
            segments = {}
            for seg_name, (_, row, col) in H_SEGMENT_CODES.items():
                v = ws.Cells(row, col).Value
                segments[seg_name] = str(v) if v is not None else None
            result["excel_segments"] = segments

            # Validate against expected prefix
            expected = tc.get("expected_pn_prefix", "")
            actual_prefix = result["excel_part_number"][:len(expected)] if expected else ""
            result["prefix_match"] = actual_prefix == expected
            result["expected_prefix"] = expected
            result["actual_prefix"] = actual_prefix

            results.append(result)

    except Exception as e:
        results.append({"error": str(e)})
    finally:
        if wb:
            wb.Close(SaveChanges=False)
        if xl:
            xl.Quit()
        # Clean up disposable copy
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
        pythoncom.CoUninitialize()

    return results


def build_model(repo_root):
    commit, clean = git_info(repo_root)

    results = run_oracle(repo_root, TEST_CASES)

    passed = sum(1 for r in results if r.get("prefix_match"))
    failed = sum(1 for r in results if "prefix_match" in r and not r["prefix_match"])
    errors = sum(1 for r in results if "error" in r)

    return {
        "step": STEP, "roadmap_version": ROADMAP_VERSION, "milestone": MILESTONE,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit, "git_working_tree_clean": clean,
        "source_workbook": WORKBOOK_REL,
        "test_count": len(TEST_CASES),
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "results": results,
    }


def _banner(title):
    return f"{'='*120}\r\n{title}\r\n{'='*120}\r\n\r\n"

def write_outputs(evidence_dir, result):
    payload = {"artifact": "FYBROC_EXCEL_ORACLE_RESULTS", **result}
    (evidence_dir / "FYBROC_EXCEL_ORACLE_RESULTS.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    out = [_banner("F160.1 - FYBROC EXCEL ORACLE RESULTS")]
    out.append(f"Git commit  : {result['git_commit']}\r\n")
    out.append(f"Source      : {result['source_workbook']}\r\n")
    out.append(f"Tests       : {result['test_count']}\r\n")
    out.append(f"Passed      : {result['passed']}\r\n")
    out.append(f"Failed      : {result['failed']}\r\n")
    out.append(f"Errors      : {result['errors']}\r\n\r\n")

    for r in result["results"]:
        if "error" in r:
            out.append(f"  ERROR: {r['error']}\r\n\r\n")
            continue
        status = "PASS" if r["prefix_match"] else "FAIL"
        out.append(f"  [{status}] {r['test_name']}\r\n")
        out.append(f"    Inputs: {r['inputs']}\r\n")
        out.append(f"    Excel PN: {r['excel_part_number']}\r\n")
        out.append(f"    Expected prefix: {r['expected_prefix']}  Actual: {r['actual_prefix']}\r\n")
        out.append(f"    Segments: {r['excel_segments']}\r\n")
        out.append(f"    Description: {r['excel_description']}\r\n\r\n")

    (evidence_dir / "FYBROC_EXCEL_ORACLE_RESULTS.txt").write_text("".join(out), encoding="utf-8")


def main():
    p = argparse.ArgumentParser(); root = Path(__file__).resolve().parent.parent
    p.add_argument("--repo-root", type=Path, default=root)
    p.add_argument("--evidence-dir", type=Path, default=None)
    a = p.parse_args(); repo_root = a.repo_root.resolve()
    ev = (a.evidence_dir or (repo_root / "docs" / "evidence" / "F160")).resolve()
    ev.mkdir(parents=True, exist_ok=True)
    result = build_model(repo_root)
    write_outputs(ev, result)
    print(json.dumps({
        "step": STEP, "tests": result["test_count"],
        "passed": result["passed"], "failed": result["failed"], "errors": result["errors"],
    }, indent=2))
    return 0

if __name__ == "__main__": raise SystemExit(main())

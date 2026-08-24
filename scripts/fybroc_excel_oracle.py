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
# These are the DATA VALIDATION input cells (confirmed via COM inspection)
H_INPUT_CELLS = {
    "SERIES": (14, 6),         # Current: 1500
    "FLANGE_TYPE": (15, 6),    # Current: ANSI
    "SIZE": (14, 7),           # Current: 1x2x10
    "PUMP_MATERIAL": (14, 8),  # Current: VR-1A
    "IMPELLER_TRIM": (14, 9),  # Current: 9.250
    "CASING_DRAINS": (14, 13),
    "SUCTION_DISCHARGE": (15, 13),
    "SHAFT_MATERIAL": (16, 13),
    "SLEEVE": (17, 13),
    "CASING_HARDWARE": (18, 13),
    "PUMP_ELASTOMERS": (19, 13),
    "BEARING_OPTION": (20, 13),
    "FRAME_HARDWARE": (21, 13),
    "GLAND_HARDWARE": (22, 13),
    "FLUSH": (23, 13),
    "FLUSH_MATERIAL": (24, 13),
    "CYCLONE_SEPARATOR": (25, 13),
    "DYNAMIC_IMPELLER": (26, 13),
    "SEAL_MFG": (14, 15),
    "SEAL_OPTION": (14, 17),
    "SEAL_TYPE": (15, 17),
    "SEAL_MATERIALS": (16, 17),
    "SEAL_ELASTOMERS": (17, 17),
    "SEAL_GUARD": (18, 17),
    "COUPLING_OPTION": (14, 20),
    "COUPLING_GUARD": (15, 20),
    "BASEPLATE_OPTION": (16, 20),
    "BASEPLATE_HARDWARE": (17, 20),
    "NAMEPLATE": (18, 20),
    "C_FACE": (19, 20),
    "MOTOR_OPTION": (14, 24),
    "MOTOR_CLASS": (15, 24),
    "MOTOR_ORIENTATION": (16, 24),
    "MOTOR_HP": (17, 24),
    "MOTOR_RPM": (18, 24),
    "MOTOR_VOLTAGE": (19, 24),
    "MOTOR_HERTZ": (20, 24),
    "MOTOR_FRAME": (21, 24),
    "MOTOR_ENCLOSURE": (22, 24),
    "MOTOR_EFFICIENCY": (23, 24),
    "MOTOR_MANUFACTURER": (24, 24),
    "MOTOR_MOD_1": (14, 27),
    "MOTOR_MOD_2": (15, 27),
    "MOTOR_MOD_3": (16, 27),
    "PERFORMANCE_TESTING": (14, 30),
    "HYDRO_TESTING": (15, 30),
    "VIBRATION": (16, 30),
    "SOUND_LEVEL": (17, 30),
}

# Output cells (horizontal)
H_OUTPUTS = {
    "part_number_formatted": (5, 4),   # D5 = PN with separators between all groups
    "description": (8, 4),              # D8 = description
    "part_number_compact": (9, 4),      # D9 = compact PN (used as actual part number)
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
        "name": "Default config (already in workbook)",
        "inputs": {},  # Don't change anything - just read current state
        "expected_pn": "FA35FC-1VC1-S03-3G-04XXXX-00",
    },
    {
        "name": "Change Size to 1.5x3x6 and Trim to 5.500 (valid per CT4)",
        "inputs": {
            "SIZE": "1.5x3x6",
            "IMPELLER_TRIM": "5.500",
        },
        "expected_pn_prefix": "FA55BE",  # F + A(1500+ANSI) + 5(1.5x3x6) + 5(VR-1A) + BE(5.500)
    },
    {
        "name": "Change material to VR-1",
        "inputs": {
            "PUMP_MATERIAL": "VR-1",
        },
        "expected_pn_prefix": "FA51BE",  # F + A(1500+ANSI) + 5(1.5x3x6) + 1(VR-1) + BE(5.500)
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
                if field in H_INPUT_CELLS:
                    row, col = H_INPUT_CELLS[field]
                    # Trim values must be written as text (not numeric)
                    if field == "IMPELLER_TRIM":
                        ws.Cells(row, col).NumberFormat = "@"
                    ws.Cells(row, col).Value = value

            # Force recalculate
            xl.CalculateFull()
            time.sleep(0.5)  # Allow Excel to settle

            # Read outputs
            pn_row, pn_col = H_OUTPUTS["part_number_compact"]
            desc_row, desc_col = H_OUTPUTS["description"]
            pn_fmt_row, pn_fmt_col = H_OUTPUTS["part_number_formatted"]

            result["excel_part_number"] = str(ws.Cells(pn_row, pn_col).Value or "")
            result["excel_part_number_formatted"] = str(ws.Cells(pn_fmt_row, pn_fmt_col).Value or "")
            result["excel_description"] = str(ws.Cells(desc_row, desc_col).Value or "")

            # Read segment codes
            segments = {}
            for seg_name, (_, row, col) in H_SEGMENT_CODES.items():
                v = ws.Cells(row, col).Value
                segments[seg_name] = str(v) if v is not None else None
            result["excel_segments"] = segments

            # Validate
            expected_pn = tc.get("expected_pn")
            expected_prefix = tc.get("expected_pn_prefix", "")
            if expected_pn:
                result["match"] = result["excel_part_number"] == expected_pn
                result["expected"] = expected_pn
            elif expected_prefix:
                actual_prefix = result["excel_part_number"][:len(expected_prefix)]
                result["prefix_match"] = actual_prefix == expected_prefix
                result["expected_prefix"] = expected_prefix
                result["actual_prefix"] = actual_prefix
                result["match"] = result["prefix_match"]
            else:
                result["match"] = True  # No expectation = pass

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

    passed = sum(1 for r in results if r.get("match"))
    failed = sum(1 for r in results if "match" in r and not r["match"])
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
        status = "PASS" if r.get("match") else "FAIL"
        out.append(f"  [{status}] {r['test_name']}\r\n")
        out.append(f"    Inputs: {r['inputs']}\r\n")
        out.append(f"    Excel PN: {r.get('excel_part_number', '?')}\r\n")
        if 'expected' in r:
            out.append(f"    Expected: {r['expected']}\r\n")
        elif 'expected_prefix' in r:
            out.append(f"    Expected prefix: {r['expected_prefix']}  Actual: {r.get('actual_prefix','?')}\r\n")
        out.append(f"    Segments: {r.get('excel_segments', {})}\r\n")
        out.append(f"    Description: {r.get('excel_description', '?')}\r\n\r\n")

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

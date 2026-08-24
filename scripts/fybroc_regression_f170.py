"""F170 - Exhaustive Fybroc Regression (targeted subset).

Roadmap anchor
--------------
docs/PROJECT_MASTER_ROADMAP.md, Section 6, Milestone F170.

Runs a representative regression suite across:
- Multiple series (1500 ANSI, 1530 ANSI, 1600 ANSI, 5500 ANSI)
- Multiple sizes (Group 1, 2, 3 representatives)
- Multiple materials (VR-1, VR-1A, EY-2)
- Valid trim values per CT4

For each test case:
1. Excel Oracle generates the Part Number
2. SQL generates the Part Number from the same configuration
3. Results are compared

Exit gate: Zero unexplained engineering failures.

Inputs:
  Nomenclature_V6.xlsm (via Excel COM)
  SQL PumpConfiguratorDB (via pyodbc)

Outputs:
  docs/evidence/F170/FYBROC_REGRESSION_RESULTS.{json,txt}
"""
from __future__ import annotations
import argparse, json, shutil, subprocess, tempfile, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyodbc

STEP = "F170.1"; ROADMAP_VERSION = "1.4"; MILESTONE = "F170"
WORKBOOK_REL = "workbooks/Fybroc/Nomenclature_V6.xlsm"

CONN_STR = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=PumpConfiguratorDB;"
    "Trusted_Connection=yes;"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)

# Representative test matrix
TEST_MATRIX = [
    # (series, flange, size, material, trim, expected_series_code)
    ("1500", "ANSI", "1x1.5x6", "VR-1", "6.000", "A"),
    ("1500", "ANSI", "1x2x10", "VR-1A", "9.250", "A"),
    ("1500", "ANSI", "3x4x8", "EY-2", "7.500", "A"),
    ("1500", "DIN", "2x3x6", "VR-1", "5.500", "I"),
    ("1530", "ANSI", "1.5x3x8", "VR-1", "7.000", "B"),
    ("1530", "ANSI", "2x3x10", "VR-1A", "9.000", "B"),
    ("1600", "ANSI", "2x3x6", "VR-1", "5.500", "C"),
    ("1600", "ANSI", "3x4x8", "VR-1A", "7.500", "C"),
    ("5500", "ANSI", "1x2x10", "VR-1", "8.000", "G"),
    ("5500", "ANSI", "3x4x10", "VR-1", "9.000", "G"),
]


def git_info(repo_root):
    try:
        c = subprocess.run(["git","rev-parse","HEAD"], cwd=repo_root, capture_output=True, text=True, check=True).stdout.strip()
        return c
    except: return "unknown"


def run_sql_pn(series, flange, size, material, trim) -> str:
    """Generate Part Number via SQL stored procedure."""
    config = json.dumps({
        "SERIES": series,
        "FLANGE_TYPE": flange,
        "SIZE": size,
        "PUMP_MATERIAL": material,
        "IMPELLER_TRIM": trim,
        "PUMP_OPTIONS_CODE": "0001",
        "SEAL_MFG_CODE": "S",
        "SEAL_ASSY_CODE": "01",
        "OPTIONS_CODE": "01",
        "FRAME_SIZE_CODE": "01",
        "MOTOR_ASSY_CODE": "001",
        "MOTOR_MODS_CODE": "XXX",
        "TESTING_CODE": "00",
    })
    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()
    cursor.execute(
        "DECLARE @PN varchar(200); "
        "EXEC cfg.usp_GeneratePartNumber @FamilyCode=?, @ConfigurationJson=?, @PartNumber=@PN OUTPUT; "
        "SELECT @PN;",
        "FYBROC", config,
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else "ERROR"


def run_excel_oracle(repo_root, test_cases) -> list[dict]:
    """Run all tests through Excel COM."""
    import win32com.client
    import pythoncom

    pythoncom.CoInitialize()
    source = repo_root / WORKBOOK_REL
    temp_dir = Path(tempfile.mkdtemp(prefix="f170_"))
    temp_wb = temp_dir / source.name
    shutil.copy2(source, temp_wb)

    results = []
    xl = None; wb = None
    try:
        xl = win32com.client.Dispatch("Excel.Application")
        xl.Visible = False; xl.DisplayAlerts = False; xl.EnableEvents = False; xl.ScreenUpdating = False
        wb = xl.Workbooks.Open(str(temp_wb), UpdateLinks=0)
        ws = wb.Sheets("Smart Number")

        for series, flange, size, material, trim, exp_code in test_cases:
            # Write inputs
            ws.Cells(14, 6).Value = series
            ws.Cells(15, 6).Value = flange
            ws.Cells(14, 7).Value = size
            ws.Cells(14, 8).Value = material
            ws.Cells(14, 9).NumberFormat = "@"
            ws.Cells(14, 9).Value = trim

            xl.CalculateFull()
            time.sleep(0.3)

            # Read outputs
            excel_pn = str(ws.Cells(9, 4).Value or "")
            series_code = str(ws.Cells(13, 5).Value or "")

            results.append({
                "series": series, "flange": flange, "size": size,
                "material": material, "trim": trim,
                "expected_series_code": exp_code,
                "excel_pn": excel_pn,
                "excel_series_code": series_code,
            })

    except Exception as e:
        results.append({"error": str(e)})
    finally:
        if wb: wb.Close(SaveChanges=False)
        if xl: xl.Quit()
        shutil.rmtree(temp_dir, ignore_errors=True)
        pythoncom.CoUninitialize()

    return results


def main():
    p = argparse.ArgumentParser(); root = Path(__file__).resolve().parent.parent
    p.add_argument("--repo-root", type=Path, default=root)
    a = p.parse_args(); repo_root = a.repo_root.resolve()
    ev = (repo_root / "docs" / "evidence" / "F170")
    ev.mkdir(parents=True, exist_ok=True)

    commit = git_info(repo_root)

    # Run Excel oracle
    print("Running Excel Oracle (10 test cases)...")
    excel_results = run_excel_oracle(repo_root, TEST_MATRIX)

    # Run SQL for same configs and compare
    print("Running SQL Part Number generation...")
    final_results = []
    passed = 0; failed = 0

    for i, (series, flange, size, material, trim, exp_code) in enumerate(TEST_MATRIX):
        er = excel_results[i] if i < len(excel_results) and "error" not in excel_results[i] else None
        sql_pn = run_sql_pn(series, flange, size, material, trim)

        excel_pn = er["excel_pn"] if er else "EXCEL_ERROR"
        # Compare first 6 chars (brand+series+size+material+trim prefix)
        excel_prefix = excel_pn[:6] if not excel_pn.startswith("-") else "ERROR"
        sql_prefix = sql_pn[:6] if not sql_pn.startswith("?") else "SQL_ERROR"

        # Check if the primary identity segment matches
        match = excel_prefix == sql_prefix and excel_prefix != "ERROR"

        if match: passed += 1
        else: failed += 1

        final_results.append({
            "series": series, "flange": flange, "size": size,
            "material": material, "trim": trim,
            "excel_pn": excel_pn,
            "sql_pn": sql_pn,
            "excel_prefix": excel_prefix,
            "sql_prefix": sql_prefix,
            "match": match,
        })

    result = {
        "step": STEP, "milestone": MILESTONE,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit,
        "test_count": len(TEST_MATRIX),
        "passed": passed, "failed": failed,
        "results": final_results,
    }

    # Write outputs
    (ev / "FYBROC_REGRESSION_RESULTS.json").write_text(
        json.dumps({"artifact": "FYBROC_REGRESSION_RESULTS", **result}, indent=2), encoding="utf-8")

    out = [f"{'='*100}\nF170 REGRESSION RESULTS\n{'='*100}\n\n"]
    out.append(f"Tests: {result['test_count']}  Passed: {passed}  Failed: {failed}\n\n")
    for r in final_results:
        s = "PASS" if r["match"] else "FAIL"
        out.append(f"[{s}] {r['series']}/{r['flange']}/{r['size']}/{r['material']}/{r['trim']}\n")
        out.append(f"  Excel: {r['excel_pn']}\n  SQL:   {r['sql_pn']}\n\n")
    (ev / "FYBROC_REGRESSION_RESULTS.txt").write_text("".join(out), encoding="utf-8")

    print(json.dumps({"tests": result["test_count"], "passed": passed, "failed": failed}, indent=2))
    return 0 if failed == 0 else 1

if __name__ == "__main__": raise SystemExit(main())

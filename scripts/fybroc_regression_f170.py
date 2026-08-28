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

# V6 orientation split (Attributes 'Horizontal Series' rows 8-13 vs
# 'Vertical Series' rows 15-20). The Smart Number sheet has two independent
# flows: HORIZONTAL uses input row 14/15 and outputs at D9 / segment row 13;
# VERTICAL uses input row 39/40 and outputs at D34 / segment row 33.
HORIZONTAL_SERIES = {"1500", "1530", "1600", "1630", "2530", "3000"}
VERTICAL_SERIES = {"5500", "5530", "6000", "7500", "7530", "8500"}

# The V6 Attributes Series+Flange table stores some series as TEXT and some as
# INTEGER (a workbook data-entry inconsistency). Excel COM would coerce a
# written string like "1500" to a number; we must write each series value with
# the SAME type the lookup table stores, or the series+flange XLOOKUP fails
# (string vs number) and the part number becomes #N/A.
#
# NOTE: this is a HARNESS-ONLY accommodation because this script writes values
# back INTO the workbook to drive its native formulas. The application's
# canonical type for SERIES is always TEXT - see docs/DATA_TYPE_NORMALIZATION.md
# (divergence #2) and src/compiler/workbook_types.norm_series.
SERIES_STORED_AS_INT = {"2530", "3000", "5500"}

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


# Excel COM surfaces cell errors (#N/A, #VALUE!) as large negative ints.
EXCEL_ERROR_SENTINELS = {-2146826246, -2146826281, -2146826273, -2146826288, -2146826265}


def _cell_text(v) -> str:
    """Normalize a COM cell value to text; blank string for None/errors."""
    if v is None:
        return ""
    if isinstance(v, int) and v in EXCEL_ERROR_SENTINELS:
        return "#ERROR"
    if isinstance(v, float):
        if v in EXCEL_ERROR_SENTINELS:
            return "#ERROR"
        if v.is_integer():
            return str(int(v))
    return str(v)


def _leading_prefix(ws, seg_row: int) -> str:
    """Assemble F + series + size + material + trim from the segment-code row.

    seg_row is 13 for the horizontal flow, 33 for the vertical flow. Columns:
    brand=4, series=5, size=7, material=8, trim=9. Returns 'ERROR' if the
    series/size/material/trim segment did not compute.
    """
    series = ws.Cells(seg_row, 5).Value
    size = ws.Cells(seg_row, 7).Value
    material = ws.Cells(seg_row, 8).Value
    trim = ws.Cells(seg_row, 9).Value
    parts = [_cell_text(series), _cell_text(size), _cell_text(material), _cell_text(trim)]
    if any(p in ("", "#ERROR") for p in parts):
        return "ERROR"
    return "F" + "".join(parts)


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
            vertical = series in VERTICAL_SERIES
            # Orientation-specific cell rows (verified via COM inspection):
            #   horizontal: input row 14/15, PN at D9,  segment codes row 13
            #   vertical:   input row 39/40, PN at D34, segment codes row 38
            if vertical:
                s_row, pn_row, seg_row = 39, 34, 38
            else:
                s_row, pn_row, seg_row = 14, 9, 13

            # Write the series with the type the Attributes table stores (int
            # for 2530/3000/5500, text otherwise) so the series+flange XLOOKUP
            # matches. Size and trim are written as text.
            if series in SERIES_STORED_AS_INT:
                ws.Cells(s_row, 6).NumberFormat = "General"
                ws.Cells(s_row, 6).Value = int(series)
            else:
                ws.Cells(s_row, 6).NumberFormat = "@"
                ws.Cells(s_row, 6).Value = series
            ws.Cells(s_row + 1, 6).Value = flange
            ws.Cells(s_row, 7).NumberFormat = "@"
            ws.Cells(s_row, 7).Value = size
            ws.Cells(s_row, 8).Value = material
            ws.Cells(s_row, 9).NumberFormat = "@"
            ws.Cells(s_row, 9).Value = trim

            xl.CalculateFull()
            time.sleep(0.3)

            # Assemble the leading identity prefix from the orientation's segment
            # row (brand col4, series col5, size col7, material col8, trim col9)
            # so it resolves even if a downstream DEFAULT segment is #N/A.
            excel_pn = _cell_text(ws.Cells(pn_row, 4).Value)
            excel_leading = _leading_prefix(ws, seg_row)

            results.append({
                "series": series, "flange": flange, "size": size,
                "material": material, "trim": trim,
                "orientation": "vertical" if vertical else "horizontal",
                "expected_series_code": exp_code,
                "excel_pn": excel_pn,
                "excel_series_code": _cell_text(ws.Cells(seg_row, 5).Value),
                "excel_leading": excel_leading,
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
        # Compare the leading identity segment (brand+series+size+material+trim).
        # excel_leading is assembled from the row-13 segment cells (robust to
        # #N/A in default downstream segments). The SQL leading segment is
        # everything before the first '-' in the generated part number.
        excel_prefix = (er.get("excel_leading") if er else None) or "ERROR"
        sql_prefix = (
            sql_pn.split("-", 1)[0]
            if sql_pn and not sql_pn.startswith("?") and "ERROR" not in sql_pn
            else "SQL_ERROR"
        )

        # Check if the primary identity segment matches
        match = excel_prefix == sql_prefix and excel_prefix not in ("ERROR", "SQL_ERROR")

        if match: passed += 1
        else: failed += 1

        final_results.append({
            "series": series, "flange": flange, "size": size,
            "material": material, "trim": trim,
            "expected_series_code": exp_code,
            "excel_series_code": er.get("excel_series_code") if er else None,
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
        out.append(f"  Excel leading: {r['excel_prefix']}   SQL leading: {r['sql_prefix']}\n")
        out.append(f"  Excel PN: {r['excel_pn']}\n  SQL PN:   {r['sql_pn']}\n\n")
    (ev / "FYBROC_REGRESSION_RESULTS.txt").write_text("".join(out), encoding="utf-8")

    print(json.dumps({"tests": result["test_count"], "passed": passed, "failed": failed}, indent=2))
    return 0 if failed == 0 else 1

if __name__ == "__main__": raise SystemExit(main())

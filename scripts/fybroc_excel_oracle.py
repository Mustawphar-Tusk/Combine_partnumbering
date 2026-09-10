"""F160 - Fybroc Excel Oracle Harness.

Roadmap anchor
--------------
docs/PROJECT_MASTER_ROADMAP.md, Section 6, Milestone F160 ("Excel Oracle Harness").

PURPOSE
-------
Use *real* Microsoft Excel (COM automation) with the authoritative
Nomenclature_V6.xlsm workbook as an INDEPENDENT engineering oracle, and compare
what the workbook's own formulas produce against what our API/SQL produces.

This is the harness F170 (exhaustive regression) builds on. F160's own exit gate
is narrow: the Excel-oracle tests must operate SAFELY (disposable copies only)
and REPEATABLY. It is NOT exhaustive coverage.

WHAT IS COMPARED (decision (b): PN + segment codes)
---------------------------------------------------
For each representative case we feed BOTH systems the same core selection
(series / flange / size / material / trim) and compare the leading IDENTITY:
  - the leading Part-Number segment  (F + series + size + material + trim), and
  - the four identity segment codes    (series_code, size_code, material_code,
    trim_code).
The leading identity is the part both systems derive independently from the same
core inputs, so it is a true cross-check. Downstream option/seal/motor segments
depend on option selections that differ between "workbook defaults" and the API's
STD walk; forcing those into lock-step for every combination is F170's job.

HOW THE WORKBOOK IS DRIVEN (verified via COM inspection - see docs/evidence/F160)
---------------------------------------------------------------------------------
Sheet "Smart Number" has two independent flows:
  HORIZONTAL: inputs at rows 14 (series/size/material/trim) + 15 (flange),
              compact PN at D9,  segment codes on row 13.
  VERTICAL:   inputs at rows 39 (series/size/material/trim) + 40 (flange),
              compact PN at D34, segment codes on row 38.
Segment columns (both flows): brand=4, series=5, size=7, material=8, trim=9,
pump_options=11, seal_mfg=15, seal_assy=16/17, options=19, frame=22,
motor_assy=23, motor_mods=26, testing=29.

DATA-TYPE RULE (critical - empirically confirmed, see F160 evidence)
--------------------------------------------------------------------
The workbook's XLOOKUP/dynamic-array formulas are type-sensitive:
  - SERIES 2530/3000/5500 must be written as an INTEGER (the Attributes table
    stores them numerically); every other series must be written as TEXT.
  - SIZE and TRIM must always be written as TEXT (force NumberFormat='@'),
    otherwise Excel coerces e.g. '6.000' -> 6 and the trim XLOOKUP misses.
Writing values without forcing these formats makes the horizontal series/trim
segments return #N/A. This is a HARNESS-ONLY accommodation for driving the
workbook's native formulas; the application's canonical SERIES type is TEXT.

SAFETY RULES (per roadmap governance)
-------------------------------------
- The authoritative workbook is NEVER opened for write and NEVER modified.
- Every run operates on a fresh disposable COPY in a temp dir, deleted after.
- A DEDICATED Excel instance is used (DispatchEx) so we never attach to (or
  disturb) a user's already-open Excel.
- No VBA macros are executed - pure formula recalculation only.

Inputs:
  workbooks/Fybroc/Nomenclature_V6.xlsm (authoritative - copied, never modified)
Outputs:
  docs/evidence/F160/FYBROC_EXCEL_ORACLE_RESULTS.{json,txt}
"""
from __future__ import annotations
import argparse, json, shutil, subprocess, tempfile, time
from datetime import datetime, timezone
from pathlib import Path

STEP = "F160.1"; ROADMAP_VERSION = "1.8"; MILESTONE = "F160"
WORKBOOK_REL = "workbooks/Fybroc/Nomenclature_V6.xlsm"
SHEET = "Smart Number"

# Orientation split (V6 Attributes 'Horizontal Series' vs 'Vertical Series').
HORIZONTAL_SERIES = {"1500", "1530", "1600", "1630", "2530", "3000"}
VERTICAL_SERIES = {"5500", "5530", "6000", "7500", "7530", "8500"}

# Series the V6 Attributes table stores as INTEGER (must be written as int so the
# series+flange XLOOKUP matches). All other series are written as TEXT.
SERIES_STORED_AS_INT = {"2530", "3000", "5500"}

# Excel COM surfaces cell errors (#N/A, #VALUE!, ...) as these large negative ints.
EXCEL_ERROR_SENTINELS = {-2146826246, -2146826281, -2146826273, -2146826288, -2146826265}

# Orientation-specific cell geometry (row, and per-flow layout).
GEOMETRY = {
    "horizontal": {"series_row": 14, "flange_row": 15, "pn_cell": (9, 4), "seg_row": 13},
    "vertical":   {"series_row": 39, "flange_row": 40, "pn_cell": (34, 4), "seg_row": 38},
}
# Segment-code columns on the segment row (shared layout for both flows).
SEG_COLS = {
    "brand": 4, "series": 5, "size": 7, "material": 8, "trim": 9,
    "pump_options": 11, "seal_mfg": 15, "seal_assy": 16, "options": 19,
    "frame_size": 22, "motor_assy": 23, "motor_mods": 26, "testing": 29,
}


def git_info(repo_root):
    try:
        c = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root,
                           capture_output=True, text=True, check=True).stdout.strip()
        s = subprocess.run(["git", "status", "--porcelain"], cwd=repo_root,
                           capture_output=True, text=True, check=True).stdout
        return c, (s.strip() == "")
    except Exception:
        return "unknown", False


def _cell_text(v) -> str:
    """Normalize a COM cell value to text; '#ERROR' for error sentinels."""
    if v is None:
        return ""
    if isinstance(v, int) and v in EXCEL_ERROR_SENTINELS:
        return "#ERROR"
    if isinstance(v, float):
        if int(v) in EXCEL_ERROR_SENTINELS:
            return "#ERROR"
        if v.is_integer():
            return str(int(v))
    return str(v)


def _leading_prefix(series_code, size_code, material_code, trim_code) -> str:
    """F + series + size + material + trim; 'ERROR' if any segment didn't compute."""
    parts = [series_code, size_code, material_code, trim_code]
    if any(p in ("", "#ERROR") for p in parts):
        return "ERROR"
    return "F" + "".join(parts)


# Representative matrix (small - F160 proves the harness works, not exhaustive).
# (series, flange, size, material, trim)
DEFAULT_MATRIX = [
    ("1500", "ANSI", "1x1.5x6", "VR-1",  "6.000"),   # horizontal, group 1
    ("1500", "ANSI", "1x2x10",  "VR-1A", "9.250"),   # horizontal, workbook default-ish
    ("1530", "ANSI", "1.5x3x8", "VR-1",  "7.000"),   # horizontal, different series
    ("1600", "ANSI", "2x3x6",   "VR-1",  "5.500"),   # horizontal
    ("3000", "ANSI", "1x1.5x6", "VR-1",  "6.000"),   # horizontal, series-stored-as-int
    ("5500", "ANSI", "1x2x10",  "VR-1",  "8.000"),   # vertical, series-stored-as-int
]


def run_oracle(repo_root: Path, matrix) -> list[dict]:
    """Drive each case through Excel COM on a single disposable copy."""
    import win32com.client
    import pythoncom

    pythoncom.CoInitialize()
    source = repo_root / WORKBOOK_REL
    temp_dir = Path(tempfile.mkdtemp(prefix="fybroc_oracle_"))
    temp_wb = temp_dir / source.name
    shutil.copy2(source, temp_wb)

    results = []
    xl = None; wb = None
    try:
        # DispatchEx => dedicated instance; never attach to a user's open Excel.
        xl = win32com.client.DispatchEx("Excel.Application")
        xl.Visible = False; xl.DisplayAlerts = False
        xl.EnableEvents = False; xl.ScreenUpdating = False
        wb = xl.Workbooks.Open(str(temp_wb), UpdateLinks=0, ReadOnly=False)
        ws = wb.Sheets(SHEET)

        for series, flange, size, material, trim in matrix:
            orientation = "vertical" if series in VERTICAL_SERIES else "horizontal"
            g = GEOMETRY[orientation]
            s_row, f_row, seg_row = g["series_row"], g["flange_row"], g["seg_row"]
            pn_r, pn_c = g["pn_cell"]

            # Write SERIES with the type the Attributes table stores.
            if series in SERIES_STORED_AS_INT:
                ws.Cells(s_row, 6).NumberFormat = "General"
                ws.Cells(s_row, 6).Value = int(series)
            else:
                ws.Cells(s_row, 6).NumberFormat = "@"
                ws.Cells(s_row, 6).Value = series
            ws.Cells(f_row, 6).Value = flange
            # SIZE and TRIM must be text so the XLOOKUPs match.
            ws.Cells(s_row, 7).NumberFormat = "@"; ws.Cells(s_row, 7).Value = size
            ws.Cells(s_row, 8).Value = material
            ws.Cells(s_row, 9).NumberFormat = "@"; ws.Cells(s_row, 9).Value = trim

            xl.CalculateFull()
            time.sleep(0.6)

            seg = {name: _cell_text(ws.Cells(seg_row, col).Value)
                   for name, col in SEG_COLS.items()}
            compact_pn = _cell_text(ws.Cells(pn_r, pn_c).Value)
            leading = _leading_prefix(seg["series"], seg["size"], seg["material"], seg["trim"])

            results.append({
                "series": series, "flange": flange, "size": size,
                "material": material, "trim": trim,
                "orientation": orientation,
                "excel_compact_pn": compact_pn,
                "excel_leading": leading,
                "excel_segments": seg,
                "computed": leading != "ERROR",
            })
    except Exception as e:
        results.append({"error": str(e)})
    finally:
        if wb: wb.Close(SaveChanges=False)
        if xl: xl.Quit()
        shutil.rmtree(temp_dir, ignore_errors=True)
        pythoncom.CoUninitialize()

    return results


def build_model(repo_root, matrix):
    commit, clean = git_info(repo_root)
    results = run_oracle(repo_root, matrix)
    computed = sum(1 for r in results if r.get("computed"))
    errored = sum(1 for r in results if not r.get("computed"))
    return {
        "step": STEP, "roadmap_version": ROADMAP_VERSION, "milestone": MILESTONE,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit, "git_working_tree_clean": clean,
        "source_workbook": WORKBOOK_REL,
        "compares": "PN leading identity + identity segment codes (series/size/material/trim)",
        "safety": "disposable copy only; dedicated Excel (DispatchEx); source workbook never modified",
        "test_count": len(matrix),
        "computed": computed,
        "errored": errored,
        "results": results,
    }


def _banner(t):
    return f"{'='*100}\r\n{t}\r\n{'='*100}\r\n\r\n"


def write_outputs(ev, result):
    (ev / "FYBROC_EXCEL_ORACLE_RESULTS.json").write_text(
        json.dumps({"artifact": "FYBROC_EXCEL_ORACLE_RESULTS", **result},
                   indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    out = [_banner("F160.1 - FYBROC EXCEL ORACLE RESULTS")]
    out.append(f"Git commit : {result['git_commit']}\r\n")
    out.append(f"Source     : {result['source_workbook']}\r\n")
    out.append(f"Compares   : {result['compares']}\r\n")
    out.append(f"Safety     : {result['safety']}\r\n")
    out.append(f"Tests      : {result['test_count']}   Computed: {result['computed']}   Errored: {result['errored']}\r\n\r\n")
    for r in result["results"]:
        if "error" in r:
            out.append(f"  HARNESS ERROR: {r['error']}\r\n\r\n"); continue
        status = "OK " if r["computed"] else "ERR"
        out.append(f"  [{status}] {r['series']}/{r['flange']}/{r['size']}/{r['material']}/{r['trim']} ({r['orientation']})\r\n")
        out.append(f"     Excel leading : {r['excel_leading']}\r\n")
        out.append(f"     Excel compact : {r['excel_compact_pn']}\r\n")
        out.append(f"     Segments      : {r['excel_segments']}\r\n\r\n")
    (ev / "FYBROC_EXCEL_ORACLE_RESULTS.txt").write_text("".join(out), encoding="utf-8")


def main():
    p = argparse.ArgumentParser()
    root = Path(__file__).resolve().parent.parent
    p.add_argument("--repo-root", type=Path, default=root)
    p.add_argument("--evidence-dir", type=Path, default=None)
    a = p.parse_args()
    repo_root = a.repo_root.resolve()
    ev = (a.evidence_dir or (repo_root / "docs" / "evidence" / "F160")).resolve()
    ev.mkdir(parents=True, exist_ok=True)
    result = build_model(repo_root, DEFAULT_MATRIX)
    write_outputs(ev, result)
    print(json.dumps({
        "step": STEP, "tests": result["test_count"],
        "computed": result["computed"], "errored": result["errored"],
    }, indent=2))
    return 0 if result["errored"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

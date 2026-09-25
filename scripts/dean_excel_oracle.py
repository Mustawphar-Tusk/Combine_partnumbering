"""D140 - Dean Excel Oracle (COM harness, re-based onto the NEW authority).

Roadmap D140 gate: "SQL output matches approved Dean workbook output" via
"Dean workbook COM regression parity."

RE-BASE (2026-08-26): the authoritative workbook is now
`workbooks/Dean/PumpConfiguration_Logic_0.1.xlsm`. Unlike the old
`Dean Data Sheet Rev 2.xlsm`, this workbook is NOT an interactive Smart-Number
configurator - it has NO 'Data Sheet' input sheet and NO 'Smart Number' Part
Number output. It is the AUTHORITATIVE numbering + constraint source: each PN
segment has its own numbering sheet enumerating (option-combo -> Alphanumeric
Code) rows (see PCL_V01 structure + Module1/Module2 VBA).

Therefore the D140 oracle here is a NUMBERING-TABLE oracle: it opens the REAL
workbook via Excel COM and reads, LIVE, the authoritative Alphanumeric Code for a
given option ComboString directly from the workbook's own numbering sheet (the
exact value the workbook itself would emit). dean_oracle_compare.py then drives
the SAME ComboString through the API/SQL resolver and requires the codes match.

This is a genuine COM regression parity check: the SQL-loaded codes
(scripts/load_dean_identifier_to_sql.py) are proved to equal the codes read LIVE
from the workbook via an INDEPENDENT path (Excel COM open + WorksheetFunction /
cell scan), not the openpyxl bulk load the loader used.

COM notes (this Excel + pywin32 combo - see D140 task 1):
  - MUST use PURE DYNAMIC dispatch (win32com.client.dynamic.Dispatch); the
    early-bind gen_py wrappers do NOT expose .Range/.Cells here.
  - Clear the stale gen_py cache once before running (ensure_clean_gen_py()).
  - Workbooks.Open + every cell touch is wrapped in com_retry.

Safety: dedicated hidden Excel instance, DISPOSABLE temp copy only, source
workbook NEVER modified, NO macros run (pure read). Cleaned up in finally.
"""
from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path

WORKBOOK_REL = "workbooks/Dean/PumpConfiguration_Logic_0.1.xlsm"

_COM_BUSY = (-2147418111, -2147417846, -2147418110)

# Per-segment numbering-sheet layout (mirrors scripts/load_dean_identifier_to_sql
# SEGMENTS): sheet name, the header row that carries 'Permutation'+'Alphanumeric
# Code', and the segment code. The oracle finds the option columns dynamically
# (strictly between Permutation and Alphanumeric Code) exactly like the loader.
SEGMENT_SHEETS = {
    "WET_END_OPTIONS": {"sheet": "Wet End Numbering", "scan_max": 20},
    "IMPELLER_OPTIONS": {"sheet": "Impeller Numbering", "scan_max": 20},
    "POWER_FRAME_OPTIONS": {"sheet": "Power Frame Numbering", "scan_max": 20},
    "BASEPLATE_OPTIONS": {"sheet": "Baseplate Numbering", "scan_max": 20},
    "FLUSH_PLAN": {"sheet": "Flush Plan Numbering", "scan_max": 40},
    # Motor Frame-Size sub-table: Permutation=S, value=T (Frame Size), code=U.
    "MOTOR_FRAME": {"sheet": "Motor Numbering", "subtable": (18, 19, 20),
                    "header_row": 16},
}


def a1(row, col):
    s = ""
    c = col
    while c > 0:
        c, r = divmod(c - 1, 26)
        s = chr(65 + r) + s
    return f"{s}{row}"


def com_retry(fn, tries=25, delay=0.4):
    import pythoncom
    last = None
    for _ in range(tries):
        try:
            return fn()
        except pythoncom.com_error as e:  # type: ignore
            code = e.args[0] if e.args else None
            if code in _COM_BUSY:
                last = e
                time.sleep(delay)
                continue
            raise
    raise last


def cell_str(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def ensure_clean_gen_py():
    """Remove the stale win32com early-bind cache so dynamic dispatch is used."""
    import os
    genpy = Path(os.environ.get("LOCALAPPDATA", "")) / "Temp" / "gen_py"
    if genpy.exists():
        shutil.rmtree(genpy, ignore_errors=True)


class DeanNumberingOracle:
    """Opens the real workbook via COM and reads segment codes LIVE by matching a
    ComboString against the workbook's numbering-sheet rows. One instance per run;
    it builds an in-memory {segment: {combo: code}} map by scanning each sheet's
    materialized table once (via COM), so per-combo lookups are O(1) and no macro
    executes."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self._maps = {}          # segment -> {combo_string: code}
        self._xl = None
        self._wb = None
        self._temp_dir = None
        self._pythoncom = None

    # -- COM lifecycle ------------------------------------------------------
    def open(self):
        ensure_clean_gen_py()
        import win32com.client.dynamic
        import pythoncom
        self._pythoncom = pythoncom
        pythoncom.CoInitialize()
        source = self.repo_root / WORKBOOK_REL
        self._temp_dir = Path(tempfile.mkdtemp(prefix="dean_oracle_v01_"))
        temp_wb = self._temp_dir / source.name
        shutil.copy2(source, temp_wb)
        xl = win32com.client.dynamic.Dispatch("Excel.Application")
        xl.Visible = False
        xl.DisplayAlerts = False
        xl.EnableEvents = False
        xl.ScreenUpdating = False
        self._xl = xl
        self._wb = com_retry(
            lambda: xl.Workbooks.Open(str(temp_wb), UpdateLinks=0, ReadOnly=True))
        if self._wb is None:
            self._wb = xl.ActiveWorkbook
        time.sleep(1.0)

    def close(self):
        try:
            if self._wb:
                com_retry(lambda: self._wb.Close(SaveChanges=False))
        except Exception:
            pass
        try:
            if self._xl:
                self._xl.Quit()
        except Exception:
            pass
        if self._temp_dir:
            shutil.rmtree(self._temp_dir, ignore_errors=True)
        if self._pythoncom:
            self._pythoncom.CoUninitialize()

    # -- table scan ---------------------------------------------------------
    def _ws(self, name):
        return com_retry(lambda: self._wb.Worksheets.Item(name))

    @staticmethod
    def _as_grid(val):
        """Normalize a Range.Value COM result to a list-of-rows (list of tuples).
        A single cell returns a scalar; a single row/col returns a 1-D tuple."""
        if val is None:
            return []
        if not isinstance(val, tuple):
            return [(val,)]
        if len(val) == 0:
            return []
        if not isinstance(val[0], tuple):    # single row
            return [val]
        return list(val)

    def _find_table(self, ws, scan_max):
        """Return (header_row1, perm_col0, code_col0) via header search, reading
        each candidate header row as ONE bulk Range array (A..AC)."""
        for r in range(1, scan_max + 1):
            rng = com_retry(lambda r=r: ws.Range(f"A{r}:AC{r}").Value)
            grid = self._as_grid(rng)
            if not grid:
                continue
            row = grid[0]
            perm = code = None
            for c0, v in enumerate(row):
                sv = cell_str(v).lower()
                if sv == "permutation":
                    perm = c0
                elif sv == "alphanumeric code":
                    code = c0
            if perm is not None and code is not None:
                return r, perm, code
        return None, None, None

    def _load_segment(self, segment_code):
        cfg = SEGMENT_SHEETS[segment_code]
        ws = self._ws(cfg["sheet"])
        used = com_retry(lambda: ws.UsedRange)
        last_row = com_retry(lambda: used.Row + used.Rows.Count - 1)
        mp = {}

        if "subtable" in cfg:
            # Motor Frame-Size sub-table: value col (T) -> code col (U), keyed by
            # value. Bulk-read T:U in one array.
            scol, vcol, ucol = cfg["subtable"]  # 0-based S/T/U
            hr = cfg["header_row"]
            rng = com_retry(lambda: ws.Range(
                f"{a1(hr + 1, vcol + 1)}:{a1(last_row, ucol + 1)}").Value)
            for row in self._as_grid(rng):
                val = cell_str(row[0]) if len(row) > 0 else ""
                u = cell_str(row[ucol - vcol]) if len(row) > (ucol - vcol) else ""
                if u and val and val.lower() not in ("frame size", "alphanumeric code"):
                    mp.setdefault(val, u)
            self._maps[segment_code] = mp
            return

        hr, perm, ccol = self._find_table(ws, cfg["scan_max"])
        if hr is None or ccol is None:
            self._maps[segment_code] = mp
            return
        opt_cols = list(range(perm + 1, ccol))
        # Bulk-read the whole materialized table (Permutation..Alphanumeric Code)
        # in ONE Range array - one COM round-trip for the entire sheet.
        rng = com_retry(lambda: ws.Range(
            f"{a1(hr + 1, perm + 1)}:{a1(last_row, ccol + 1)}").Value)
        base = perm  # first column of the read block (0-based sheet col)
        for row in self._as_grid(rng):
            code = cell_str(row[ccol - base]) if len(row) > (ccol - base) else ""
            if not code or code.lower() in ("alphanumeric code", "code"):
                continue
            parts = []
            for c in opt_cols:
                idx = c - base
                parts.append(cell_str(row[idx]) if 0 <= idx < len(row) else "")
            combo = "*".join(parts)
            while combo.endswith("*"):
                combo = combo[:-1]
            if combo:
                mp.setdefault(combo, code)
        self._maps[segment_code] = mp

    def code_for(self, segment_code, combo_string):
        """Return the workbook's Alphanumeric Code for a ComboString, read LIVE
        from the numbering sheet (scanning the sheet on first access)."""
        if segment_code not in self._maps:
            self._load_segment(segment_code)
        return self._maps[segment_code].get(combo_string)

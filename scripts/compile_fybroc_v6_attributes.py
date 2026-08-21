"""F110.3 - Fybroc Nomenclature V6 Attributes Compiler.

Roadmap anchor
--------------
docs/PROJECT_MASTER_ROADMAP.md, Section 6, Milestone F110
("V5 to V6 Nomenclature Reconciliation") and F120 identifier mapping.

The Attributes sheet in Nomenclature_V6.xlsm is the authoritative
lookup table for all Fybroc part-number segment codes. It contains
seven distinct mapping tables on one sheet:

  1. Brand           col 3-4    FYBR -> F
  2. Series+Flange   col 6-8    Series x FlangeTtype -> single letter code
                                (e.g. 1500+ANSI=A, 1530+ANSI=B, 1500+DIN=I)
  3. Size            col 10-11  Pump size string -> numeric/alpha code
                                (e.g. 1x1.5x6=1, 2x3x13=A, 8x10x15=M)
  4. Pump_Material   col 13-14  Material name -> code
                                (e.g. VR-1=1, EY-2=2, VR-1A=5)
  5. Impeller_Trim   col 16-17  Trim decimal value -> 2-char Base-26 code
                                (e.g. 16.000=MA, 14.125=KB, 4.000=AA)
  6. Motor Mods      col 19-20  Motor modification description -> code
                                (e.g. No Modification=X, Class H=9)
  7. Inch            col 23-24  Inch integer -> letter (4"=A, 5"=B...)
     Decimal         col 26-27  Decimal suffix -> letter (.000=A, .125=B...)

The Series+Flange table also lists which series are Horizontal vs
Vertical (cols 47-48, rows 8-18).

Motor HP/RPM/Frame lookup is in cols 32-37 (separate from Motor Mods).
Per-size valid trim ranges are in cols 41-42 (size -> min trim) used by
ConstraintTable4 cross-reference.

No workbook is opened in write mode. Nothing is written back.

Inputs:
  workbooks/Fybroc/Nomenclature_V6.xlsm  (read-only)

Outputs:
  docs/evidence/F110/FYBROC_V6_ATTRIBUTES.{json,txt}
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
except ImportError as exc:
    raise SystemExit(
        "openpyxl is required - run with the project's own .venv interpreter."
    ) from exc

STEP = "F110.3"
ROADMAP_VERSION = "1.0"
MILESTONE = "F110"
WORKBOOK_REL = "workbooks/Fybroc/Nomenclature_V6.xlsm"

# Sheet layout - all tables are on the Attributes sheet
SHEET = "Attributes"
HEADER_ROW = 7
DATA_START = 8
DATA_END = 42          # rows 8-42 contain the main lookup tables

# Column positions (1-indexed)
COL_BRAND       = 3;  COL_BRAND_CODE       = 4
COL_H_SERIES    = 6;  COL_FLANGE           = 7;  COL_SERIES_CODE = 8
COL_SIZE        = 10; COL_SIZE_CODE        = 11
COL_MATERIAL    = 13; COL_MATERIAL_CODE    = 14
COL_TRIM        = 16; COL_TRIM_CODE        = 17
COL_MOTOR_MOD   = 19; COL_MOTOR_MOD_CODE   = 20
COL_INCH        = 23; COL_INCH_CODE        = 24
COL_DECIMAL     = 26; COL_DECIMAL_CODE     = 27
COL_SERIES_LIST = 47; COL_ORIENTATION      = 48

# Impeller trim full table extends rows 8-104 (col 16-17)
TRIM_DATA_END = 104

# Per-size valid trim min/max table: cols 41-42 (size -> lower trim bound)
COL_SIZE_TRIM_SIZE = 41
COL_SIZE_TRIM_VAL  = 42
SIZE_TRIM_END = 523


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


def _str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _float_str(v: Any) -> str | None:
    """Normalize a trim value to a consistent decimal string."""
    if v is None:
        return None
    try:
        return f"{float(str(v).strip()):.3f}"
    except (ValueError, TypeError):
        return _str(v)


def compile_brand(ws) -> list[dict]:
    rows = []
    for r in range(DATA_START, DATA_END + 1):
        brand = _str(ws.cell(row=r, column=COL_BRAND).value)
        code  = _str(ws.cell(row=r, column=COL_BRAND_CODE).value)
        if brand and code:
            rows.append({"brand": brand, "code": code})
    return rows


def compile_series_flange(ws) -> list[dict]:
    """Series + Flange Type -> identifier code."""
    rows = []
    for r in range(DATA_START, DATA_END + 1):
        series = _str(ws.cell(row=r, column=COL_H_SERIES).value)
        flange = _str(ws.cell(row=r, column=COL_FLANGE).value)
        code   = _str(ws.cell(row=r, column=COL_SERIES_CODE).value)
        if series and flange and code:
            rows.append({"series": series, "flange_type": flange, "code": code})
    return rows


def compile_series_orientation(ws) -> list[dict]:
    """Series -> Horizontal or Vertical orientation label."""
    rows = []
    for r in range(DATA_START, DATA_END + 1):
        series      = _str(ws.cell(row=r, column=COL_SERIES_LIST).value)
        orientation = _str(ws.cell(row=r, column=COL_ORIENTATION).value)
        if series and orientation:
            rows.append({"series": series, "orientation": orientation})
    return rows


def compile_sizes(ws) -> list[dict]:
    rows = []
    for r in range(DATA_START, DATA_END + 1):
        size = _str(ws.cell(row=r, column=COL_SIZE).value)
        code = _str(ws.cell(row=r, column=COL_SIZE_CODE).value)
        if size and code:
            rows.append({"size": size, "code": code})
    return rows


def compile_pump_materials(ws) -> list[dict]:
    rows = []
    for r in range(DATA_START, DATA_END + 1):
        material = _str(ws.cell(row=r, column=COL_MATERIAL).value)
        code     = _str(ws.cell(row=r, column=COL_MATERIAL_CODE).value)
        if material and code:
            rows.append({"material": material, "code": code})
    return rows


def compile_impeller_trims(ws) -> list[dict]:
    """Full impeller trim decimal -> 2-char code table (rows 8-104)."""
    rows = []
    for r in range(DATA_START, TRIM_DATA_END + 1):
        trim = _float_str(ws.cell(row=r, column=COL_TRIM).value)
        code = _str(ws.cell(row=r, column=COL_TRIM_CODE).value)
        if trim and code:
            rows.append({"trim_decimal": trim, "code": code})
    return rows


def compile_motor_mods(ws) -> list[dict]:
    rows = []
    for r in range(DATA_START, DATA_END + 1):
        mod  = _str(ws.cell(row=r, column=COL_MOTOR_MOD).value)
        code = _str(ws.cell(row=r, column=COL_MOTOR_MOD_CODE).value)
        if mod and code:
            rows.append({"modification": mod, "code": code})
    return rows


def compile_inch_codes(ws) -> list[dict]:
    rows = []
    for r in range(DATA_START, DATA_END + 1):
        inch = _str(ws.cell(row=r, column=COL_INCH).value)
        code = _str(ws.cell(row=r, column=COL_INCH_CODE).value)
        if inch and code:
            rows.append({"inch": inch, "code": code})
    return rows


def compile_decimal_codes(ws) -> list[dict]:
    rows = []
    for r in range(DATA_START, DATA_END + 1):
        dec  = _str(ws.cell(row=r, column=COL_DECIMAL).value)
        code = _str(ws.cell(row=r, column=COL_DECIMAL_CODE).value)
        if dec and code:
            rows.append({"decimal": dec, "code": code})
    return rows


def compile_size_trim_ranges(ws) -> dict[str, list[str]]:
    """Per-size valid trim values from cols 41-42 (rows 8-523)."""
    size_trims: dict[str, list[str]] = {}
    for r in range(DATA_START, SIZE_TRIM_END + 1):
        size = _str(ws.cell(row=r, column=COL_SIZE_TRIM_SIZE).value)
        trim = _float_str(ws.cell(row=r, column=COL_SIZE_TRIM_VAL).value)
        if size and trim:
            size_trims.setdefault(size, []).append(trim)
    return size_trims


def build_model(repo_root: Path) -> dict[str, Any]:
    commit, clean = git_info(repo_root)

    wb = openpyxl.load_workbook(
        str(repo_root / WORKBOOK_REL), read_only=True, data_only=True
    )
    ws = wb[SHEET]

    brand             = compile_brand(ws)
    series_flange     = compile_series_flange(ws)
    series_orientation = compile_series_orientation(ws)
    sizes             = compile_sizes(ws)
    pump_materials    = compile_pump_materials(ws)
    impeller_trims    = compile_impeller_trims(ws)
    motor_mods        = compile_motor_mods(ws)
    inch_codes        = compile_inch_codes(ws)
    decimal_codes     = compile_decimal_codes(ws)
    size_trim_ranges  = compile_size_trim_ranges(ws)

    wb.close()

    return {
        "step": STEP,
        "roadmap_version": ROADMAP_VERSION,
        "milestone": MILESTONE,
        "source_workbook": WORKBOOK_REL,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit,
        "git_working_tree_clean": clean,
        "brand": brand,
        "series_flange_codes": series_flange,
        "series_orientation": series_orientation,
        "size_codes": sizes,
        "pump_material_codes": pump_materials,
        "impeller_trim_codes": impeller_trims,
        "motor_modification_codes": motor_mods,
        "inch_codes": inch_codes,
        "decimal_codes": decimal_codes,
        "size_valid_trims": {
            size: {"trim_count": len(trims), "trims": trims}
            for size, trims in sorted(size_trim_ranges.items())
        },
    }


def _banner(title: str) -> str:
    line = "=" * 120
    return f"{line}\r\n{title}\r\n{line}\r\n\r\n"


def write_outputs(evidence_dir: Path, result: dict[str, Any]) -> None:
    payload = {"artifact": "FYBROC_V6_ATTRIBUTES", **result}
    (evidence_dir / "FYBROC_V6_ATTRIBUTES.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    lines = [_banner("F110.3 - FYBROC V6 ATTRIBUTES (All identifier lookup tables from Nomenclature_V6 Attributes sheet)")]
    lines.append(
        f"Git commit  : {result['git_commit']}\r\n"
        f"Git clean   : {result['git_working_tree_clean']}\r\n\r\n"
        f"Brand entries          : {len(result['brand'])}\r\n"
        f"Series+Flange codes    : {len(result['series_flange_codes'])}\r\n"
        f"Series orientations    : {len(result['series_orientation'])}\r\n"
        f"Size codes             : {len(result['size_codes'])}\r\n"
        f"Pump material codes    : {len(result['pump_material_codes'])}\r\n"
        f"Impeller trim codes    : {len(result['impeller_trim_codes'])}\r\n"
        f"Motor modification codes: {len(result['motor_modification_codes'])}\r\n"
        f"Inch codes             : {len(result['inch_codes'])}\r\n"
        f"Decimal codes          : {len(result['decimal_codes'])}\r\n"
        f"Sizes with trim ranges : {len(result['size_valid_trims'])}\r\n\r\n"
    )

    lines.append(_banner("BRAND"))
    for r in result["brand"]:
        lines.append(f"  {r['brand']:<20} -> {r['code']}\r\n")
    lines.append("\r\n")

    lines.append(_banner("SERIES + FLANGE TYPE -> CODE"))
    for r in result["series_flange_codes"]:
        lines.append(f"  Series={r['series']:<8} Flange={r['flange_type']:<8} -> {r['code']}\r\n")
    lines.append("\r\n")

    lines.append(_banner("SERIES ORIENTATION"))
    for r in result["series_orientation"]:
        lines.append(f"  {r['series']:<8} -> {r['orientation']}\r\n")
    lines.append("\r\n")

    lines.append(_banner("SIZE CODES"))
    for r in result["size_codes"]:
        lines.append(f"  {r['size']:<15} -> {r['code']}\r\n")
    lines.append("\r\n")

    lines.append(_banner("PUMP MATERIAL CODES"))
    for r in result["pump_material_codes"]:
        lines.append(f"  {r['material']:<20} -> {r['code']}\r\n")
    lines.append("\r\n")

    lines.append(_banner("IMPELLER TRIM CODES (decimal -> 2-char code)"))
    for r in result["impeller_trim_codes"]:
        lines.append(f"  {r['trim_decimal']:<10} -> {r['code']}\r\n")
    lines.append("\r\n")

    lines.append(_banner("MOTOR MODIFICATION CODES"))
    for r in result["motor_modification_codes"]:
        lines.append(f"  {r['code']:<5} {r['modification']}\r\n")
    lines.append("\r\n")

    lines.append(_banner("INCH CODES"))
    for r in result["inch_codes"]:
        lines.append(f"  {r['inch']:<8} -> {r['code']}\r\n")
    lines.append("\r\n")

    lines.append(_banner("DECIMAL SUFFIX CODES"))
    for r in result["decimal_codes"]:
        lines.append(f"  {r['decimal']:<10} -> {r['code']}\r\n")
    lines.append("\r\n")

    lines.append(_banner("PER-SIZE VALID TRIM RANGES"))
    for size, info in result["size_valid_trims"].items():
        trim_range = f"{info['trims'][-1]} - {info['trims'][0]}" if info["trims"] else "none"
        lines.append(f"  {size:<15} {info['trim_count']:>3} trims  range: {trim_range}\r\n")

    (evidence_dir / "FYBROC_V6_ATTRIBUTES.txt").write_text(
        "".join(lines), encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="F110.3 Fybroc V6 Attributes compiler")
    default_root = Path(__file__).resolve().parent.parent
    parser.add_argument("--repo-root", type=Path, default=default_root)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    args = parser.parse_args()

    repo_root: Path = args.repo_root.resolve()
    evidence_dir: Path = (
        args.evidence_dir or (repo_root / "docs" / "evidence" / "F110")
    ).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)

    result = build_model(repo_root)
    write_outputs(evidence_dir, result)

    print(json.dumps({
        "step": STEP,
        "output_dir": str(evidence_dir),
        "brand_entries": len(result["brand"]),
        "series_flange_codes": len(result["series_flange_codes"]),
        "series_orientation": len(result["series_orientation"]),
        "size_codes": len(result["size_codes"]),
        "pump_material_codes": len(result["pump_material_codes"]),
        "impeller_trim_codes": len(result["impeller_trim_codes"]),
        "motor_modification_codes": len(result["motor_modification_codes"]),
        "inch_codes": len(result["inch_codes"]),
        "decimal_codes": len(result["decimal_codes"]),
        "sizes_with_trim_ranges": len(result["size_valid_trims"]),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

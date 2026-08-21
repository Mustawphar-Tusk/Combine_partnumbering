"""F110.4 - Fybroc Nomenclature V6 Smart Number Compiler.

Roadmap anchor
--------------
docs/PROJECT_MASTER_ROADMAP.md, Section 6, Milestone F110
("V5 to V6 Nomenclature Reconciliation") - identifier segment sequence,
identifier codes, combination rules, source fields, orientation behavior.

The Smart Number sheet in Nomenclature_V6.xlsm defines the full
part-number construction flow for both Fybroc orientations.

HORIZONTAL (rows 1-28, cols D-AD):
  Row 4  : Section title "Fybroc Horizontal Part Number"
  Row 5  : Example part number
  Row 8  : Human-readable description of selected configuration
  Row 9  : Generated part number (concatenation with "-" separator)
  Row 12 : Segment label headers
  Row 13 : Segment CODE values (the actual part number tokens)
  Row 14+: Human-readable selection values for each segment field

  Segment sequence (col -> segment name):
    D(4)  Brand
    E(5)  Series (encodes Series + Flange Type via Attributes lookup)
    G(7)  Size
    H(8)  Pump Material
    I(9)  Impeller Trim
    K(11) Pump Options
    O(15) Seal Manufacturer
    P(16) Complete Seal Assembly
    S(19) Options
    V(22) Frame Size
    W(23) Motor Assembly
    Z(26) Motor Modifications
    AC(29) Testing

  Part number format:
    <Brand><Series><Size><Material><Trim>-<PumpOptions>-<SealMfg><SealAssy>-<Options>-<FrameSize><MotorAssy>-<MotorMods>-<Testing>

VERTICAL (rows 33-56, cols D-AF):
  Row 33 : Section title "Fybroc Vertical Part Number"
  Row 34 : Generated part number (D34)
  Row 35 : Legacy part number format (F-series prefix + size code)
  Row 37 : Segment label headers
  Row 38 : Segment CODE values
  Row 39+: Human-readable selection values

  Segment sequence (col -> segment name):
    D(4)  Brand
    E(5)  Series
    G(7)  Size
    H(8)  Pump Material
    I(9)  Impeller Trim
    K(11) Pump Options (Vertical)
    O(15) Setting/Length
    Q(17) Vertical Options
    S(19) Options (Vertical)
    V(22) Frame Size
    W(23) Motor Assembly
    Z(26) Motor Modifications
    AC(29) Testing

  Part number format (vertical):
    <Brand><Series><Size><Material><Trim>-<PumpOptions>-<Setting/Length><VertOptions>-<Options>-<FrameSize><MotorAssy>-<MotorMods>-<Testing>

Source sheets referenced by Smart Number lookups:
  - Attributes            (Brand, Series+Flange, Size, Material, Trim, Motor Mod codes)
  - Pump Options - Horizontal
  - Pump Options - Vertical
  - Seal Assembly - Horizontal
  - Setting-Length-Vertical
  - Options - Horizontal
  - Options - Vertical
  - Motor Assy
  - Testing

No workbook is opened in write mode. Nothing is written back.

Inputs:
  workbooks/Fybroc/Nomenclature_V6.xlsm  (read-only)

Outputs:
  docs/evidence/F110/FYBROC_V6_SMART_NUMBER.{json,txt}
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

STEP = "F110.4"
ROADMAP_VERSION = "1.0"
MILESTONE = "F110"
WORKBOOK_REL = "workbooks/Fybroc/Nomenclature_V6.xlsm"
SHEET = "Smart Number"

# ---------------------------------------------------------------------------
# Horizontal layout constants
# ---------------------------------------------------------------------------
H_TITLE_ROW        = 4
H_EXAMPLE_PN_ROW   = 5
H_DESCRIPTION_ROW  = 8
H_PART_NUMBER_ROW  = 9
H_LABEL_ROW        = 12
H_CODE_ROW         = 13
H_SELECTION_START  = 14
H_SELECTION_END    = 26

# Horizontal segment columns (col index, segment name, field rows)
# Each col is a segment; the rows below H_CODE_ROW show the field selections
# that feed into that segment via lookups.
HORIZONTAL_SEGMENTS = [
    (4,  "Brand",             [(14, "Brand")]),
    (5,  "Series",            [(14, "Series"), (15, "Flange Type")]),
    (7,  "Size",              [(14, "Size")]),
    (8,  "Pump Material",     [(14, "Pump Material")]),
    (9,  "Impeller Trim",     [(14, "Impeller Trim")]),
    (11, "Pump Options",      [
        (14, "Casing Drains"), (15, "Suction Discharge"), (16, "Shaft Material"),
        (17, "Impeller Sleeve"), (18, "Casing Hardware"), (19, "Pump Elastomers"),
        (20, "Bearing Option"), (21, "Frame Hardware"), (22, "Gland Hardware"),
        (23, "Flush"), (24, "Flush Material"), (25, "Cyclone Separator"),
        (26, "Dynamic Impeller"),
    ]),
    (15, "Seal Manufacturer", [(14, "Seal Manufacturer")]),
    (16, "Seal Assembly",     [
        (14, "Seal Option"), (15, "Seal Type"), (16, "Seal Materials"),
        (17, "Seal Elastomers"), (18, "Seal Guard"),
    ]),
    (19, "Options",           [
        (14, "Coupling Option"), (15, "Coupling Guard"), (16, "Baseplate Option"),
        (17, "Baseplate Hardware"), (18, "Customer Nameplate"), (19, "C-Face Adapter"),
    ]),
    (22, "Frame Size",        [(14, "Frame Size")]),
    (23, "Motor Assembly",    [
        (14, "Motor Option"), (15, "Motor Class"), (16, "Motor Orientation"),
        (17, "Horsepower"), (18, "RPM"), (19, "Voltage"), (20, "Hertz"),
        (21, "Frame"), (22, "Enclosure"), (23, "Efficiency"), (24, "Manufacturer"),
    ]),
    (26, "Motor Modifications", [
        (14, "Modification 1"), (15, "Modification 2"), (16, "Modification 3"),
    ]),
    (29, "Testing",           [
        (14, "Performance Testing"), (15, "Hydro Testing"),
        (16, "Vibration"), (17, "Sound Level"),
    ]),
]

# ---------------------------------------------------------------------------
# Vertical layout constants
# ---------------------------------------------------------------------------
V_TITLE_ROW        = 33
V_PART_NUMBER_ROW  = 34
V_LEGACY_PN_ROW    = 35
V_LABEL_ROW        = 37
V_CODE_ROW         = 38
V_SELECTION_START  = 39
V_SELECTION_END    = 49

VERTICAL_SEGMENTS = [
    (4,  "Brand",             [(39, "Brand")]),
    (5,  "Series",            [(39, "Series"), (40, "Flange Type")]),
    (7,  "Size",              [(39, "Size")]),
    (8,  "Pump Material",     [(39, "Pump Material")]),
    (9,  "Impeller Trim",     [(39, "Impeller Trim")]),
    (11, "Pump Options",      [
        (39, "Shaft Material"), (40, "Impeller Sleeve"), (41, "Wetted Hardware"),
        (42, "Pump Elastomers"), (43, "Flush"), (44, "Flush Options"),
        (45, "Impeller Balance"), (46, "Vapor Protection"), (47, "Strainer Options"),
    ]),
    (15, "Setting/Length",    [(39, "Setting/Length"), (40, "S-Dimension")]),
    (17, "Vertical Options",  [(39, "Tailpipe Option"), (40, "Tailpipe Length")]),
    (19, "Options",           [
        (39, "Coupling Option"), (40, "Coupling Guard"),
        (41, "Mounting Plate Option"), (42, "Customer Nameplate"),
    ]),
    (22, "Frame Size",        [(39, "Frame Size")]),
    (23, "Motor Assembly",    [
        (39, "Motor Option"), (40, "Motor Class"), (41, "Motor Orientation"),
        (42, "Horsepower"), (43, "RPM"), (44, "Voltage"), (45, "Hertz"),
        (46, "Frame"), (47, "Enclosure"), (48, "Efficiency"), (49, "Manufacturer"),
    ]),
    (26, "Motor Modifications", [
        (39, "Modification 1"), (40, "Modification 2"), (41, "Modification 3"),
    ]),
    (29, "Testing",           [
        (39, "Performance Testing"), (40, "Hydro Testing"),
        (41, "Vibration"), (42, "Sound Level"),
    ]),
]

# Source sheets that Smart Number lookups reference
SOURCE_SHEETS = [
    "Attributes",
    "Pump Options - Horizontal",
    "Pump Options - Vertical",
    "Seal Assembly - Horizontal",
    "Setting-Length-Vertical",
    "Options - Horizontal",
    "Options - Vertical",
    "Motor Assy",
    "Testing",
]


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


def compile_orientation(ws, title_row: int, pn_row: int, code_row: int,
                        label_row: int, segments: list, orientation: str) -> dict[str, Any]:
    """Compile segment structure for one orientation (H or V)."""
    title   = _str(ws.cell(row=title_row, column=4).value)
    example_pn = _str(ws.cell(row=pn_row, column=4).value)

    segment_list = []
    for col, seg_name, field_rows in segments:
        code  = _str(ws.cell(row=code_row, column=col).value)
        label = _str(ws.cell(row=label_row, column=col).value)

        # Read actual selection values shown in the example configuration
        fields = []
        for row_num, field_name in field_rows:
            # Field label is typically 2 cols right of segment col; value 3 cols right
            # But layout varies — read actual cell values at the expected positions
            val = _str(ws.cell(row=row_num, column=col + 9).value)  # value col pattern
            if val is None:
                # try adjacent columns for label/value pair
                for offset in range(1, 10):
                    v = _str(ws.cell(row=row_num, column=col + offset).value)
                    if v:
                        val = v
                        break
            fields.append({
                "field": field_name,
                "example_value": val,
            })

        segment_list.append({
            "col": col,
            "col_letter": chr(64 + col) if col <= 26 else "A" + chr(64 + col - 26),
            "segment_name": seg_name,
            "example_code": code,
            "label": label,
            "fields": fields,
        })

    return {
        "orientation": orientation,
        "title": title,
        "example_part_number": example_pn,
        "part_number_cell": f"D{pn_row}",
        "segment_count": len(segment_list),
        "part_number_format": _build_pn_format(segments),
        "segments": segment_list,
    }


def _build_pn_format(segments: list) -> str:
    """Build a human-readable part number format string from segment list."""
    # Group segments by separator groups (matching the actual PN structure)
    # The part number uses '-' between logical groups, not between every segment
    names = [seg_name for _, seg_name, _ in segments]
    # Known groupings from workbook observation:
    # Group1: Brand+Series+Size+Material+Trim (no separators)
    # Group2: PumpOptions
    # Group3: SealMfg+SealAssy  OR  Setting/Length+VertOptions
    # Group4: Options
    # Group5: FrameSize+MotorAssy
    # Group6: MotorMods
    # Group7: Testing
    return " - ".join([
        "".join(n for n in names[:5]),
        names[5] if len(names) > 5 else "",
        "".join(names[6:8]) if len(names) > 7 else "",
        names[8] if len(names) > 8 else "",
        "".join(names[9:11]) if len(names) > 10 else "",
        names[11] if len(names) > 11 else "",
        names[12] if len(names) > 12 else "",
    ])


def build_model(repo_root: Path) -> dict[str, Any]:
    commit, clean = git_info(repo_root)

    wb = openpyxl.load_workbook(
        str(repo_root / WORKBOOK_REL), read_only=True, data_only=True
    )
    ws = wb[SHEET]

    horizontal = compile_orientation(
        ws,
        title_row=H_TITLE_ROW, pn_row=H_PART_NUMBER_ROW,
        code_row=H_CODE_ROW, label_row=H_LABEL_ROW,
        segments=HORIZONTAL_SEGMENTS, orientation="Horizontal",
    )

    vertical = compile_orientation(
        ws,
        title_row=V_TITLE_ROW, pn_row=V_PART_NUMBER_ROW,
        code_row=V_CODE_ROW, label_row=V_LABEL_ROW,
        segments=VERTICAL_SEGMENTS, orientation="Vertical",
    )

    # Read example part numbers directly
    horizontal["example_part_number"] = _str(ws.cell(row=H_PART_NUMBER_ROW, column=4).value)
    horizontal["example_description"] = _str(ws.cell(row=H_DESCRIPTION_ROW, column=4).value)
    vertical["example_part_number"]   = _str(ws.cell(row=V_PART_NUMBER_ROW, column=4).value)
    vertical["legacy_part_number"]    = _str(ws.cell(row=V_LEGACY_PN_ROW, column=4).value)

    # Read the actual code row for both orientations
    h_codes = {}
    for col, seg_name, _ in HORIZONTAL_SEGMENTS:
        c = _str(ws.cell(row=H_CODE_ROW, column=col).value)
        if c:
            h_codes[seg_name] = c
    horizontal["example_codes"] = h_codes

    v_codes = {}
    for col, seg_name, _ in VERTICAL_SEGMENTS:
        c = _str(ws.cell(row=V_CODE_ROW, column=col).value)
        if c:
            v_codes[seg_name] = c
    vertical["example_codes"] = v_codes

    wb.close()

    return {
        "step": STEP,
        "roadmap_version": ROADMAP_VERSION,
        "milestone": MILESTONE,
        "source_workbook": WORKBOOK_REL,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit,
        "git_working_tree_clean": clean,
        "source_sheets_referenced": SOURCE_SHEETS,
        "horizontal": horizontal,
        "vertical": vertical,
        "findings": {
            "part_number_separator": "-",
            "part_number_cell_horizontal": f"D{H_PART_NUMBER_ROW}",
            "part_number_cell_vertical": f"D{V_PART_NUMBER_ROW}",
            "horizontal_segments": len(HORIZONTAL_SEGMENTS),
            "vertical_segments": len(VERTICAL_SEGMENTS),
            "orientation_diff": [
                "Horizontal: Seal Manufacturer + Seal Assembly segment group",
                "Vertical: Setting/Length + Vertical Options segment group replaces Seal group position",
                "Horizontal: Pump Options include Flush, Casing Drains, Suction Discharge, Shaft Material, Bearing, Gland Hardware",
                "Vertical: Pump Options include Shaft Material, Wetted Hardware, Flush, Vapor Protection, Strainer",
                "Vertical: Setting/Length segment encodes setting number + dimension code",
                "Vertical: Legacy part number format (F<series>-<size><trim>) also displayed (row 35)",
            ],
        },
    }


def _banner(title: str) -> str:
    line = "=" * 120
    return f"{line}\r\n{title}\r\n{line}\r\n\r\n"


def write_outputs(evidence_dir: Path, result: dict[str, Any]) -> None:
    payload = {"artifact": "FYBROC_V6_SMART_NUMBER", **result}
    (evidence_dir / "FYBROC_V6_SMART_NUMBER.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    h = result["horizontal"]
    v = result["vertical"]

    lines = [_banner("F110.4 - FYBROC V6 SMART NUMBER (Part Number Construction Flow, Both Orientations)")]
    lines.append(
        f"Git commit  : {result['git_commit']}\r\n"
        f"Git clean   : {result['git_working_tree_clean']}\r\n\r\n"
        f"Source sheets referenced: {', '.join(result['source_sheets_referenced'])}\r\n\r\n"
    )

    for orient_data in [h, v]:
        lines.append(_banner(f"{orient_data['orientation'].upper()} PART NUMBER"))
        lines.append(
            f"  Title              : {orient_data['title']}\r\n"
            f"  Part Number Cell   : {orient_data['part_number_cell']}\r\n"
            f"  Example PN         : {orient_data['example_part_number']}\r\n"
            f"  Separator          : \"-\"\r\n"
            f"  Segment count      : {orient_data['segment_count']}\r\n"
            f"  Format             : {orient_data['part_number_format']}\r\n\r\n"
            f"  Example codes      : {orient_data['example_codes']}\r\n\r\n"
        )
        lines.append("  SEGMENTS:\r\n")
        for seg in orient_data["segments"]:
            lines.append(
                f"    Col {seg['col_letter']:<3} [{seg['segment_name']:<22}]"
                f"  code={seg['example_code'] or '—':<8}\r\n"
            )
            for f in seg["fields"]:
                lines.append(f"          {f['field']:<35} = {f['example_value'] or '—'}\r\n")
            lines.append("\r\n")

    lines.append(_banner("ORIENTATION DIFFERENCES"))
    for finding in result["findings"]["orientation_diff"]:
        lines.append(f"  - {finding}\r\n")

    (evidence_dir / "FYBROC_V6_SMART_NUMBER.txt").write_text(
        "".join(lines), encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="F110.4 Fybroc V6 Smart Number compiler")
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
        "horizontal_segments": result["horizontal"]["segment_count"],
        "horizontal_example_pn": result["horizontal"]["example_part_number"],
        "vertical_segments": result["vertical"]["segment_count"],
        "vertical_example_pn": result["vertical"]["example_part_number"],
        "vertical_legacy_pn": result["vertical"]["legacy_part_number"],
        "source_sheets": result["source_sheets_referenced"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

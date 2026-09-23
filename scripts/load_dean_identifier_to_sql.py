"""D130 - Load the Dean identifier authority into SQL (DEAN-scoped, idempotent).

Loads TWO things, both family-scoped to DEAN and additive (never touches Fybroc):

  1. A#/D# model identity  ->  cfg.PumpModelReference
     Series+Size -> authoritative A-number (model_identifier) -> D-number
     (base_identifier). Source: exports/m023_dean_source_reconciliation.json
     (pump_options_matrix.models, 206 models).

  2. Segment String->Base-36 Code maps  ->  stg.SegmentCombinationImport
     (under a FamilyCode='DEAN' batch) - the SAME runtime store Fybroc uses.
     Each row: SegmentCode, SelectionsJson (the '*'-joined ComboString components,
     as a JSON object in the numbering table's column order), SegmentValue (the
     base-36 code), ExpectedWidth (= len(code)). Source: the numbering sheets of
     workbooks/Dean/Dean Data Sheet Rev 2.xlsm.

The Dean Part Number (Smart Number!B5 + J5) is:
  D<A#>-<WetEnd(4)>-<Trim(2)><ImpOpts(2)>-<PowerEnd(3)>-<Seal(5)>
    -<Flush(2)><Barrier><Cooling(2)>-<Frame(2)><Baseplate(3)>
    -<Motor(4)><MotorOpts(2)>-<AddlOpts(2)>-<Testing(2)><Doc(4)>

This loader populates the table-lookup segments (the FILTER-backed ones). The
special segments computed by the resolver at request time (Seal 00000/TBD__,
Impeller Trim inch/decimal letters, Flush Config-Info array, Barrier Table76,
Motor-Frame BASE(MATCH), and the segment gates) are NOT enumerated here.

Idempotent: re-running replaces the DEAN model-reference rows and the DEAN
segment-combination batch for the same source-file hash.

Usage:
  $env:PYTHONPATH="."
  python scripts/load_dean_identifier_to_sql.py [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pyodbc
from openpyxl import load_workbook

CONN = (
    "DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;"
    "DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;"
    "Encrypt=yes;TrustServerCertificate=yes;"
)

WB_PATH = Path("workbooks/Dean/Dean Data Sheet Rev 2.xlsm")
RECON_PATH = Path("exports/m023_dean_source_reconciliation.json")
FAMILY = "DEAN"

# ---------------------------------------------------------------------------
# Numbering-sheet layout (0-based column indexes), confirmed by direct read.
# Row 2 (1-based) is the header; data starts at row 3. Each entry:
#   sheet, segment_code, segment_name, string_col0, code_col0, expected_width,
#   field_order (the numbering table's option columns, in ComboString order)
# The field_order column labels come from the sheet's row-2 header and match the
# Smart Number FILTER predicate order (see docs/evidence/D130/DEAN_D130_DESIGN.md
# section 7a).
# ---------------------------------------------------------------------------
SEGMENTS = [
    {
        "sheet": "Wet End Numbering",
        "segment_code": "WET_END_OPTIONS",
        "segment_name": "Wet End Options",
        "string_col": 14,   # O
        "code_col": 15,     # P
        "width": 4,
        "field_order": [
            "Pump Material Class", "Casing Material", "Flange Style", "Casing Taps",
            "Drain Options", "Casing Mount", "Casing Gasket", "Shipping Gasket",
            "Wear Ring Material", "Tack weld wear rings", "Seal Chamber Config",
            "Spot-Facing",
        ],
    },
    {
        "sheet": "Wet End Numbering",
        "segment_code": "IMPELLER_OPTIONS",
        "segment_name": "Impeller Options",
        "string_col": 35,   # AJ
        "code_col": 36,     # AK
        "width": 2,
        "field_order": [
            "Impeller Balance", "Impeller Material", "Wear Rings", "Balance Holes",
        ],
    },
    {
        "sheet": "Power End Numbering",
        "segment_code": "POWER_FRAME_OPTIONS",
        "segment_name": "Power Frame Options",
        "string_col": 13,   # N (pre-joined String)
        "code_col": 14,     # O
        "width": 2,         # codes are 2-wide (e.g. '04','2C'); dean.json profile
                            # says 3 but the authoritative sheet uses 2 -> follow sheet
        "field_order": [
            "Shaft Configuration", "Shaft Material", "Lubrication Options",
            "Oiler Options", "Oil Seal", "Sight Glass", "Magnetic Drain",
            "Expansion Chamber", "Bearing Frame Cooling", "Coupling Guard",
            "Coupling Type",
        ],
    },
    {
        "sheet": "Misc Numbering",
        "segment_code": "COOLING_PLAN",
        "segment_name": "Cooling Plan",
        "string_col": 6,    # G
        "code_col": 5,      # F
        "width": 2,
        "field_order": ["Cooling Plan", "Cooling Plan Piping", "Cooling Plan Extras"],
    },
    {
        "sheet": "Misc Numbering",
        "segment_code": "ADDITIONAL_OPTIONS",
        "segment_name": "Additional Options",
        "string_col": 15,   # P
        "code_col": 14,     # O
        "width": 2,
        "field_order": [
            "Shipping Gasket", "Auxillary Nameplate", "Crating", "Paint Options",
            "Coating",
        ],
    },
    {
        # Baseplate has NO pre-joined String column; the option combination is
        # stored across separate columns C..K per row. We join them ourselves.
        "sheet": "Baseplate Numbering",
        "segment_code": "BASEPLATE_OPTIONS",
        "segment_name": "Baseplate Options",
        "columns_mode": True,
        "combo_cols": [2, 3, 4, 5, 6, 7, 8, 9, 10],  # C..K
        "code_col": 11,     # L
        "width": 3,
        "field_order": [
            "Baseplate Type", "Drip Pan", "Alignment Lugs", "Lifting Lugs",
            "Levelling Screws", "Grounding Lug", "Grout Hole", "Isolation Pads",
            "Stilts",
        ],
    },
    {
        "sheet": "Test and Doc Numbering",
        "segment_code": "TESTING",
        "segment_name": "Testing",
        "string_col": 8,    # I
        "code_col": 7,      # H
        "width": 2,
        "field_order": [
            "Performance Testing", "Hydrotest", "General Inspection", "Vibration",
            "Sound Level",
        ],
    },
    {
        "sheet": "Test and Doc Numbering",
        "segment_code": "DOCUMENTATION",
        "segment_name": "Documentation",
        "string_col": 18,   # S
        "code_col": 20,     # U
        "width": 4,
        "field_order": ["Document 1", "Document 2", "Document 3", "Document 4"],
    },
    {
        "sheet": "Motor Numbering",
        "segment_code": "MOTOR",
        "segment_name": "Motor",
        "string_col": 14,   # O
        "code_col": 13,     # N
        "width": 3,
        "field_order": [
            "Motor", "Motor Control", "Rated Power", "Rated Speed", "Motor Voltage",
            "Phase/Frequency", "Motor Enclosure", "Motor Efficiency", "Motor Brand",
        ],
    },
]

HEADER_ROW = 2   # 1-based; data starts at row 3


def sha256_file(path: Path) -> str:
    d = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            d.update(chunk)
    return d.hexdigest()


def _col0(letter_idx0: int) -> str:
    idx = letter_idx0 + 1
    s = ""
    while idx > 0:
        idx, r = divmod(idx - 1, 26)
        s = chr(65 + r) + s
    return s


# ---------------------------------------------------------------------------
# 1. A#/D# identity
# ---------------------------------------------------------------------------
def load_models(conn, dry_run: bool) -> int:
    data = json.loads(RECON_PATH.read_text(encoding="utf-8"))
    models = data.get("pump_options_matrix", {}).get("models") or []
    if not models:
        # fallback: find any list of dicts with model_identifier
        def walk(o):
            if isinstance(o, list) and o and isinstance(o[0], dict) \
               and "model_identifier" in o[0]:
                return o
            if isinstance(o, dict):
                for v in o.values():
                    r = walk(v)
                    if r:
                        return r
            if isinstance(o, list):
                for v in o:
                    r = walk(v)
                    if r:
                        return r
            return None
        models = walk(data) or []
    # keep only rows with a real A#/D#
    rows = []
    for m in models:
        a = (m.get("model_identifier") or "").strip()
        d = (m.get("base_identifier") or "").strip()
        series = (m.get("series") or "").strip()
        size = (m.get("size") or "").strip()
        if not (a and d and series and size):
            continue
        rows.append((series, size, a, d, m.get("source_worksheet", "Pump Options"),
                     int(m.get("source_row", 0) or 0)))
    print(f"[models] {len(rows)} A#/D# identity rows parsed from reconciliation JSON")
    if dry_run:
        for r in rows[:5]:
            print("   sample:", r)
        return len(rows)

    cur = conn.cursor()
    fam_id = cur.execute(
        "SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode=?", FAMILY
    ).fetchone()[0]
    cv_id = cur.execute(
        "SELECT ConfigurationVersionId FROM cfg.ConfigurationVersion "
        "WHERE PumpFamilyId=? AND IsCurrent=1", fam_id
    ).fetchone()[0]

    # idempotent: clear existing DEAN model refs for this cv, then reload
    cur.execute(
        "DELETE FROM cfg.PumpModelReference WHERE PumpFamilyId=? AND ConfigurationVersionId=?",
        fam_id, cv_id,
    )
    ins = (
        "INSERT INTO cfg.PumpModelReference "
        "(PumpFamilyId, ConfigurationVersionId, ModelIdentifier, SeriesCode, "
        " SizeCode, BaseIdentifier, IsActive, SourceWorksheet, SourceRow) "
        "VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)"
    )
    # dedupe on (series,size): the UX index is (family,cv,series,size) WHERE IsActive=1
    seen = {}
    for series, size, a, d, ws, srow in rows:
        seen[(series.upper(), size.upper())] = (series.upper(), size.upper(), a, d, ws, srow)
    payload = [(fam_id, cv_id, a, s, z, d, ws, srow)
               for (s, z, a, d, ws, srow) in seen.values()]
    cur.fast_executemany = True
    cur.executemany(ins, payload)
    conn.commit()
    print(f"[models] loaded {len(payload)} unique (series,size) rows into "
          f"cfg.PumpModelReference (family={fam_id}, cv={cv_id})")
    return len(payload)


# ---------------------------------------------------------------------------
# 2. Segment String->Code maps
# ---------------------------------------------------------------------------
def extract_segment_rows(wb, seg):
    """Yield (source_id, source_row, combo_string, code, selections_dict) for a
    segment's numbering sheet, reading only the needed columns in bulk.

    Two layouts:
      - String mode (default): a pre-joined '*'-String column + a code column.
      - columns_mode: the combination is spread across combo_cols (join with '*').
    """
    ws = wb[seg["sheet"]]
    ccol, width = seg["code_col"], seg["width"]
    columns_mode = seg.get("columns_mode", False)
    if columns_mode:
        combo_cols = seg["combo_cols"]
        max_col = max(max(combo_cols), ccol) + 1
    else:
        scol = seg["string_col"]
        max_col = max(scol, ccol) + 1

    source_id = 0
    # data starts at row 3 (1-based); header at row 2
    for r_idx, row in enumerate(
        ws.iter_rows(min_row=HEADER_ROW + 1, max_col=max_col, values_only=True),
        start=HEADER_ROW + 1,
    ):
        code = row[ccol] if ccol < len(row) else None
        if code is None:
            continue
        code_s = str(code).strip()
        if code_s == "" or code_s.lower() in ("base-36 code", "code"):
            continue
        if len(code_s) != width:  # mirrors SQL CHECK(LEN=ExpectedWidth)
            continue

        if columns_mode:
            parts = [("" if (c >= len(row) or row[c] is None) else str(row[c]).strip())
                     for c in combo_cols]
            if all(p == "" for p in parts):
                continue
            combo_s = "*".join(parts)
        else:
            combo = row[scol] if scol < len(row) else None
            if combo is None:
                continue
            combo_s = str(combo).strip()
            if combo_s == "" or combo_s.lower() == "string":
                continue
            parts = combo_s.split("*")

        selections = {seg["field_order"][i]: parts[i]
                      for i in range(min(len(parts), len(seg["field_order"])))}
        source_id += 1
        yield source_id, r_idx, combo_s, code_s, selections


def load_segments(conn, wb, dry_run: bool) -> dict:
    source_hash = sha256_file(WB_PATH)
    counts = {}
    if dry_run:
        for seg in SEGMENTS:
            n = sum(1 for _ in extract_segment_rows(wb, seg))
            counts[seg["segment_code"]] = n
            if seg.get("columns_mode"):
                src = "cols " + _col0(seg["combo_cols"][0]) + ".." + _col0(seg["combo_cols"][-1])
            else:
                src = "String=" + _col0(seg["string_col"])
            print(f"[segment] {seg['segment_code']:<22} {seg['sheet']:<24} "
                  f"{src} Code={_col0(seg['code_col'])} "
                  f"width={seg['width']}  rows={n:,}")
        return counts

    cur = conn.cursor()
    # idempotent: drop any prior DEAN batch for this exact source hash
    existing = cur.execute(
        "SELECT ImportBatchId FROM stg.SegmentCombinationImportBatch "
        "WHERE FamilyCode=? AND SourceFileHash=?", FAMILY, source_hash
    ).fetchone()
    if existing:
        bid = int(existing[0])
        cur.execute("DELETE FROM stg.SegmentCombinationImport WHERE ImportBatchId=?", bid)
        cur.execute("DELETE FROM stg.SegmentCombinationImportBatch WHERE ImportBatchId=?", bid)
        conn.commit()
        print(f"[segment] replaced existing DEAN batch {bid}")

    # We compute the expected row count as we go; create the batch first.
    batch_id = int(cur.execute(
        "INSERT INTO stg.SegmentCombinationImportBatch "
        "(FamilyCode, SourceFile, SourceFileHash, ExpectedRowCount, Status) "
        "OUTPUT INSERTED.ImportBatchId VALUES (?, ?, ?, 0, 'Loading')",
        FAMILY, str(WB_PATH.resolve()), source_hash,
    ).fetchone()[0])
    conn.commit()

    ins = (
        "INSERT INTO stg.SegmentCombinationImport "
        "(ImportBatchId, FamilyCode, WorkbookRole, WorkbookName, WorksheetName, "
        " SegmentCode, SegmentName, SourceRow, SourceId, SegmentValue, "
        " ExpectedWidth, CombinationKey, SelectionsJson, SourceCellsJson, SourceProfile) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    cur.fast_executemany = True
    total = 0
    for seg in SEGMENTS:
        buf = []
        seg_rows = 0
        for source_id, srow, combo_s, code_s, selections in extract_segment_rows(wb, seg):
            sel_json = json.dumps(selections, separators=(",", ":"))
            if seg.get("columns_mode"):
                src_desc = {"combo_cols": [_col0(c) for c in seg["combo_cols"]],
                            "code_col": _col0(seg["code_col"]), "row": srow}
            else:
                src_desc = {"string_col": _col0(seg["string_col"]),
                            "code_col": _col0(seg["code_col"]), "row": srow}
            cells_json = json.dumps(src_desc, separators=(",", ":"))
            buf.append((
                batch_id, FAMILY, "configuration_and_quote",
                WB_PATH.name, seg["sheet"], seg["segment_code"], seg["segment_name"],
                srow, source_id, code_s, seg["width"], combo_s, sel_json,
                cells_json, "dean_numbering_v1",
            ))
            if len(buf) >= 2000:
                cur.executemany(ins, buf)
                conn.commit()
                total += len(buf)
                seg_rows += len(buf)
                buf = []
        if buf:
            cur.executemany(ins, buf)
            conn.commit()
            total += len(buf)
            seg_rows += len(buf)
        counts[seg["segment_code"]] = seg_rows
        print(f"[segment] {seg['segment_code']:<22} loaded {seg_rows:,} rows")

    cur.execute(
        "UPDATE stg.SegmentCombinationImportBatch "
        "SET LoadedRowCount=?, ExpectedRowCount=?, Status='Loaded', "
        "    CompletedAt=SYSUTCDATETIME() WHERE ImportBatchId=?",
        total, total, batch_id,
    )
    conn.commit()
    print(f"[segment] DEAN batch {batch_id}: {total:,} total segment rows loaded")
    counts["_batch_id"] = batch_id
    counts["_total"] = total
    return counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="parse + count only; no DB writes")
    args = ap.parse_args()

    if not WB_PATH.exists():
        raise SystemExit(f"Workbook not found: {WB_PATH}")
    if not RECON_PATH.exists():
        raise SystemExit(f"Reconciliation JSON not found: {RECON_PATH}")

    print(f"Loading workbook {WB_PATH} (read_only) ...", flush=True)
    wb = load_workbook(WB_PATH, read_only=True, data_only=True, keep_vba=False)

    conn = None if args.dry_run else pyodbc.connect(CONN, autocommit=False)
    try:
        n_models = load_models(conn, args.dry_run)
        seg_counts = load_segments(conn, wb, args.dry_run)
    finally:
        wb.close()
        if conn is not None:
            conn.close()

    print("\n=== SUMMARY ===")
    print(f"models (A#/D#): {n_models}")
    for k, v in seg_counts.items():
        if not k.startswith("_"):
            print(f"  {k}: {v:,}")
    print("DONE")


if __name__ == "__main__":
    main()

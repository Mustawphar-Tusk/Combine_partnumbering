"""Load the NEW Dean Motor Numbering (workbooks/Dean/Motor Numbering.xlsm).

This REPLACES the old frame-only Dean motor with the authoritative multi-field
motor spec from engineering's new workbook. Three loads, all DEAN-only and
additive to the frozen Fybroc data:

  1. MOTOR_SPEC segment -> stg.SegmentCombinationImport (APPENDED to the CURRENT
     Loaded DEAN batch; the main identifier loader owns the batch and we do not
     supersede it). Each of the 34,084 enumerated motor combinations becomes one
     row: SegmentValue = the 4-char Combined Alphanumeric Code (brand letter +
     3-char base), CombinationKey = '*'-joined spec values in MOTOR_SPEC field
     order, SelectionsJson = {field_code: value}. This is the motor allow-list +
     numbering source the resolver reads.

  2. Motor option fields -> cfg.SeriesFieldOption (DEAN, series-level for every
     Dean series). The allowed values are DERIVED FROM THE COMBINATIONS (the
     enumerated reality), not the thin options header - e.g. Voltage really has
     6 values in the combos, not the 1 the header shows. STD = first value seen.

  3. Motor price -> price.DeanMotorPrice (new additive table), keyed by the
     unique 4-char code: numeric Amount where the workbook has a number,
     IsContactFactory=1 where the workbook says 'C.F.' (491 numeric / 33,593 C.F.).

Source ranges (sheet 'Pricing'):
  - Options block : Q1:AC72    (field headers; values come from the combos)
  - Combinations  : R95:AG34179 (header row 95; data 96..34179)

Usage:
  $env:PYTHONPATH="."
  python scripts/load_dean_motor_numbering.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pyodbc
from openpyxl import load_workbook

CONN = (
    "DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;"
    "DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;"
    "Encrypt=yes;TrustServerCertificate=yes;"
)
WB_PATH = Path("workbooks/Dean/Motor Numbering.xlsm")
FAMILY = "DEAN"
SEGMENT_CODE = "MOTOR_SPEC"
SEGMENT_NAME = "Motor Spec"
CODE_WIDTH = 4

# Combos block (sheet 'Pricing', 1-based columns). Header row 95, data 96..34179.
COMBO_HEADER_ROW = 95
COMBO_FIRST_DATA_ROW = 96
COMBO_LAST_DATA_ROW = 34179
# Spec columns S..AB (19..28) in combos column order == MOTOR_SPEC field order.
SPEC_COLS = list(range(19, 29))            # S..AB
COL_COMBINED = 29                          # AC  Combined Alphanumeric Code
COL_PRICE = 30                             # AD  Price

# combos spec header label -> canonical Dean motor field code (MOTOR_SPEC order).
HEADER_TO_FIELD = {
    "Motor": "MOTOR",
    "Motor Control": "MOTOR_CONTROL",
    "Frame Size": "FRAME_SIZE",
    "Rated Speed": "RATED_SPEED",
    "Rated Power": "RATED_POWER",
    "Voltage": "VOLTAGE",
    "Phase/Frequency": "PHASE_FREQUENCY",
    "Enclosure": "ENCLOSURE",
    "Efficiency": "EFFICIENCY",
    "Brand": "BRAND",
}
# Canonical field order for the MOTOR_SPEC CombinationKey (== SPEC_COLS order).
MOTOR_FIELD_ORDER = [
    "MOTOR", "MOTOR_CONTROL", "FRAME_SIZE", "RATED_SPEED", "RATED_POWER",
    "VOLTAGE", "PHASE_FREQUENCY", "ENCLOSURE", "EFFICIENCY", "BRAND",
]

# Motor option fields loaded fresh into cfg.SeriesFieldOption. FRAME_SIZE is
# EXCLUDED: it already exists per-series (from Pump Constraints applicability) and
# is only CANONICALIZED in place (UPPER + VP->HP) so its values match the motor
# combos - its per-series applicable set is preserved, never replaced.
MOTOR_OPTION_FIELDS = [f for f in MOTOR_FIELD_ORDER if f != "FRAME_SIZE"]


def canon_frame(v):
    """Canonical FRAME_SIZE form (engineering rule): UPPERCASE + VP->HP suffix,
    so 143t / 143VP both become 143HP's sibling 143T-family codes. Applied to the
    motor combos AND the existing DB FRAME_SIZE values so they match."""
    import re
    u = str(v).strip().upper()
    return re.sub(r"VP$", "HP", u)


def _s(v):
    return "" if v is None else str(v).strip()


def read_combos(wb):
    """Yield (source_id, source_row, combo_key, code, selections, price_raw) for
    every enumerated motor combination. price_raw is the raw AD cell (number or
    the text 'C.F.')."""
    ws = wb["Pricing"]
    # verify header order matches HEADER_TO_FIELD expectation
    hdr = {}
    for row in ws.iter_rows(min_row=COMBO_HEADER_ROW, max_row=COMBO_HEADER_ROW,
                            min_col=1, max_col=COL_PRICE, values_only=True):
        for c0, v in enumerate(row, 1):
            hdr[c0] = _s(v)
    fields = []
    for c in SPEC_COLS:
        label = hdr.get(c, "")
        fld = HEADER_TO_FIELD.get(label)
        if fld is None:
            raise SystemExit(f"Unexpected combos header at col {c}: {label!r}")
        fields.append(fld)
    if fields != MOTOR_FIELD_ORDER:
        raise SystemExit(f"Combo field order mismatch: {fields} != {MOTOR_FIELD_ORDER}")

    source_id = 0
    for r_idx, row in enumerate(
        ws.iter_rows(min_row=COMBO_FIRST_DATA_ROW, max_row=COMBO_LAST_DATA_ROW,
                     min_col=1, max_col=COL_PRICE, values_only=True),
        start=COMBO_FIRST_DATA_ROW,
    ):
        code = _s(row[COL_COMBINED - 1])
        if code == "":
            continue
        if len(code) != CODE_WIDTH:
            raise SystemExit(f"row {r_idx}: code {code!r} width != {CODE_WIDTH}")
        parts = []
        selections = {}
        for off, c in enumerate(SPEC_COLS):
            val = _s(row[c - 1])
            fld = MOTOR_FIELD_ORDER[off]
            # Canonicalize the frame to match the DB FRAME_SIZE values (UPPER+VP->HP).
            # The motor combos already use the canonical form, but normalize anyway
            # so the CombinationKey and SelectionsJson are consistent with the
            # resolver's canonicalized selection value.
            if fld == "FRAME_SIZE":
                val = canon_frame(val)
            parts.append(val)
            selections[fld] = val
        combo_key = "*".join(parts)
        price_raw = row[COL_PRICE - 1]
        source_id += 1
        yield source_id, r_idx, combo_key, code, selections, price_raw


def _price_num(price_raw):
    """(amount, is_cf): numeric amount or None, and whether it's Contact Factory."""
    if isinstance(price_raw, (int, float)):
        return float(price_raw), False
    s = _s(price_raw).upper().replace(".", "").replace(" ", "")
    # 'C.F.' / 'CF' => contact factory
    if s in ("CF", ""):
        return None, True
    # any other text: try to parse a number, else treat as C.F.
    try:
        return float(str(price_raw).replace(",", "").replace("$", "").strip()), False
    except ValueError:
        return None, True


def current_dean_batch(cur):
    row = cur.execute(
        "SELECT TOP 1 ImportBatchId FROM stg.SegmentCombinationImportBatch "
        "WHERE FamilyCode=? AND Status='Loaded' ORDER BY ImportBatchId DESC", FAMILY
    ).fetchone()
    return int(row[0]) if row else None


def active_pub(cur):
    return int(cur.execute(
        "SELECT TOP 1 MetadataPublicationId FROM cfg.MetadataPublication "
        "WHERE Status='Active' ORDER BY ActivatedAt DESC").fetchone()[0])


def dean_series(cur):
    """Dean series codes (authoritative from cfg.PumpModelReference, family-scoped).
    Used to attach the motor option fields at series level and to scope the
    Fybroc-isolation watermark (non-Dean series)."""
    pid = cur.execute(
        "SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode=?", FAMILY
    ).fetchone()[0]
    rows = cur.execute(
        "SELECT DISTINCT SeriesCode FROM cfg.PumpModelReference "
        "WHERE PumpFamilyId=? AND IsActive=1", pid
    ).fetchall()
    return pid, sorted({r[0] for r in rows})


def fybroc_watermarks(cur, pub, dean_series_set):
    """Isolation watermark: Fybroc rows that MUST be unchanged. Family is the
    authoritative discriminator: Fybroc = PumpFamilyId <> DEAN's id (NOT a series
    heuristic). This is what every Dean-only write must leave untouched."""
    deanpid = cur.execute(
        "SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode=?", FAMILY).fetchone()[0]
    return {
        "FeasibleConstraint": cur.execute(
            "SELECT COUNT(*) FROM cfg.FeasibleConstraint").fetchone()[0],
        "SeriesFieldOption_nonDEAN": cur.execute(
            "SELECT COUNT(*) FROM cfg.SeriesFieldOption "
            "WHERE MetadataPublicationId=? AND PumpFamilyId<>?", pub, deanpid).fetchone()[0],
        "SegmentCombinationImport_nonDEAN": cur.execute(
            "SELECT COUNT(*) FROM stg.SegmentCombinationImport WHERE FamilyCode<>?",
            FAMILY).fetchone()[0],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not WB_PATH.exists():
        raise SystemExit(f"Workbook not found: {WB_PATH}")

    print(f"Loading {WB_PATH} (read_only) ...", flush=True)
    wb = load_workbook(WB_PATH, read_only=True, data_only=True, keep_vba=False)

    combos = list(read_combos(wb))
    wb.close()
    n = len(combos)
    numeric = sum(1 for *_, pr in combos if _price_num(pr)[1] is False)
    cf = n - numeric
    # derive per-field allowed values (in first-seen order) from the combos
    field_values: dict[str, list[str]] = {f: [] for f in MOTOR_FIELD_ORDER}
    seen: dict[str, set] = {f: set() for f in MOTOR_FIELD_ORDER}
    for _sid, _sr, _ck, _code, sel, _pr in combos:
        for f in MOTOR_FIELD_ORDER:
            v = sel[f]
            if v and v not in seen[f]:
                seen[f].add(v)
                field_values[f].append(v)

    print(f"[motor] combos parsed: {n:,}  numeric price: {numeric}  C.F.: {cf}")
    for f in MOTOR_FIELD_ORDER:
        print(f"[motor] field {f:<16} values={len(field_values[f])}")

    if args.dry_run:
        print("[dry-run] no DB writes.")
        print("sample combo:", combos[0][2], "->", combos[0][3],
              "price", combos[0][5])
        return

    conn = pyodbc.connect(CONN, autocommit=False)
    cur = conn.cursor()
    pub_id = active_pub(cur)
    pid, series_list = dean_series(cur)
    dean_series_set = set(series_list)
    pre = fybroc_watermarks(cur, pub_id, dean_series_set)
    print("pre Fybroc watermarks:", pre)

    batch_id = current_dean_batch(cur)
    if batch_id is None:
        raise SystemExit("No Loaded DEAN segment batch found - run "
                         "load_dean_identifier_to_sql.py first.")
    print(f"[motor] appending MOTOR_SPEC into current DEAN batch {batch_id}")

    # --- idempotency: remove any prior MOTOR_SPEC rows in this batch ---
    cur.execute("DELETE FROM stg.SegmentCombinationImport "
                "WHERE ImportBatchId=? AND SegmentCode=?", batch_id, SEGMENT_CODE)
    conn.commit()

    ins = (
        "INSERT INTO stg.SegmentCombinationImport "
        "(ImportBatchId, FamilyCode, WorkbookRole, WorkbookName, WorksheetName, "
        " SegmentCode, SegmentName, SourceRow, SourceId, SegmentValue, "
        " ExpectedWidth, CombinationKey, SelectionsJson, SourceCellsJson, SourceProfile) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
    )
    cur.fast_executemany = True
    buf = []
    loaded = 0
    for source_id, srow, combo_key, code, selections, _pr in combos:
        sel_json = json.dumps(selections, separators=(",", ":"))
        cells_json = json.dumps({"sheet": "Pricing", "row": srow, "mode": "motor_combos"},
                                separators=(",", ":"))
        buf.append((batch_id, FAMILY, "configuration_and_quote", WB_PATH.name,
                    "Pricing", SEGMENT_CODE, SEGMENT_NAME, srow, source_id, code,
                    CODE_WIDTH, combo_key, sel_json, cells_json, "dean_motor_numbering"))
        if len(buf) >= 2000:
            cur.executemany(ins, buf); conn.commit(); loaded += len(buf); buf = []
    if buf:
        cur.executemany(ins, buf); conn.commit(); loaded += len(buf)
    # Set the batch LoadedRowCount to the ACTUAL current row count for this batch
    # (idempotent: safe to re-run without double-counting).
    cur.execute("UPDATE b SET b.LoadedRowCount = x.cnt "
                "FROM stg.SegmentCombinationImportBatch b "
                "CROSS APPLY (SELECT COUNT(*) cnt FROM stg.SegmentCombinationImport "
                "             WHERE ImportBatchId=?) x WHERE b.ImportBatchId=?",
                batch_id, batch_id)
    conn.commit()
    print(f"[motor] MOTOR_SPEC rows loaded: {loaded:,}")

    # --- 2a) CANONICALIZE existing FRAME_SIZE in place (UPPER + VP->HP).
    # Preserves each series' applicable frame SET; only renames values so they
    # match the motor combos. De-duplicates if a canonical form now collides
    # (e.g. '143t' and '143T' -> one '143T'); keeps IsStandard if any source row
    # was standard. DEAN series only; Fybroc FRAME_SIZE (other series) untouched.
    frame_rows = cur.execute(
        "SELECT SeriesFieldOptionId, SeriesCode, SizeCode, OptionValue, IsStandard "
        "FROM cfg.SeriesFieldOption "
        "WHERE MetadataPublicationId=? AND PumpFamilyId=? AND FieldCode='FRAME_SIZE'",
        pub_id, pid).fetchall()
    # group by (series, size, canonical value). The query is already DEAN-family
    # scoped; the dean_series_set guard is a belt-and-suspenders second filter.
    canon_map: dict = {}
    for sfo_id, scode, sz, val, std in frame_rows:
        if scode not in dean_series_set:
            continue  # never touch non-Dean FRAME_SIZE
        key = (scode, sz, canon_frame(val))
        g = canon_map.setdefault(key, {"ids": [], "std": 0})
        g["ids"].append(sfo_id)
        g["std"] = g["std"] or (1 if std else 0)
    frame_canon_updated = 0
    frame_canon_deleted = 0
    for (scode, sz, cval), g in canon_map.items():
        keep = g["ids"][0]
        cur.execute("UPDATE cfg.SeriesFieldOption SET OptionValue=?, IsStandard=? "
                    "WHERE SeriesFieldOptionId=?", cval, g["std"], keep)
        frame_canon_updated += 1
        for dup in g["ids"][1:]:
            cur.execute("DELETE FROM cfg.SeriesFieldOption WHERE SeriesFieldOptionId=?", dup)
            frame_canon_deleted += 1
    conn.commit()
    print(f"[motor] FRAME_SIZE canonicalized (Dean): {frame_canon_updated} kept, "
          f"{frame_canon_deleted} case/VP dupes merged (applicability preserved)")

    # --- 2b) the OTHER 9 motor option fields into cfg.SeriesFieldOption
    #        (DEAN, series-level). FRAME_SIZE is NOT loaded here (handled above). ---
    # CRITICAL: scope the delete to PumpFamilyId=DEAN. Fybroc shares this table
    # and uses some of the SAME field codes (e.g. MOTOR_CONTROL), so a
    # family-unscoped delete would wipe Fybroc rows (Fybroc is FROZEN). Never
    # delete without the family filter.
    cur.execute(
        "DELETE FROM cfg.SeriesFieldOption WHERE MetadataPublicationId=? "
        "AND PumpFamilyId=? AND FieldCode IN ({})".format(
            ",".join("?" * len(MOTOR_OPTION_FIELDS))),
        pub_id, pid, *MOTOR_OPTION_FIELDS)
    conn.commit()
    sfo_ins = (
        "INSERT INTO cfg.SeriesFieldOption "
        "(MetadataPublicationId, PumpFamilyId, SourceFieldCode, FieldCode, OptionValue, "
        " SeriesCode, WorkbookName, WorksheetName, SourceRow, SourceFieldCell, "
        " SourceValueCell, SourceSeriesCell, SelectionMarker, IsStandard, IsActive) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)"
    )
    sbuf = []
    for series in series_list:
        for f in MOTOR_OPTION_FIELDS:
            for i, val in enumerate(field_values[f]):
                sbuf.append((
                    pub_id, pid, f, f, val, series,
                    WB_PATH.name, "Pricing", 0, "Q1", "Q2", "B",
                    "X", 1 if i == 0 else 0,
                ))
    cur.fast_executemany = True
    for i in range(0, len(sbuf), 2000):
        cur.executemany(sfo_ins, sbuf[i:i + 2000]); conn.commit()
    print(f"[motor] SeriesFieldOption rows: {len(sbuf):,} "
          f"({len(MOTOR_OPTION_FIELDS)} motor fields x {len(series_list)} series; "
          f"FRAME_SIZE preserved per-series)")

    # --- 3) price.DeanMotorPrice (create + load) ---
    cur.execute("""
        IF OBJECT_ID('price.DeanMotorPrice','U') IS NULL
        CREATE TABLE price.DeanMotorPrice(
            MotorCode char(4) NOT NULL PRIMARY KEY,
            Amount decimal(19,4) NULL,
            IsContactFactory bit NOT NULL,
            Brand nvarchar(50) NULL,
            SourceRow int NULL,
            LoadedAt datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME()
        );
    """)
    conn.commit()
    cur.execute("DELETE FROM price.DeanMotorPrice;")
    conn.commit()
    pins = ("INSERT INTO price.DeanMotorPrice "
            "(MotorCode, Amount, IsContactFactory, Brand, SourceRow) VALUES (?,?,?,?,?)")
    pbuf = []
    for _sid, srow, _ck, code, sel, price_raw in combos:
        amt, is_cf = _price_num(price_raw)
        pbuf.append((code, amt, 1 if is_cf else 0, sel.get("BRAND"), srow))
    cur.fast_executemany = True
    for i in range(0, len(pbuf), 2000):
        cur.executemany(pins, pbuf[i:i + 2000]); conn.commit()
    print(f"[motor] DeanMotorPrice rows: {len(pbuf):,} "
          f"(numeric {numeric} / C.F. {cf})")

    post = fybroc_watermarks(cur, pub_id, dean_series_set)
    print("post Fybroc watermarks:", post)
    assert pre == post, f"FYBROC watermarks changed! pre={pre} post={post}"
    print("FYBROC unchanged.")
    conn.close()
    print("DONE")


if __name__ == "__main__":
    main()

"""Full X/STD-vs-DB audit across ALL fields and ALL 10 series.

Reproduces load_all_series.py's transform EXACTLY (field_code = UPPER, spaces
and hyphens -> '_'; option value = lowercased; V6 flange authority drops
DIN/JIS for series outside 1500/1530/1600/1630), then diffs the resulting
"expected" (field_code, option_value, series, is_standard) set against the live
cfg.SeriesFieldOption for the active publication.

Any difference reported here is an UNEXPECTED divergence between the Rev0.3
Selections authority (+ documented V6 flange rule) and the runtime DB. An empty
diff is a clean bill of health.

Read-only. Prints a report; writes docs/evidence/F120/
FYBROC_SELECTIONS_DB_AUDIT.txt.
"""
from __future__ import annotations

import sys
from pathlib import Path

import openpyxl
import warnings
warnings.simplefilter("ignore")
import pyodbc

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from src.compiler.workbook_types import norm_series

WB = _ROOT / "workbooks" / "Fybroc" / "Fybroc Configuration Rev0.3.xlsx"
OUT = _ROOT / "docs" / "evidence" / "F120" / "FYBROC_SELECTIONS_DB_AUDIT.txt"
CONN = ("DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;"
        "DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;"
        "Encrypt=yes;TrustServerCertificate=yes;")

# Mirrors load_all_series.py exactly.
V6_DIN_JIS_SERIES = {"1500", "1530", "1600", "1630"}
NON_ANSI_FLANGE_ANSWERS = {"din/iso flange", "jis flange"}


def build_expected() -> set[tuple[str, str, str, int]]:
    wb = openpyxl.load_workbook(WB, read_only=True, data_only=True)
    ws = wb["Selections"]
    series_codes = []
    for c in range(4, 14):
        s = norm_series(ws.cell(row=1, column=c).value)
        if s:
            series_codes.append(s)

    expected: set[tuple[str, str, str, int]] = set()
    for r in range(2, 679):
        question = ws.cell(row=r, column=2).value
        answer = ws.cell(row=r, column=3).value
        if not question or not answer:
            continue
        question = str(question).strip()
        answer = str(answer).strip()
        field_code = question.upper().replace(" ", "_").replace("-", "_")
        for i, series in enumerate(series_codes):
            marker = ws.cell(row=r, column=4 + i).value
            marker = str(marker).strip() if marker is not None else ""
            mu = marker.upper()
            if mu in ("X", "STD"):
                if (field_code == "FLANGE_TYPE"
                        and answer.lower() in NON_ANSI_FLANGE_ANSWERS
                        and series not in V6_DIN_JIS_SERIES):
                    continue  # V6 flange authority
                is_standard = 1 if mu == "STD" else 0
                expected.add((field_code, answer.lower(), series, is_standard))
    wb.close()
    return expected, series_codes


def load_db() -> set[tuple[str, str, str, int]]:
    cn = pyodbc.connect(CONN)
    cur = cn.cursor()
    pub_id = cur.execute(
        "SELECT MetadataPublicationId FROM cfg.MetadataPublication WHERE Status='Active'"
    ).fetchone()[0]
    # Scope to the FYBROC family: cfg.SeriesFieldOption is shared across families
    # (Dean rows were added in D110), so this Fybroc authority audit must filter
    # by PumpFamilyId or it would see Dean rows as spurious "EXTRA".
    fybroc_id = cur.execute(
        "SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode='FYBROC'"
    ).fetchone()[0]
    got = set()
    for row in cur.execute(
        "SELECT FieldCode, OptionValue, SeriesCode, IsStandard "
        "FROM cfg.SeriesFieldOption WHERE MetadataPublicationId=? AND PumpFamilyId=?",
        pub_id, fybroc_id):
        got.add((str(row[0]).strip(), str(row[1]).strip(),
                 str(row[2]).strip(), 1 if row[3] else 0))
    cn.close()
    return got, pub_id


def main() -> int:
    expected, series_codes = build_expected()
    db, pub_id = load_db()

    # Compare on the full 4-tuple (field, value, series, is_standard).
    missing = expected - db            # authoritative-allowed but not in DB
    extra = db - expected              # in DB but not authoritative-allowed

    # Also compare ignoring is_standard, to separate "row missing" from
    # "STD flag differs".
    exp3 = {(f, v, s) for f, v, s, _ in expected}
    db3 = {(f, v, s) for f, v, s, _ in db}
    missing3 = exp3 - db3
    extra3 = db3 - exp3
    std_flag_diffs = (missing | extra) - {
        t for t in (missing | extra) if (t[0], t[1], t[2]) in (missing3 | extra3)
    }

    lines = []
    W = "=" * 92
    lines.append(f"{W}\r\nFYBROC SELECTIONS -> DB FULL AUDIT (all fields, all series)\r\n{W}\r\n\r\n")
    lines.append(f"Active publication: {pub_id}\r\n")
    lines.append(f"Series audited: {series_codes}\r\n\r\n")
    lines.append(f"Authoritative expected rows (X/STD, post V6 flange rule): {len(expected)}\r\n")
    lines.append(f"DB rows:                                                 {len(db)}\r\n\r\n")

    lines.append(f"--- MISSING: allowed by Rev0.3(+V6) but NOT in DB ({len(missing3)}) ---\r\n")
    for f, v, s in sorted(missing3):
        lines.append(f"    {s:6s} {f:26s} {v!r}\r\n")
    if not missing3:
        lines.append("    (none)\r\n")

    lines.append(f"\r\n--- EXTRA: in DB but NOT allowed by Rev0.3(+V6) ({len(extra3)}) ---\r\n")
    for f, v, s in sorted(extra3):
        lines.append(f"    {s:6s} {f:26s} {v!r}\r\n")
    if not extra3:
        lines.append("    (none)\r\n")

    lines.append(f"\r\n--- STD-flag mismatches (row present, IsStandard differs) ({len(std_flag_diffs)}) ---\r\n")
    for f, v, s, std in sorted(std_flag_diffs):
        lines.append(f"    {s:6s} {f:26s} {v!r} expected_is_standard={std}\r\n")
    if not std_flag_diffs:
        lines.append("    (none)\r\n")

    clean = not missing3 and not extra3 and not std_flag_diffs
    lines.append(f"\r\n{W}\r\nRESULT: {'CLEAN - DB matches Rev0.3 Selections + V6 flange authority exactly' if clean else 'DIVERGENCES FOUND (see above)'}\r\n{W}\r\n")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(lines), encoding="utf-8")

    # console summary
    print("".join(lines))
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())

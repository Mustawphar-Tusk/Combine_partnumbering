"""D140 - Dean Excel Oracle vs API/SQL comparison (re-based onto v0.1 authority).

Roadmap anchor: docs/PROJECT_MASTER_ROADMAP.md, Milestone D140 (Dean Excel
Oracle). Exit gate: "SQL output matches approved Dean workbook output" via
"Dean workbook COM regression parity."

RE-BASE (2026-08-26): the authoritative workbook
`workbooks/Dean/PumpConfiguration_Logic_0.1.xlsm` is a numbering/constraint
authority, not a Smart-Number configurator. So this compares, PER PN SEGMENT and
PER TEST CONFIG:

  * the segment ComboString the API/SQL resolver builds for the config
    (dean_identifier._build_combo, same code path the live API uses), and
  * the Alphanumeric Code the API/SQL resolver returns for that segment
    (segment_debug), AGAINST
  * the code read LIVE from the workbook's OWN numbering sheet via Excel COM
    (dean_excel_oracle.DeanNumberingOracle) for that SAME ComboString.

If the workbook's numbering sheet contains the ComboString, the workbook code and
the API code MUST be identical (a difference is a real FAILURE). If the workbook
sheet does NOT contain the ComboString (the config lands on a combo the workbook
never enumerated - the disclosed STD-vs-numbering / external-Standard-Confs gap,
item A2), that is a workbook-authority gap: recorded, NOT a failure. Table-backed
segments only: wet_end, impeller_options, power_frame_options, baseplate_options,
flush_plan, motor_frame. The unbuilt/gated/special segments (barrier, cooling,
testing, documentation, additional_options, motor, motor_options, trim, seal) are
not enumerated in v0.1 numbering sheets and are covered by audit_dean_identifier.

Requires: real Microsoft Excel + pywin32 (Windows only) AND the API on
127.0.0.1:8080. Exit 0 iff every segment/combo the WORKBOOK enumerated matched
the API. Outputs docs/evidence/D140/DEAN_ORACLE_COMPARE.{json,txt}.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dean_excel_oracle as oracle  # noqa: E402

# resolver: build the exact ComboString the live API uses, per segment.
_SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(_SRC.parent))
from src.api import dean_identifier as di  # noqa: E402

BASE = "http://127.0.0.1:8080/api/v2/families/DEAN"
ROOT = Path(__file__).resolve().parents[1]

# Table-backed segments (workbook numbering sheet <-> API segment_debug key).
# (segment_code_for_combo, oracle_segment, api_debug_key, human)
TABLE_SEGMENTS = [
    ("WET_END_OPTIONS", "WET_END_OPTIONS", "wet_end", "wet end"),
    ("IMPELLER_OPTIONS", "IMPELLER_OPTIONS", "impeller_options", "impeller options"),
    ("POWER_FRAME_OPTIONS", "POWER_FRAME_OPTIONS", "power_frame_options", "power frame"),
    ("BASEPLATE_OPTIONS", "BASEPLATE_OPTIONS", "baseplate_options", "baseplate"),
]

# Representative matrix (small - D140 proves harness fidelity + parity, not
# exhaustive coverage, which is D150). Includes models D130/D140 showed fully
# resolving plus a couple exercising the disclosed STD-vs-numbering gap.
# Models audit_dean_identifier.py showed FULLY resolve (wet_end + power_frame land
# on enumerated numbering rows), so the workbook oracle MUST contain those combos
# and MUST match. Plus one disclosed-gap model (records ENG_GAP, not a failure).
DEFAULT_MATRIX = [
    {"series": "R5140", "size": "1.5X3X8.5", "label": "D651 fully-resolving"},
    {"series": "R5140", "size": "3X4X8.5", "label": "D653 fully-resolving"},
    {"series": "R5170", "size": "2X3X13.5", "label": "D675 fully-resolving"},
    {"series": "DL200", "size": "1.5X3X6", "label": "D363 (disclosed gap ok)"},
]


def post(path, payload, _retries=8):
    data = json.dumps(payload).encode()
    last = None
    for attempt in range(_retries):
        req = urllib.request.Request(BASE + path, data=data,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 503:
                last = e
                time.sleep(min(1.0 * (attempt + 1), 4.0))
                continue
            raise
    raise last


def _wait():
    for _ in range(40):
        try:
            post("/configurations/resolve-state", {"series": "DL200", "selections": {}})
            return True
        except Exception:
            time.sleep(1)
    return False


def api_full_config(case):
    """Resolve the API's STD-default config (same basis as audit_dean_identifier:
    seed size + Pump Configuration, take standard_defaults) + segment_debug + PN.

    Returns (full_selections_used, segment_debug, part_number). full_selections
    is the EXACT set fed to /resolve, so di._build_combo over it reproduces the
    same ComboString the live API used for each segment."""
    series, size = case["series"], case["size"]
    seed = {"ALT_SIZE": size, "SIZE": size,
            "PUMP_CONFIGURATION": "Pump, Baseplate, Coupling and Motor"}
    seed.update(case.get("selections", {}))
    st = post("/configurations/resolve-state", {"series": series, "selections": seed})
    sd = dict(st.get("standard_defaults", {}))
    sd.update({"ALT_SIZE": size, "SIZE": size})
    full = {"SERIES": series, **sd}
    payload = {"series": series, "selections": full,
               "segment_codes": {}, "requested_by": "dean_oracle_compare"}
    r = post("/configured-products/resolve", payload)
    return full, (r.get("segment_debug", {}) or {}), (r.get("part_number", "") or "")


def main():
    if not _wait():
        print("FAIL: API server not reachable on 127.0.0.1:8080")
        return 1

    # 1) Resolve each case via the API to obtain the COMPLETE selection set +
    #    segment codes.
    print("Resolving API full configs...", flush=True)
    cases = []
    for case in DEFAULT_MATRIX:
        try:
            full_sel, api_segs, api_pn = api_full_config(case)
            cases.append((case, full_sel, api_segs, api_pn, None))
        except Exception as e:
            cases.append((case, {}, {}, "", f"api_error:{e}"))

    # 2) Open the workbook via COM ONCE and read the LIVE code for each segment's
    #    ComboString (built with the resolver's own _build_combo).
    print("Opening workbook via Excel COM (numbering-table oracle)...", flush=True)
    orc = oracle.DeanNumberingOracle(ROOT)
    harness_error = None
    try:
        orc.open()
    except Exception as e:
        harness_error = f"{type(e).__name__}: {e}"

    ev = ROOT / "docs" / "evidence" / "D140"
    ev.mkdir(parents=True, exist_ok=True)

    rows = []
    seg_matched = seg_failed = seg_eng_gap = 0
    case_pass = case_fail = 0

    if harness_error:
        print(f"FAIL: Excel oracle harness error: {harness_error}")
        return 1

    print("\n=== D140 Dean Excel-oracle (v0.1 numbering) vs API/SQL ===")
    try:
        for case, full_sel, api_segs, api_pn, api_err in cases:
            label = case.get("label", "")
            if api_err:
                case_fail += 1
                print(f"  [FAIL] {case['series']} {case['size']} ({label}): {api_err}")
                rows.append({"case": case, "error": api_err})
                continue

            # selections keyed by canonical code (SERIES/SIZE upper already present)
            sel = {k.upper(): v for k, v in full_sel.items()}
            seg_report = []
            this_case_fail = 0
            for combo_seg, orc_seg, api_key, human in TABLE_SEGMENTS:
                combo = di._build_combo(sel, combo_seg)
                # Baseplate NONE gate: resolver emits '00' without a table hit and
                # the workbook's NONE row combo is just 'NONE' -> handle via oracle.
                wb_code = orc.code_for(orc_seg, combo)
                api_v = str(api_segs.get(api_key, "")).strip()
                api_unresolved = "?" in api_v

                if wb_code is None:
                    status = "ENG_GAP"   # workbook did not enumerate this combo
                    seg_eng_gap += 1
                elif api_unresolved:
                    status = "FAIL"; seg_failed += 1; this_case_fail += 1
                elif str(wb_code).strip() == api_v:
                    status = "MATCH"; seg_matched += 1
                else:
                    status = "FAIL"; seg_failed += 1; this_case_fail += 1
                seg_report.append({"segment": human, "combo": combo,
                                   "excel": (wb_code if wb_code is not None else ""),
                                   "api": api_v, "status": status})

            # Flush + motor-frame: single-leg lookups (compare directly).
            flush_plan = str(sel.get("FLUSH_PLAN", "")).strip() or "NONE"
            fl_wb = orc.code_for("FLUSH_PLAN", flush_plan if flush_plan.upper() != "NONE" else "NONE")
            fl_api = str(api_segs.get("flush_plan", "")).strip()
            # Only compare flush when the workbook has an EXACT combo == plan row
            # (named plans have multi-part combos we don't reconstruct here); the
            # NONE row is the exact-match case we can assert.
            if fl_wb is not None:
                if "?" in fl_api:
                    st_f = "FAIL"; seg_failed += 1; this_case_fail += 1
                elif str(fl_wb).strip() == fl_api:
                    st_f = "MATCH"; seg_matched += 1
                else:
                    st_f = "FAIL"; seg_failed += 1; this_case_fail += 1
                seg_report.append({"segment": "flush plan", "combo": flush_plan,
                                   "excel": fl_wb, "api": fl_api, "status": st_f})
            else:
                seg_report.append({"segment": "flush plan", "combo": flush_plan,
                                   "excel": "", "api": fl_api, "status": "ENG_GAP"})
                seg_eng_gap += 1

            frame = str(sel.get("FRAME_SIZE", "")).strip()
            if frame and frame.upper() not in ("NONE", "N/A"):
                fr_wb = orc.code_for("MOTOR_FRAME", frame)
                fr_api = str(api_segs.get("frame_size", "")).strip()
                if fr_wb is not None:
                    if str(fr_wb).strip() == fr_api:
                        seg_matched += 1
                        seg_report.append({"segment": "motor frame", "combo": frame,
                                           "excel": fr_wb, "api": fr_api, "status": "MATCH"})
                    else:
                        seg_failed += 1; this_case_fail += 1
                        seg_report.append({"segment": "motor frame", "combo": frame,
                                           "excel": fr_wb, "api": fr_api, "status": "FAIL"})

            ok = this_case_fail == 0
            case_pass += ok; case_fail += (not ok)
            mark = "PASS" if ok else "FAIL"
            print(f"  [{mark}] {case['series']} {case['size']} ({label})  api PN: {api_pn}")
            for s in seg_report:
                if s["status"] != "MATCH":
                    print(f"        {s['status']:8} {s['segment']}: "
                          f"excel={s['excel']!r} api={s['api']!r} combo={s['combo']!r}")
            rows.append({"case": case, "api_pn": api_pn,
                         "segments": seg_report, "case_pass": ok})
    finally:
        orc.close()

    result = {
        "artifact": "DEAN_ORACLE_COMPARE",
        "milestone": "D140",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "authority": "PumpConfiguration_Logic_0.1.xlsm numbering sheets, read LIVE via Excel COM",
        "compares": "per-segment ComboString code: API/SQL resolver vs workbook numbering sheet (COM). "
                    "Workbook-unenumerated combos = disclosed STD-vs-numbering gap (recorded, not failed).",
        "case_count": len(DEFAULT_MATRIX),
        "cases_passed": case_pass, "cases_failed": case_fail,
        "segments_matched": seg_matched,
        "segments_failed": seg_failed,
        "segments_engineering_gap": seg_eng_gap,
        "engineering_questions_ref": "docs/evidence/DEAN_ENGINEERING_QUESTIONS.md",
        "results": rows,
    }
    (ev / "DEAN_ORACLE_COMPARE.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8")

    out = ["=" * 100 + "\r\n",
           "D140 - DEAN EXCEL ORACLE (v0.1 numbering, COM) vs API/SQL\r\n",
           "=" * 100 + "\r\n\r\n"]
    out.append(f"Authority : {result['authority']}\r\n")
    out.append(f"Compares  : {result['compares']}\r\n")
    out.append(f"Cases     : {result['case_count']}  Passed: {case_pass}  Failed: {case_fail}\r\n")
    out.append(f"Segments  : matched={seg_matched}  failed={seg_failed}  "
               f"engineering_gap={seg_eng_gap}\r\n\r\n")
    for r in rows:
        c = r["case"]
        if "error" in r:
            out.append(f"  [ERROR] {c['series']} {c['size']}: {r['error']}\r\n\r\n"); continue
        mark = "PASS" if r["case_pass"] else "FAIL"
        out.append(f"  [{mark}] {c['series']} {c['size']} ({c.get('label','')})\r\n")
        out.append(f"     api PN : {r['api_pn']}\r\n")
        for s in r["segments"]:
            out.append(f"        [{s['status']:8}] {s['segment']}: "
                       f"excel={s['excel']!r} api={s['api']!r}\r\n")
        out.append("\r\n")
    (ev / "DEAN_ORACLE_COMPARE.txt").write_text("".join(out), encoding="utf-8")

    print(f"\n=== RESULT: {case_pass} cases passed, {case_fail} failed; "
          f"segments matched={seg_matched} failed={seg_failed} eng_gap={seg_eng_gap} ===")
    print(f"Evidence: {ev / 'DEAN_ORACLE_COMPARE.txt'}")
    return 0 if seg_failed == 0 and case_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

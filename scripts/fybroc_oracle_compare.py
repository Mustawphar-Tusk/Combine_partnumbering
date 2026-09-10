"""F160 - Fybroc Excel-Oracle vs API/SQL comparison.

Roadmap anchor: docs/PROJECT_MASTER_ROADMAP.md, Milestone F160.

Runs the Excel oracle (scripts/fybroc_excel_oracle.py) AND the API/SQL resolve
endpoint over the SAME representative matrix, then compares the leading IDENTITY:
  - leading Part-Number segment  (F + series + size + material + trim)
  - identity segment codes         (series_code, size_code, material_code, trim_code)

This is decision (b): PN + segment codes. The leading identity is what BOTH
systems derive independently from the same core selection (series/flange/size/
material/trim), so it is a genuine cross-check between the approved workbook and
our SQL-authoritative identity (F150). Downstream option/seal/motor segments
depend on option selections that differ between workbook defaults and the API's
STD walk; exhaustive lock-step comparison of those is F170.

SAFETY: the Excel side only ever touches a disposable copy (see the oracle
module). This script does not modify any workbook or database state beyond the
normal resolve-endpoint persistence (idempotent reuse).

Requirements:
  - Real Microsoft Excel + pywin32 (win32com)  [Windows only]
  - API server on 127.0.0.1:8080  (start separately, or via run_all_fybroc_audits)

Exit code 0 iff every case computed in Excel AND matched the API leading identity.
Outputs docs/evidence/F160/FYBROC_ORACLE_COMPARE.{json,txt}.
"""
from __future__ import annotations
import json, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fybroc_excel_oracle as oracle  # noqa: E402

BASE = "http://127.0.0.1:8080/api/v2/families/FYBROC"
ROOT = Path(__file__).resolve().parents[1]

# Map the oracle field names to the API segment_debug field names.
IDENTITY_KEYS = [
    ("series", "series_code"),
    ("size", "size_code"),
    ("material", "material_code"),
    ("trim", "trim_code"),
]


def post(path, payload, _retries=8):
    """POST with a bounded retry on transient 503 database_unavailable.

    The resolve endpoint opens a fresh pyodbc connection per call; the very
    first connection handshake of a run can transiently fail (ODBC refuses under
    contention, e.g. while Excel COM is starting), which the API maps to
    HTTP 503 'database_unavailable'. That is an environmental transient, not an
    identity mismatch, so we retry with backoff to keep the harness repeatable.
    A non-503 HTTP error (e.g. a real 4xx) is raised immediately."""
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
            post("/configurations/evaluate", {"series": "1500", "selections": {}}); return True
        except Exception:
            time.sleep(1)
    return False


def build_full_config(series, core):
    """Walk the hierarchy picking STD/first option, seeding the core identity
    selections (SIZE/PUMP_MATERIAL/IMPELLER_TRIM/FLANGE_TYPE) so the API resolves
    the SAME identity the Excel oracle was fed."""
    sel = dict(core)
    for _ in range(200):
        d = post("/configurations/evaluate", {"series": series, "selections": sel})
        cur = d.get("current_field")
        if cur is None:
            break
        if cur in sel:  # already seeded (core identity) - keep it
            continue
        opts = d["allowable_options"].get(cur, [])
        std = d.get("standard_defaults", {}).get(cur)
        pick = std if std in opts else (opts[0] if opts else None)
        if pick is None:
            break
        sel[cur] = pick
    return sel


def api_identity(series, flange, size, material, trim):
    """Resolve via the API and return (leading, segment_codes_dict).

    NOTE: the API resolves size_code from ALT_SIZE (the real hierarchy field;
    SIZE is a legacy alias) - see src/api/v2_routes.py line ~925. We therefore
    seed ALT_SIZE with the same size value the Excel oracle was fed, so both
    systems resolve the SAME size. (SIZE is also kept for pricing lookups.)"""
    core = {"SERIES": series, "FLANGE_TYPE": flange, "SIZE": size, "ALT_SIZE": size,
            "PUMP_MATERIAL": material, "IMPELLER_TRIM": trim}
    sel = build_full_config(series, core)
    payload = {"series": series, "selections": {"SERIES": series, **sel},
               "segment_codes": {}, "requested_by": "fybroc_oracle_compare"}
    r = post("/configured-products/resolve", payload)
    seg = r.get("segment_debug", {})
    part_number = r.get("part_number", "")
    leading = part_number.split("-", 1)[0] if part_number else ""
    codes = {
        "series_code": str(seg.get("series_code", "")),
        "size_code": str(seg.get("size_code", "")),
        "material_code": str(seg.get("material_code", "")),
        "trim_code": str(seg.get("trim_code", "")),
    }
    return leading, codes, part_number


def main():
    if not _wait():
        print("FAIL: API server not reachable on 127.0.0.1:8080")
        return 1

    # Warm up the resolve DB-connection path BEFORE the long Excel session, so
    # the first real resolve afterward doesn't hit a cold/stale connection.
    try:
        api_identity("1500", "ANSI", "1x1.5x6", "VR-1", "6.000")
    except Exception:
        pass

    print("Running Excel oracle over representative matrix...")
    ex_results = oracle.run_oracle(ROOT, oracle.DEFAULT_MATRIX)

    ev = ROOT / "docs" / "evidence" / "F160"
    ev.mkdir(parents=True, exist_ok=True)

    rows = []
    passed = failed = 0
    print("\n=== F160 Excel-oracle vs API/SQL identity comparison ===")
    for i, (series, flange, size, material, trim) in enumerate(oracle.DEFAULT_MATRIX):
        ex = ex_results[i] if i < len(ex_results) and "error" not in ex_results[i] else None
        if ex is None or not ex.get("computed"):
            failed += 1
            print(f"  [FAIL] {series}/{flange}/{size}/{material}/{trim}: Excel oracle did not compute")
            rows.append({"series": series, "flange": flange, "size": size,
                         "material": material, "trim": trim,
                         "match": False, "reason": "excel_not_computed",
                         "excel": ex})
            continue

        ex_seg = ex["excel_segments"]
        ex_leading = ex["excel_leading"]
        try:
            api_leading, api_codes, api_pn = api_identity(series, flange, size, material, trim)
        except urllib.error.HTTPError as e:
            failed += 1
            print(f"  [FAIL] {series}/{flange}/{size}/{material}/{trim}: API HTTP {e.code}")
            rows.append({"series": series, "flange": flange, "size": size,
                         "material": material, "trim": trim,
                         "match": False, "reason": f"api_http_{e.code}"})
            continue

        # Compare identity segment codes field by field + leading prefix.
        seg_mismatch = {}
        for ex_key, api_key in IDENTITY_KEYS:
            ev_v = str(ex_seg.get(ex_key, ""))
            av_v = str(api_codes.get(api_key, ""))
            if ev_v != av_v:
                seg_mismatch[api_key] = {"excel": ev_v, "api": av_v}
        leading_match = ex_leading == api_leading
        match = leading_match and not seg_mismatch

        if match:
            passed += 1
            print(f"  [PASS] {series}/{flange}/{size}/{material}/{trim}: {ex_leading} (Excel) == {api_leading} (API)")
        else:
            failed += 1
            print(f"  [FAIL] {series}/{flange}/{size}/{material}/{trim}: "
                  f"Excel leading={ex_leading} API leading={api_leading} mismatch={seg_mismatch}")

        rows.append({
            "series": series, "flange": flange, "size": size,
            "material": material, "trim": trim,
            "orientation": ex["orientation"],
            "excel_leading": ex_leading, "api_leading": api_leading,
            "excel_compact_pn": ex["excel_compact_pn"], "api_part_number": api_pn,
            "excel_identity": {k: ex_seg.get(k) for k, _ in IDENTITY_KEYS},
            "api_identity": api_codes,
            "leading_match": leading_match,
            "segment_mismatch": seg_mismatch,
            "match": match,
        })

    result = {
        "artifact": "FYBROC_ORACLE_COMPARE",
        "milestone": "F160",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "compares": "PN leading identity + identity segment codes (Excel oracle vs API/SQL)",
        "test_count": len(oracle.DEFAULT_MATRIX),
        "passed": passed, "failed": failed,
        "results": rows,
    }
    (ev / "FYBROC_ORACLE_COMPARE.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8")

    out = ["=" * 100 + "\r\n", "F160 - EXCEL ORACLE vs API/SQL IDENTITY COMPARISON\r\n", "=" * 100 + "\r\n\r\n"]
    out.append(f"Compares : {result['compares']}\r\n")
    out.append(f"Tests    : {result['test_count']}   Passed: {passed}   Failed: {failed}\r\n\r\n")
    for r in rows:
        s = "PASS" if r.get("match") else "FAIL"
        out.append(f"  [{s}] {r['series']}/{r['flange']}/{r['size']}/{r['material']}/{r['trim']}\r\n")
        out.append(f"     Excel leading: {r.get('excel_leading')}   API leading: {r.get('api_leading')}\r\n")
        out.append(f"     Excel PN: {r.get('excel_compact_pn')}   API PN: {r.get('api_part_number')}\r\n")
        if r.get("segment_mismatch"):
            out.append(f"     MISMATCH: {r['segment_mismatch']}\r\n")
        out.append("\r\n")
    (ev / "FYBROC_ORACLE_COMPARE.txt").write_text("".join(out), encoding="utf-8")

    print(f"\n=== RESULT: {passed} passed, {failed} failed ===")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

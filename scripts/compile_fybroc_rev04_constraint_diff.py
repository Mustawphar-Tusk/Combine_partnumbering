"""Rev0.4 vs Rev0.3 FYBROC constraint/selection DIFF (READ-ONLY, no DB, no writes
except an evidence report).

Reuses the authoritative Rev0.3 compiler functions (compile_fybroc_constraint_model)
against BOTH workbooks and reports, per structure, exactly where Rev0.4 differs from
Rev0.3:

  1. Feasible-Constraint tables (ConstraintTableN): tables added/removed; and per
     shared table, allow/deny rows added/removed/changed (keyed on the option-value
     tuple, comparing the Allowed? verdict).
  2. Constraint Index (named entries: Option1/2/3/TableName/Description).
  3. Combination Matrix (per target field: list1/list2, per-series verdict,
     combination verdict, answer ref, applicable sizes).
  4. Selections (option domains): (field_code, answer, series, X/STD) set diff,
     applying the SAME transform the runtime loader/audit uses (UPPER field, V6
     flange rule) so the diff reflects what would actually change in the DB.

Output: docs/evidence/REV04_CONSTRAINTS/REV04_vs_REV03_CONSTRAINT_DIFF.{md,json}

Nothing is loaded into SQL. This is the "see where they differ" step BEFORE any
supersession decision.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.compile_fybroc_constraint_model as cm  # noqa: E402
from src.compiler.workbook_types import norm_series  # noqa: E402

R3 = ROOT / "workbooks" / "Fybroc" / "Fybroc Configuration Rev0.3.xlsx"
R4 = ROOT / "workbooks" / "Fybroc" / "Fybroc Configuration Rev0.4.xlsx"
OUT_DIR = ROOT / "docs" / "evidence" / "REV04_CONSTRAINTS"

# Selections transform (mirror audit_selections_vs_db.py / load_all_series.py)
V6_DIN_JIS_SERIES = {"1500", "1530", "1600", "1630"}
NON_ANSI_FLANGE_ANSWERS = {"din/iso flange", "jis flange"}


# ---------------------------------------------------------------------------
# Extraction helpers (read-only)
# ---------------------------------------------------------------------------
def extract_constraints(path: Path) -> dict:
    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    matrix = cm.compile_combination_matrix(wb["Constraints"])
    index = cm.compile_constraint_index(wb["Constraint Index"])
    feasible = cm.compile_feasible_constraints(wb["Feasible Constraints"])
    wb.close()
    return {"matrix": matrix, "index": index, "feasible": feasible}


def extract_selections(path: Path) -> set:
    """(field_code, answer_lower, series, is_standard) after V6 flange rule."""
    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    ws = wb["Selections"]
    series_codes = []
    for c in range(4, 14):
        s = norm_series(ws.cell(row=1, column=c).value)
        if s:
            series_codes.append(s)
    out = set()
    for r in range(2, ws.max_row + 1):
        q = ws.cell(row=r, column=2).value
        a = ws.cell(row=r, column=3).value
        if not q or not a:
            continue
        field_code = str(q).strip().upper().replace(" ", "_").replace("-", "_")
        answer = str(a).strip()
        for i, series in enumerate(series_codes):
            marker = ws.cell(row=r, column=4 + i).value
            mu = (str(marker).strip().upper() if marker is not None else "")
            if mu in ("X", "STD"):
                if (field_code == "FLANGE_TYPE"
                        and answer.lower() in NON_ANSI_FLANGE_ANSWERS
                        and series not in V6_DIN_JIS_SERIES):
                    continue
                out.add((field_code, answer.lower(), series, 1 if mu == "STD" else 0))
    wb.close()
    return out, series_codes


# ---------------------------------------------------------------------------
# Diff helpers
# ---------------------------------------------------------------------------
def _table_rowkey(headers, row):
    """Key a constraint-table row by its option-value tuple (all headers except
    the 'Allowed?' column), and return (key_tuple, allowed_verdict)."""
    allowed_idx = next(
        (i for i, h in enumerate(headers)
         if str(h).strip().lower().rstrip("?") == "allowed"),
        len(headers) - 1,
    )
    vals = [row.get(h) for h in headers]
    key = tuple(("" if vals[i] is None else str(vals[i]).strip())
                for i in range(len(headers)) if i != allowed_idx)
    verdict = ("" if vals[allowed_idx] is None else str(vals[allowed_idx]).strip())
    return key, verdict


def diff_feasible(f3: dict, f4: dict) -> dict:
    names3, names4 = set(f3), set(f4)
    report = {
        "tables_added": sorted(names4 - names3),
        "tables_removed": sorted(names3 - names4),
        "tables_changed": {},
        "tables_identical": [],
    }
    for name in sorted(names3 & names4):
        t3, t4 = f3[name], f4[name]
        h3, h4 = t3["headers"], t4["headers"]
        m3 = {}
        for row in t3["rows"]:
            k, v = _table_rowkey(h3, row)
            m3[k] = v
        m4 = {}
        for row in t4["rows"]:
            k, v = _table_rowkey(h4, row)
            m4[k] = v
        added = sorted(set(m4) - set(m3))
        removed = sorted(set(m3) - set(m4))
        changed = sorted(k for k in (set(m3) & set(m4)) if m3[k] != m4[k])
        header_changed = (h3 != h4)
        if not added and not removed and not changed and not header_changed:
            report["tables_identical"].append(name)
        else:
            report["tables_changed"][name] = {
                "headers_rev03": h3, "headers_rev04": h4,
                "header_changed": header_changed,
                "rows_rev03": t3["row_count"], "rows_rev04": t4["row_count"],
                "added": [{"key": list(k), "allowed": m4[k]} for k in added],
                "removed": [{"key": list(k), "allowed": m3[k]} for k in removed],
                "verdict_changed": [
                    {"key": list(k), "rev03": m3[k], "rev04": m4[k]} for k in changed
                ],
            }
    return report


def diff_index(i3: list, i4: list) -> dict:
    def key(e):
        return e.get("table_name") or f"(noTable) {e.get('option1')}|{e.get('option2')}|{e.get('option3')}"
    m3 = {key(e): e for e in i3}
    m4 = {key(e): e for e in i4}
    changed = {}
    for k in sorted(set(m3) & set(m4)):
        a, b = m3[k], m4[k]
        fields = {}
        for f in ("option1", "option2", "option3", "description", "series_applicability"):
            if (a.get(f) or "") != (b.get(f) or ""):
                fields[f] = {"rev03": a.get(f), "rev04": b.get(f)}
        if fields:
            changed[k] = fields
    return {
        "added": sorted(set(m4) - set(m3)),
        "removed": sorted(set(m3) - set(m4)),
        "changed": changed,
    }


def diff_matrix(m3: dict, m4: dict) -> dict:
    def by_field(mtx):
        return {row["field"]: row for row in mtx["rows"]}
    r3, r4 = by_field(m3), by_field(m4)
    changed = {}
    for f in sorted(set(r3) & set(r4)):
        a, b = r3[f], r4[f]
        d = {}
        for k in ("list1", "list2", "combination_verdict", "answer_ref"):
            if (a.get(k) or "") != (b.get(k) or ""):
                d[k] = {"rev03": a.get(k), "rev04": b.get(k)}
        if a.get("series_verdicts") != b.get("series_verdicts"):
            d["series_verdicts"] = {"rev03": a.get("series_verdicts"),
                                    "rev04": b.get("series_verdicts")}
        if sorted(a.get("applicable_sizes") or []) != sorted(b.get("applicable_sizes") or []):
            s3 = set(a.get("applicable_sizes") or [])
            s4 = set(b.get("applicable_sizes") or [])
            d["applicable_sizes"] = {"added": sorted(s4 - s3), "removed": sorted(s3 - s4)}
        if d:
            changed[f] = d
    return {
        "fields_added": sorted(set(r4) - set(r3)),
        "fields_removed": sorted(set(r3) - set(r4)),
        "series_codes_rev03": m3.get("series_codes"),
        "series_codes_rev04": m4.get("series_codes"),
        "changed": changed,
    }


def diff_selections(s3: set, s4: set) -> dict:
    added = sorted(s4 - s3)
    removed = sorted(s3 - s4)
    # split "flag-only" (same field/answer/series present, X<->STD flip) from
    # true add/remove of an option
    key3 = {(f, a, s): std for (f, a, s, std) in s3}
    key4 = {(f, a, s): std for (f, a, s, std) in s4}
    flag_flips = sorted(
        (f, a, s, key3[(f, a, s)], key4[(f, a, s)])
        for (f, a, s) in (set(key3) & set(key4)) if key3[(f, a, s)] != key4[(f, a, s)]
    )
    true_added = sorted(k for k in (set(key4) - set(key3)))
    true_removed = sorted(k for k in (set(key3) - set(key4)))
    return {
        "true_added": [list(k) for k in true_added],
        "true_removed": [list(k) for k in true_removed],
        "std_flag_flips": [list(x) for x in flag_flips],
        "count_rev03": len(s3), "count_rev04": len(s4),
    }


# ---------------------------------------------------------------------------
def main() -> int:
    c3 = extract_constraints(R3)
    c4 = extract_constraints(R4)
    sel3, series3 = extract_selections(R3)
    sel4, series4 = extract_selections(R4)

    feas = diff_feasible(c3["feasible"], c4["feasible"])
    idx = diff_index(c3["index"], c4["index"])
    mtx = diff_matrix(c3["matrix"], c4["matrix"])
    sel = diff_selections(sel3, sel4)

    result = {
        "artifact": "REV04_vs_REV03_CONSTRAINT_DIFF",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "rev03_workbook": R3.name,
        "rev04_workbook": R4.name,
        "feasible": feas,
        "constraint_index": idx,
        "combination_matrix": mtx,
        "selections": sel,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "REV04_vs_REV03_CONSTRAINT_DIFF.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    # ---- markdown report ----
    L = []
    L.append("# Rev0.4 vs Rev0.3 — FYBROC constraint & selection diff\n")
    L.append(f"_Generated {result['generated_utc']}_  ")
    L.append(f"Rev0.3: `{R3.name}`  Rev0.4: `{R4.name}`\n")
    L.append("Read-only extraction via the authoritative Rev0.3 compiler functions "
             "run against both workbooks. Nothing was loaded to SQL.\n")

    L.append("\n## 1. Feasible Constraint tables\n")
    L.append(f"- tables only in Rev0.4 (added): {feas['tables_added'] or '—'}\n")
    L.append(f"- tables only in Rev0.3 (removed): {feas['tables_removed'] or '—'}\n")
    L.append(f"- identical tables: {len(feas['tables_identical'])} "
             f"({', '.join(feas['tables_identical']) or '—'})\n")
    L.append(f"- CHANGED tables: {len(feas['tables_changed'])}\n")
    for name, ch in feas["tables_changed"].items():
        L.append(f"\n### {name}  (rows {ch['rows_rev03']} → {ch['rows_rev04']})\n")
        if ch["header_changed"]:
            L.append(f"- headers changed: {ch['headers_rev03']} → {ch['headers_rev04']}\n")
        if ch["added"]:
            L.append(f"- **added rows ({len(ch['added'])})**:\n")
            for a in ch["added"]:
                L.append(f"    - `{a['key']}` → {a['allowed']}\n")
        if ch["removed"]:
            L.append(f"- **removed rows ({len(ch['removed'])})**:\n")
            for a in ch["removed"]:
                L.append(f"    - `{a['key']}` → {a['allowed']}\n")
        if ch["verdict_changed"]:
            L.append(f"- **verdict changed ({len(ch['verdict_changed'])})**:\n")
            for a in ch["verdict_changed"]:
                L.append(f"    - `{a['key']}`: {a['rev03']} → {a['rev04']}\n")

    L.append("\n## 2. Constraint Index\n")
    L.append(f"- added: {idx['added'] or '—'}\n")
    L.append(f"- removed: {idx['removed'] or '—'}\n")
    L.append(f"- changed: {len(idx['changed'])}\n")
    for k, fields in idx["changed"].items():
        L.append(f"    - {k}: {json.dumps(fields, ensure_ascii=False)}\n")

    L.append("\n## 3. Combination Matrix\n")
    L.append(f"- series codes Rev0.3: {mtx['series_codes_rev03']}\n")
    L.append(f"- series codes Rev0.4: {mtx['series_codes_rev04']}\n")
    L.append(f"- fields added: {mtx['fields_added'] or '—'}\n")
    L.append(f"- fields removed: {mtx['fields_removed'] or '—'}\n")
    L.append(f"- fields changed: {len(mtx['changed'])}\n")
    for f, d in mtx["changed"].items():
        L.append(f"    - **{f}**: {json.dumps(d, ensure_ascii=False)}\n")

    L.append("\n## 4. Selections (option domains, post V6 flange rule)\n")
    L.append(f"- Rev0.3 rows: {sel['count_rev03']}   Rev0.4 rows: {sel['count_rev04']}\n")
    L.append(f"- options ADDED by Rev0.4 ({len(sel['true_added'])}):\n")
    for k in sel["true_added"]:
        L.append(f"    - {k[2]:6}  {k[0]:26}  {k[1]!r}\n")
    L.append(f"- options REMOVED by Rev0.4 ({len(sel['true_removed'])}):\n")
    for k in sel["true_removed"]:
        L.append(f"    - {k[2]:6}  {k[0]:26}  {k[1]!r}\n")
    L.append(f"- STD/X flag flips ({len(sel['std_flag_flips'])}):\n")
    for x in sel["std_flag_flips"]:
        L.append(f"    - {x[2]:6}  {x[0]:26}  {x[1]!r}  is_standard {x[3]} → {x[4]}\n")

    (OUT_DIR / "REV04_vs_REV03_CONSTRAINT_DIFF.md").write_text("".join(L), encoding="utf-8")

    # ---- console summary ----
    print("=" * 90)
    print("REV0.4 vs REV0.3 FYBROC CONSTRAINT/SELECTION DIFF")
    print("=" * 90)
    print(f"Feasible tables: added={feas['tables_added']} removed={feas['tables_removed']} "
          f"changed={list(feas['tables_changed'])} identical={len(feas['tables_identical'])}")
    for name, ch in feas["tables_changed"].items():
        print(f"  {name}: rows {ch['rows_rev03']}->{ch['rows_rev04']}  "
              f"+{len(ch['added'])} -{len(ch['removed'])} ~{len(ch['verdict_changed'])}"
              f"{'  HEADERS CHANGED' if ch['header_changed'] else ''}")
    print(f"Constraint Index: added={idx['added']} removed={idx['removed']} "
          f"changed={list(idx['changed'])}")
    print(f"Combination Matrix: fields_added={mtx['fields_added']} "
          f"fields_removed={mtx['fields_removed']} changed={list(mtx['changed'])}")
    print(f"  series Rev0.3={mtx['series_codes_rev03']}")
    print(f"  series Rev0.4={mtx['series_codes_rev04']}")
    print(f"Selections: rev03={sel['count_rev03']} rev04={sel['count_rev04']}  "
          f"true_added={len(sel['true_added'])} true_removed={len(sel['true_removed'])} "
          f"std_flips={len(sel['std_flag_flips'])}")
    print(f"\nEvidence: {OUT_DIR / 'REV04_vs_REV03_CONSTRAINT_DIFF.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

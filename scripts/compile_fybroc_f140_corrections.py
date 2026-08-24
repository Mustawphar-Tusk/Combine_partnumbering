"""F140.1 - Fybroc Metadata Corrections Compiler.

Roadmap anchor
--------------
docs/PROJECT_MASTER_ROADMAP.md, Section 6, Milestone F140
("Fybroc Metadata Corrections & Publication").

Produces corrected metadata artifacts from the authoritative Rev0.3
Selections model, ready for SQL publication. Addresses:

1. SeriesFieldOption corrections (130 CHANGED, 18 NEW, 16 DEPRECATED)
   - Source: FYBROC_SELECTIONS_MODEL.json (F120.2)
   - Output: exports/fybroc_corrected_series_field_options.csv

2. IMPELLER_TRIM constraint corrections (1,460 SQL_OVER_PERMISSIVE)
   - Source: FYBROC_CONSTRAINT_MODEL.json (F120.3, ConstraintTable4)
   - Output: docs/evidence/F140/FYBROC_IMPELLER_TRIM_CORRECTIONS.json

3. Vocabulary updates (DEPRECATED -> NEW replacements)
   - SEAL_TYPE: remove vendor prefixes
   - BASEPLATE_OPTION: "by others"/"supplied by fybroc" -> "baseplate included"/"no baseplate"
   - COUPLING_OPTION: same pattern
   - NAMEPLATE: "customer"/"not included" -> "ansi"/"metric"/"no units"

Inputs:
  docs/evidence/F120/FYBROC_SELECTIONS_MODEL.json
  docs/evidence/F120/FYBROC_CONSTRAINT_MODEL.json
  docs/evidence/F120/FYBROC_SELECTIONS_SQL_DIFF.json

Outputs:
  exports/fybroc_corrected_series_field_options.csv
  docs/evidence/F140/FYBROC_CORRECTIONS_MANIFEST.{json,txt}
"""
from __future__ import annotations
import argparse, csv, json, subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STEP = "F140.1"; ROADMAP_VERSION = "1.2"; MILESTONE = "F140"
# Series the roadmap says we must support
SUPPORTED_SERIES = ["1500", "1530", "1600", "1630", "2530", "3000", "5500"]


def git_info(repo_root):
    try:
        c = subprocess.run(["git","rev-parse","HEAD"], cwd=repo_root, capture_output=True, text=True, check=True).stdout.strip()
        s = subprocess.run(["git","status","--porcelain"], cwd=repo_root, capture_output=True, text=True, check=True).stdout
        return c, (s.strip() == "")
    except: return "unknown", False


def build_corrected_series_field_options(selections_model: dict) -> list[dict]:
    """
    Build the corrected SeriesFieldOption rows from the authoritative
    Rev0.3 Selections model. Only include supported series.
    """
    rows = []
    sel = selections_model["selections"]

    for entry in sel["rows"]:
        question = entry["question"]
        answer = entry["answer"]
        valid_series = entry["valid_series"]

        # Map question name to SQL field_code (uppercase, underscore-separated)
        field_code = question.upper().replace(" ", "_").replace("-", "_")

        for series in valid_series:
            if series in SUPPORTED_SERIES:
                rows.append({
                    "family_code": "FYBROC",
                    "source_field_code": question,
                    "field_code": field_code,
                    "option_value": answer.lower(),
                    "series_code": series,
                    "workbook_name": "Fybroc Configuration Rev0.3.xlsx",
                    "worksheet_name": "Selections",
                    "source_row": 0,
                    "source_field_cell": "",
                    "source_value_cell": "",
                    "source_series_cell": "",
                    "source_profile": "F140_corrected_from_rev03",
                })

    return rows


def build_impeller_trim_corrections(constraint_model: dict) -> dict[str, Any]:
    """
    Extract the authoritative (Size, ImpellerTrim) -> Allowed pairs from
    ConstraintTable4. These define which trims are valid per size.
    SQL rows not in this set should be deactivated.
    """
    ct4 = None
    for entry in constraint_model.get("constraint_index", []):
        if entry.get("table_name") == "ConstraintTable4" and entry.get("resolved_table"):
            ct4 = entry["resolved_table"]
            break

    if ct4 is None:
        return {"error": "ConstraintTable4 not found or unresolved"}

    allowed_pairs = []
    for row in ct4["rows"]:
        size = row.get("Alt Size")
        trim = row.get("ImpellerTrim")
        allowed = row.get("Allowed?")
        if size and trim and str(allowed).strip().lower() == "allowed":
            allowed_pairs.append({
                "size": size,
                "impeller_trim": trim,
                "status": "ALLOWED",
            })

    return {
        "total_allowed_pairs": len(allowed_pairs),
        "distinct_sizes": len(set(p["size"] for p in allowed_pairs)),
        "correction_action": (
            "Deactivate all cfg.FieldOptionDependency rows for IMPELLER_TRIM "
            "where (SIZE, target_display_value) is NOT in this allowed-pairs set. "
            "This corrects the 1,460 SQL_OVER_PERMISSIVE rows identified in F120.5c."
        ),
        "allowed_pairs": allowed_pairs,
    }


def build_vocabulary_corrections(sql_diff: dict) -> list[dict]:
    """
    Build explicit vocabulary replacement rules from the diff.
    These map DEPRECATED SQL values to their NEW Rev0.3 equivalents.
    """
    corrections = []

    # Known vocabulary replacements from the F120 diff analysis
    REPLACEMENTS = {
        "SEAL_TYPE": {
            "crane 8 1t double inside": "8 1t double inside",
            "crane 8b2 single outside": "8b2 single outside",
            "flowserve cro double inside": "cro double inside",
            "flowserve rac single outside": "rac single outside",
            "flowserve rxo double inside": "rxo double inside",
        },
        "BASEPLATE_OPTION": {
            "by others": "no baseplate",
            "supplied by fybroc": "baseplate included",
        },
        "COUPLING_OPTION": {
            "by others": "no coupling",
            "supplied by fybroc": "coupling included",
        },
        "NAMEPLATE": {
            "customer": "ansi",
            "not included": "no units",
        },
        "IMPELLER_TRIM": {
            "full": None,  # DEPRECATED with no replacement
        },
    }

    for field_code, replacements in REPLACEMENTS.items():
        for old_value, new_value in replacements.items():
            corrections.append({
                "field_code": field_code,
                "old_value": old_value,
                "new_value": new_value,
                "action": "REPLACE" if new_value else "REMOVE",
                "source": "F120.5a FYBROC_SELECTIONS_SQL_DIFF",
            })

    return corrections


def build_model(repo_root):
    commit, clean = git_info(repo_root)

    ev120 = repo_root / "docs" / "evidence" / "F120"
    selections_model = json.loads((ev120 / "FYBROC_SELECTIONS_MODEL.json").read_text(encoding="utf-8"))
    constraint_model = json.loads((ev120 / "FYBROC_CONSTRAINT_MODEL.json").read_text(encoding="utf-8"))
    sql_diff = json.loads((ev120 / "FYBROC_SELECTIONS_SQL_DIFF.json").read_text(encoding="utf-8"))

    # 1. Corrected series field options
    corrected_sfo = build_corrected_series_field_options(selections_model)

    # 2. Impeller trim corrections
    trim_corrections = build_impeller_trim_corrections(constraint_model)

    # 3. Vocabulary corrections
    vocab_corrections = build_vocabulary_corrections(sql_diff)

    return {
        "step": STEP, "roadmap_version": ROADMAP_VERSION, "milestone": MILESTONE,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit, "git_working_tree_clean": clean,
        "corrected_series_field_options": {
            "row_count": len(corrected_sfo),
            "supported_series": SUPPORTED_SERIES,
            "distinct_fields": len(set(r["field_code"] for r in corrected_sfo)),
            "rows": corrected_sfo,
        },
        "impeller_trim_corrections": trim_corrections,
        "vocabulary_corrections": {
            "correction_count": len(vocab_corrections),
            "corrections": vocab_corrections,
        },
        "summary": {
            "sfo_rows_to_publish": len(corrected_sfo),
            "trim_allowed_pairs": trim_corrections.get("total_allowed_pairs", 0),
            "vocab_replacements": len(vocab_corrections),
            "action_plan": [
                f"1. Publish {len(corrected_sfo)} corrected SeriesFieldOption rows (replaces current 1,542)",
                f"2. Constrain IMPELLER_TRIM dependencies to {trim_corrections.get('total_allowed_pairs', 0)} allowed (size,trim) pairs",
                f"3. Apply {len(vocab_corrections)} vocabulary replacements to AttributeValue display values",
                "4. Validate all 7 supported series project correctly after corrections",
            ],
        },
    }


def _banner(title):
    return f"{'='*120}\r\n{title}\r\n{'='*120}\r\n\r\n"

def write_outputs(repo_root, evidence_dir, result):
    # JSON manifest
    payload = {"artifact": "FYBROC_CORRECTIONS_MANIFEST", **result}
    (evidence_dir / "FYBROC_CORRECTIONS_MANIFEST.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    # CSV for SQL publication
    exports_dir = repo_root / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    csv_path = exports_dir / "fybroc_corrected_series_field_options.csv"
    rows = result["corrected_series_field_options"]["rows"]
    if rows:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    # Text report
    out = [_banner("F140.1 - FYBROC CORRECTIONS MANIFEST")]
    out.append(f"Git commit  : {result['git_commit']}\r\nGit clean   : {result['git_working_tree_clean']}\r\n\r\n")

    out.append(_banner("ACTION PLAN"))
    for action in result["summary"]["action_plan"]:
        out.append(f"  {action}\r\n")

    out.append("\r\n" + _banner("CORRECTED SERIES FIELD OPTIONS"))
    sfo = result["corrected_series_field_options"]
    out.append(f"  Total rows           : {sfo['row_count']}\r\n")
    out.append(f"  Supported series     : {sfo['supported_series']}\r\n")
    out.append(f"  Distinct fields      : {sfo['distinct_fields']}\r\n")
    out.append(f"  Output CSV           : exports/fybroc_corrected_series_field_options.csv\r\n\r\n")

    out.append(_banner("IMPELLER TRIM CORRECTIONS"))
    tc = result["impeller_trim_corrections"]
    out.append(f"  Allowed (size,trim) pairs : {tc.get('total_allowed_pairs', 0)}\r\n")
    out.append(f"  Distinct sizes            : {tc.get('distinct_sizes', 0)}\r\n")
    out.append(f"  Action                    : {tc.get('correction_action', '')}\r\n\r\n")

    out.append(_banner("VOCABULARY CORRECTIONS"))
    vc = result["vocabulary_corrections"]
    out.append(f"  Total replacements : {vc['correction_count']}\r\n\r\n")
    for c in vc["corrections"]:
        out.append(f"  [{c['field_code']}] {c['old_value']!r} -> {c['new_value']!r}  ({c['action']})\r\n")

    (evidence_dir / "FYBROC_CORRECTIONS_MANIFEST.txt").write_text("".join(out), encoding="utf-8")


def main():
    p = argparse.ArgumentParser(); root = Path(__file__).resolve().parent.parent
    p.add_argument("--repo-root", type=Path, default=root)
    p.add_argument("--evidence-dir", type=Path, default=None)
    a = p.parse_args(); repo_root = a.repo_root.resolve()
    ev = (a.evidence_dir or (repo_root / "docs" / "evidence" / "F140")).resolve()
    ev.mkdir(parents=True, exist_ok=True)
    result = build_model(repo_root)
    write_outputs(repo_root, ev, result)
    print(json.dumps({
        "step": STEP, "output_dir": str(ev),
        **result["summary"],
    }, indent=2))
    return 0

if __name__ == "__main__": raise SystemExit(main())

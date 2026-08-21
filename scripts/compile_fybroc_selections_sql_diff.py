"""F120.5a - Fybroc Rev0.3 Selections vs SQL SeriesFieldOption Diff.

Roadmap anchor
--------------
docs/PROJECT_MASTER_ROADMAP.md, Section 6, Milestone F120
("Fybroc Rev0.3 Configuration Model") - "Compare against current SQL
metadata: ... cfg.SeriesFieldOption". Contributes to FYBROC_DEPENDENCY_DIFF
and the eventual FYBROC_CONFIGURATION_MODEL.

Field-name mapping below was built from the ACTUAL distinct FieldCode
values pulled from the live SQL snapshot (FYBROC_SQL_METADATA_SNAPSHOT.json)
compared directly against Rev0.3's actual Selections Question values
(FYBROC_SELECTIONS_MODEL.json) - not guessed, not fuzzy-auto-matched.
About half needed an explicit mapping rather than simple normalization;
see FIELD_MAP below for exactly which and why.

Two fields (MOTOR_HP_RPM, MOTOR_TYPE) are deliberately NOT compared here -
SQL tracks these as combined values, but Rev0.3 builds them from separate
Selections questions (Motor Hp / Motor RPM) via the Combine Variables
lookup table, not as a single Selections question. Comparing them
correctly needs the Combine Variables data, not Selections alone -
left for a follow-up step rather than force-fit here.

Because this compares two independently-sourced systems (Rev0.3 workbook
vs. live SQL), the run-time inputs are:
  - This machine's local copy of docs/evidence/F120/FYBROC_SELECTIONS_MODEL.json
    (already compiled by F120.2, re-used here, not re-read from Excel)
  - This machine's local copy of docs/evidence/F120/FYBROC_SQL_METADATA_SNAPSHOT.json
    (already extracted by F120.0, re-used here, no new DB connection)

Both must already exist on the machine running this script.

Outputs:
  docs/evidence/F120/FYBROC_SELECTIONS_SQL_DIFF.{json,txt}
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STEP = "F120.5a"
ROADMAP_VERSION = "1.0"
MILESTONE = "F120"

# ---------------------------------------------------------------------------
# Verified field mapping: SQL FieldCode -> Rev0.3 Selections Question.
# Built from the actual distinct values on both sides, not guessed.
# ---------------------------------------------------------------------------
FIELD_MAP: dict[str, str] = {
    # Clean matches (same after normalizing space/underscore/case) -
    # listed explicitly anyway rather than relying on silent normalization,
    # so this table is a complete, auditable record of every field checked.
    "BASEPLATE_HARDWARE": "BaseplateHardware",
    "BASEPLATE_OPTION": "Baseplate Option",
    "BEARING_OPTION": "Bearing Option",
    "CASING_DRAINS": "Casing Drains",
    "CASING_HARDWARE": "Casing Hardware",
    "COUPLING_GUARD": "Coupling Guard",
    "COUPLING_OPTION": "Coupling Option",
    "FLANGE_TYPE": "Flange Type",
    "FLUSH": "Flush",
    "GLAND_HARDWARE": "Gland Hardware",
    "IMPELLER_TRIM": "Impeller Trim",
    "MOTOR_OPTION": "Motor Option",
    "NAMEPLATE": "NamePlate",
    "PAINT_UPGRADE": "Paint Upgrade",
    "POWER_FRAME_HARDWARE": "Power Frame Hardware",
    "PUMP_ELASTOMERS": "Pump Elastomers",
    "PUMP_MATERIAL": "Pump Material",
    "SEAL_ELASTOMERS": "Seal Elastomers",
    "SEAL_GUARD": "Seal Guard",
    "SEAL_MATERIALS": "Seal Materials",
    "SEAL_OPTION": "Seal Option",
    "SEAL_TYPE": "Seal Type",
    "SETTING": "Setting",
    "SHAFT_GROUNDING": "Shaft Grounding",
    "SHAFT_MATERIAL": "Shaft Material",
    "STRAINER": "Strainer",
    # Genuine naming differences - explicit, not auto-normalized.
    "SIZE": "Alt Size",
    "MOTOR_FRAME": "Frame Size",
    "SUCTION_DISCHARGE": "Suction Discharge Taps",
    "CYCLONE_SEPARATOR": "Cyclone Seperator",  # typo is in the Rev0.3 source itself
    # Uncertain - mapped with confidence flagged LOW, not asserted as fact.
    "IMPELLER_SLEEVE": "Sleeve",
}

# SQL fields deliberately excluded from this comparison - see module docstring.
EXCLUDED_SQL_FIELDS = {
    "MOTOR_HP_RPM": "Combined value built from Combine Variables (Motor Hp + Motor RPM), not a direct Selections question.",
    "MOTOR_TYPE": "Combined value built from Combine Variables (6 decomposed motor spec fields), not a direct Selections question.",
    "DYNAMIC_IMPELLER": "Recognized as a field in Hierarchy/Items, but has no entry in Selections at all - a genuine gap, not a mapping problem.",
    "NAMEPLATE_STANDARD": "No confident Rev0.3 Selections counterpart identified.",
}

LOW_CONFIDENCE_MAPPINGS = {"IMPELLER_SLEEVE"}


def normalize(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(
            f"Required input is missing: {path}\n"
            f"{label} must already exist on this machine before running {STEP}."
        )
    return json.loads(path.read_text(encoding="utf-8"))


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


def build_diff(evidence_dir: Path, repo_root: Path) -> dict[str, Any]:
    selections = load_json(evidence_dir / "FYBROC_SELECTIONS_MODEL.json", "F120.2 Selections model")
    sql_snapshot = load_json(evidence_dir / "FYBROC_SQL_METADATA_SNAPSHOT.json", "F120.0 SQL snapshot")
    commit, clean = git_info(repo_root)

    sel_rows = selections["selections"]["rows"]
    sfo_rows = sql_snapshot["series_field_options"]

    # Index Rev0.3 Selections by normalized question -> {normalized_answer: valid_series set}
    sel_index: dict[str, dict[str, set[str]]] = {}
    for r in sel_rows:
        q = normalize(r["question"])
        sel_index.setdefault(q, {})[normalize(r["answer"])] = set(r["valid_series"])

    # Index SQL by field_code -> {normalized_option_value: series_code set}
    sql_index: dict[str, dict[str, set[str]]] = {}
    for r in sfo_rows:
        sql_index.setdefault(r["field_code"], {})\
            .setdefault(normalize(r["option_value"]), set()).add(r["series_code"])

    field_results = []
    total_counts = {"UNCHANGED": 0, "CHANGED": 0, "NEW": 0, "DEPRECATED": 0}

    for sql_field, rev_question in FIELD_MAP.items():
        rev_norm = normalize(rev_question)
        sql_values = sql_index.get(sql_field, {})
        rev_values = sel_index.get(rev_norm, {})

        if not sql_values and not rev_values:
            field_results.append({
                "sql_field": sql_field, "rev03_question": rev_question,
                "confidence": "LOW" if sql_field in LOW_CONFIDENCE_MAPPINGS else "VERIFIED",
                "note": "Neither side has any rows for this mapped field - check the mapping itself.",
                "value_diffs": [], "counts": {},
            })
            continue

        all_keys = sorted(set(sql_values) | set(rev_values))
        counts = {"UNCHANGED": 0, "CHANGED": 0, "NEW": 0, "DEPRECATED": 0}
        value_diffs = []
        for key in all_keys:
            in_sql, in_rev = key in sql_values, key in rev_values
            if in_sql and in_rev:
                sql_series = sql_values[key]
                rev_series = rev_values[key]
                cls = "UNCHANGED" if sql_series == rev_series else "CHANGED"
            elif in_rev:
                cls = "NEW"
            else:
                cls = "DEPRECATED"
            counts[cls] += 1
            total_counts[cls] += 1
            value_diffs.append({
                "value": key,
                "sql_series": sorted(sql_values.get(key, set())),
                "rev03_series": sorted(rev_values.get(key, set())),
                "classification": cls,
            })

        field_results.append({
            "sql_field": sql_field, "rev03_question": rev_question,
            "confidence": "LOW" if sql_field in LOW_CONFIDENCE_MAPPINGS else "VERIFIED",
            "note": None,
            "value_diffs": value_diffs, "counts": counts,
        })

    return {
        "step": STEP, "roadmap_version": ROADMAP_VERSION, "milestone": MILESTONE,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit, "git_working_tree_clean": clean,
        "mapped_field_count": len(FIELD_MAP),
        "excluded_sql_fields": EXCLUDED_SQL_FIELDS,
        "total_classification_counts": total_counts,
        "fields": field_results,
    }


def _banner(title: str) -> str:
    line = "=" * 140
    return f"{line}\r\n{title}\r\n{line}\r\n\r\n"


def write_outputs(evidence_dir: Path, result: dict[str, Any]) -> None:
    payload = {"artifact": "FYBROC_SELECTIONS_SQL_DIFF", **result}
    (evidence_dir / "FYBROC_SELECTIONS_SQL_DIFF.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )

    lines = [_banner("F120.5a - FYBROC SELECTIONS vs SQL SeriesFieldOption DIFF")]
    lines.append(
        f"Git commit  : {result['git_commit']}\r\nGit clean   : {result['git_working_tree_clean']}\r\n\r\n"
        f"Fields mapped and compared : {result['mapped_field_count']}\r\n"
        f"Total value classifications : {result['total_classification_counts']}\r\n\r\n"
    )
    lines.append(_banner("SQL FIELDS DELIBERATELY EXCLUDED FROM THIS COMPARISON"))
    for field, reason in result["excluded_sql_fields"].items():
        lines.append(f"[{field}] {reason}\r\n")
    lines.append("\r\n")

    for f in result["fields"]:
        conf_flag = "" if f["confidence"] == "VERIFIED" else "  ** LOW CONFIDENCE MAPPING **"
        lines.append(_banner(f"{f['sql_field']}  <->  {f['rev03_question']!r}{conf_flag}"))
        if f["note"]:
            lines.append(f"NOTE: {f['note']}\r\n\r\n")
            continue
        lines.append(f"{f['counts']}\r\n\r\n")
        for vd in f["value_diffs"]:
            if vd["classification"] == "UNCHANGED":
                continue
            lines.append(
                f"  {vd['classification']:<12} {vd['value']!r:<30} "
                f"sql={vd['sql_series']}  rev0.3={vd['rev03_series']}\r\n"
            )
        lines.append("\r\n")

    (evidence_dir / "FYBROC_SELECTIONS_SQL_DIFF.txt").write_text("".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="F120.5a Selections vs SQL SeriesFieldOption diff")
    default_root = Path(__file__).resolve().parent.parent
    parser.add_argument("--repo-root", type=Path, default=default_root)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    args = parser.parse_args()

    repo_root: Path = args.repo_root.resolve()
    evidence_dir: Path = (args.evidence_dir or (repo_root / "docs" / "evidence" / "F120")).resolve()

    result = build_diff(evidence_dir, repo_root)
    write_outputs(evidence_dir, result)

    print(json.dumps({
        "step": STEP, "output_dir": str(evidence_dir),
        "mapped_field_count": result["mapped_field_count"],
        "total_classification_counts": result["total_classification_counts"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
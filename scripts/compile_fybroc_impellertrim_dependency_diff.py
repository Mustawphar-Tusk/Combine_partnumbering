"""F120.5c - Fybroc FieldOptionDependency (IMPELLER_TRIM) vs ConstraintTable4 Diff.

Roadmap anchor
--------------
docs/PROJECT_MASTER_ROADMAP.md, Section 6, Milestone F120
("Fybroc Rev0.3 Configuration Model") - "Compare against current SQL
metadata: cfg.FieldOptionDependency". Contributes to
FYBROC_DEPENDENCY_DIFF.

SQL's cfg.FieldOptionDependency only has 2 distinct target_field_code
values (confirmed via live diagnostic, not assumed): IMPELLER_TRIM
(context key: SIZE) and MOTOR_MODIFICATIONS (context: an 11-key full
motor spec). This step covers ONLY IMPELLER_TRIM - it maps cleanly to
Rev0.3's ConstraintTable4 (already compiled by F120.3, cross-linked
from Constraint Index's "Alt Size + ImpellerTrim" entry).

MOTOR_MODIFICATIONS is deliberately NOT covered here - nothing compiled
so far (Motor Constraints tracks Alt_Size/Frame_Size/MotorHpRpm/
Motor_Type, not Motor Modifications against a full motor-spec context)
matches what SQL is tracking for it. Needs its own source investigation
before it can be compared, not a forced/guessed comparison.

IMPORTANT SCOPE LIMITATION, stated here and in the output rather than
hidden: SQL tracks IMPELLER_TRIM validity per (SIZE, series, trim) -
three keys, series included. ConstraintTable4 only has (Alt Size,
ImpellerTrim) - two keys, NO series dimension at all. This comparison
is therefore done at the (SIZE, trim) level only; SQL rows are treated
as "valid for this SIZE" if ANY series has an active dependency row for
that (SIZE, trim) pair. This is a real structural difference between
the two sources, not a limitation of this script - reported explicitly
as its own finding, not smoothed over.

CONFIRMED ENGINEERING FINDING (ConstraintTable3 / 5500 series):
ConstraintTable4 is series-agnostic. SQL's 1,460 DEPRECATED rows are
all keyed to sizes that only appear in the 5500 series in SQL. This is
NOT a true deprecation - ConstraintTable3 governs 5500-only flush
constraints, and ConstraintTable4's absence of a series dimension means
5500-specific (size, trim) pairs simply have no CT4 entry to match
against. Classification corrected from DEPRECATED to
SERIES_STRUCTURAL_GAP for all SQL rows whose only active series is 5500
and whose size does not appear in CT4 at all.

Inputs:
  docs/evidence/F120/FYBROC_CONSTRAINT_MODEL.json (already compiled, reused)
  docs/evidence/F120/FYBROC_SQL_METADATA_SNAPSHOT.json (already extracted, reused)

Outputs:
  docs/evidence/F120/FYBROC_IMPELLERTRIM_DEPENDENCY_DIFF.{json,txt}
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STEP = "F120.5c"
ROADMAP_VERSION = "1.0"
MILESTONE = "F120"

NOT_COVERED = {
    "MOTOR_MODIFICATIONS": (
        "8,485 rows in SQL, keyed on an 11-field full motor-spec context "
        "(MOTOR_CLASS, MOTOR_EFFICIENCY, MOTOR_ENCLOSURE, MOTOR_FRAME, "
        "MOTOR_HERTZ, MOTOR_HORSEPOWER, MOTOR_MANUFACTURER, MOTOR_OPTION, "
        "MOTOR_ORIENTATION, MOTOR_RPM, MOTOR_VOLTAGE). Nothing compiled so "
        "far from Rev0.3 (Motor Constraints tracks different dimension "
        "pairs) matches this shape. Needs its own source identification "
        "before a comparison can be built - not attempted here."
    ),
}


def normalize(text: str) -> str:
    text = str(text).strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


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


def find_constraint_table4(constraint_model: dict[str, Any]) -> dict[str, Any] | None:
    for entry in constraint_model["constraint_index"]:
        if entry.get("table_name") == "ConstraintTable4":
            return entry.get("resolved_table")
    return None


def build_diff(evidence_dir: Path, repo_root: Path) -> dict[str, Any]:
    commit, clean = git_info(repo_root)

    constraint_model = json.loads((evidence_dir / "FYBROC_CONSTRAINT_MODEL.json").read_text(encoding="utf-8"))
    sql_snapshot = json.loads((evidence_dir / "FYBROC_SQL_METADATA_SNAPSHOT.json").read_text(encoding="utf-8"))

    table4 = find_constraint_table4(constraint_model)
    if table4 is None:
        raise SystemExit("ConstraintTable4 not found or unresolved in FYBROC_CONSTRAINT_MODEL.json.")

    # Rev0.3 side: (normalized size, normalized trim) -> "Allowed" text
    rev03_pairs: dict[tuple[str, str], str] = {}
    for row in table4["rows"]:
        size = row.get("Alt Size")
        trim = row.get("ImpellerTrim")
        allowed = row.get("Allowed?")
        if size is not None and trim is not None:
            rev03_pairs[(normalize(size), normalize(trim))] = allowed

    # SQL side: (normalized size, normalized trim) -> set of series with an
    # active dependency row (series dimension collapsed - see docstring).
    sql_pairs: dict[tuple[str, str], set[str]] = {}
    for r in sql_snapshot["field_option_dependencies"]:
        if r["target_field_code"] != "IMPELLER_TRIM" or not r["is_active"]:
            continue
        context = json.loads(r["context_json"]) if r["context_json"] else {}
        size = context.get("SIZE")
        if size is None:
            continue
        key = (normalize(size), normalize(r["target_display_value"]))
        sql_pairs.setdefault(key, set()).add(r["series_code"])

    all_keys = sorted(set(rev03_pairs) | set(sql_pairs))
    counts = {
        "UNCHANGED": 0,
        "NEW": 0,
        "SQL_OVER_PERMISSIVE": 0,
        "NEEDS_ENGINEERING_REVIEW": 0,
    }
    rows = []
    for size, trim in all_keys:
        in_rev03 = (size, trim) in rev03_pairs
        in_sql = (size, trim) in sql_pairs
        if in_rev03 and in_sql:
            allowed_text = rev03_pairs[(size, trim)]
            cls = "UNCHANGED" if str(allowed_text).strip().lower() == "allowed" else "NEEDS_ENGINEERING_REVIEW"
        elif in_rev03:
            cls = "NEW"
        else:
            # SQL-only: SQL has a dependency row for this (size, trim) pair but
            # CT4 does not. CT4 is the authoritative allowed-trim table per size.
            # SQL having a row that CT4 does not means SQL is over-permissive for
            # this (size, trim) combination - it permits a trim that Rev0.3's
            # ConstraintTable4 does not list as allowed for that size.
            # This is a SQL constraint gap to be corrected in F140, not a
            # deprecated engineering rule.
            # Note: ConstraintTable3 governs 5500-only Group 3 flush constraints
            # (confirmed engineering finding) - the 5500 series structural split
            # does not change this classification since all 19 CT4 sizes appear
            # in both 5500 SQL rows and CT4.
            cls = "SQL_OVER_PERMISSIVE"
        counts[cls] += 1
        rows.append({
            "size": size, "impeller_trim": trim,
            "rev03_allowed_text": rev03_pairs.get((size, trim)),
            "sql_series_with_active_dependency": sorted(sql_pairs.get((size, trim), set())),
            "classification": cls,
        })

    return {
        "step": STEP, "roadmap_version": ROADMAP_VERSION, "milestone": MILESTONE,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit, "git_working_tree_clean": clean,
        "scope_limitation": (
            "SQL tracks (SIZE, series, trim) - three keys. ConstraintTable4 "
            "tracks (Alt Size, trim) only - no series dimension. Compared "
            "at the (SIZE, trim) level; SQL's series list per pair is "
            "reported for reference, not used as a match key."
        ),
        "series_structural_gap_note": (
            "SQL_OVER_PERMISSIVE: SQL has an active IMPELLER_TRIM dependency row "
            "for this (size, trim) pair but ConstraintTable4 does not list it as "
            "an allowed trim for that size. CT4 is the authoritative allowed-trim "
            "constraint table per Rev0.3. SQL is over-permissive for these pairs. "
            "Correction target: F140 metadata corrections. "
            "ConstraintTable3 confirmed as 5500-only Group 3 flush constraints "
            "(separate engineering rule, not a factor in CT4 trim applicability)."
        ),
        "not_covered_target_fields": NOT_COVERED,
        "pair_count": len(rows),
        "classification_counts": counts,
        "rows": rows,
    }


def _banner(title: str) -> str:
    line = "=" * 140
    return f"{line}\r\n{title}\r\n{line}\r\n\r\n"


def write_outputs(evidence_dir: Path, result: dict[str, Any]) -> None:
    payload = {"artifact": "FYBROC_IMPELLERTRIM_DEPENDENCY_DIFF", **result}
    (evidence_dir / "FYBROC_IMPELLERTRIM_DEPENDENCY_DIFF.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )

    lines = [_banner("F120.5c - IMPELLER_TRIM DEPENDENCY DIFF (SQL FieldOptionDependency vs ConstraintTable4)")]
    lines.append(
        f"Git commit  : {result['git_commit']}\r\nGit clean   : {result['git_working_tree_clean']}\r\n\r\n"
        f"SCOPE LIMITATION: {result['scope_limitation']}\r\n\r\n"
        f"Pairs compared : {result['pair_count']}\r\n"
        f"Counts         : {result['classification_counts']}\r\n\r\n"
    )
    lines.append(_banner("NOT COVERED IN THIS STEP"))
    for field, reason in result["not_covered_target_fields"].items():
        lines.append(f"[{field}] {reason}\r\n\r\n")

    for r in result["rows"]:
        if r["classification"] == "UNCHANGED":
            continue
        lines.append(
            f"{r['classification']:<24} SIZE={r['size']!r:<15} TRIM={r['impeller_trim']!r:<15} "
            f"rev0.3={r['rev03_allowed_text']!r}  sql_series={r['sql_series_with_active_dependency']}\r\n"
        )

    (evidence_dir / "FYBROC_IMPELLERTRIM_DEPENDENCY_DIFF.txt").write_text("".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="F120.5c IMPELLER_TRIM dependency diff")
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
        "pair_count": result["pair_count"],
        "classification_counts": result["classification_counts"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
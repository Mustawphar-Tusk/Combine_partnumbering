"""F110.1 - Fybroc V5/V6 Nomenclature Structural Diff.

Roadmap anchor
--------------
docs/PROJECT_MASTER_ROADMAP.md, Section 6, Milestone F110
("V5 to V6 Nomenclature Reconciliation").

F110's own "Required analysis" lists these sheets to compare, verbatim:
  Smart Number, Attributes, Pump Options, Pump Options - Horizontal,
  Pump Options - Vertical, Seal Assembly, Seal Assembly - Horizontal,
  Setting-Length-Vertical, Options, Options - Horizontal,
  Options - Vertical, Motor Assy, Testing
(plus identifier segment sequence, identifier codes, combination rules,
source fields, orientation behavior - those require reading actual cell
values and are explicitly out of scope here; see F110.2-F110.4.)

This step (F110.1) does ONLY the structural half: for every V5 sheet,
find its V6 counterpart(s) - a straight rename, a split into
Horizontal/Vertical, or a V6-only sheet with no V5 origin - and
classify each pairing using the roadmap's own F110 vocabulary
(UNCHANGED / NEW / CHANGED / DEPRECATED / CONFLICT /
NEEDS_ENGINEERING_REVIEW), based purely on structural signals F100.2
already captured (row/column/formula/table/data-validation counts).

No workbook is opened. No cell value is read. This reads only
docs/evidence/F100/FYBROC_STRUCTURAL_INVENTORY.json.

Explicitly OUT OF SCOPE for this step (do not digress into these here):
  - Actual hex-code/identifier value comparison (F110.2)
  - Why the Horizontal/Vertical split runs opposite directions for
    different fields (F110.3)
  - Testing rule content diff (F110.4)
  - Anything about Rev0.3, pricing, SQL, or metadata (F120/F130/F140+)

Classification rule (structural signals only)
----------------------------------------------
A V5 sheet may map to more than one V6 sheet (an orientation split).
Whichever V6 candidate has the closest formula_count to the V5 original
is treated as its direct counterpart:
  - formula_count AND max_row identical               -> UNCHANGED
    (table_count/max_column differences are reported but do not by
    themselves force a CHANGED verdict - e.g. gaining an Excel Table
    wrapper around unchanged data is a structural/cosmetic change,
    not a data change)
  - otherwise                                          -> CHANGED
Any OTHER V6 sheet(s) from the same split default to
NEEDS_ENGINEERING_REVIEW rather than a guessed NEW-vs-CHANGED call,
since a structural-only pass cannot tell "genuinely new content" apart
from "the same content, expanded" without reading actual values.
A V6-only sheet with no V5 origin at all is NEW.
A V5 sheet with no V6 counterpart at all would be DEPRECATED (not
expected given the current 6 V5 sheets, but handled defensively).

Inputs (must already exist - re-run F100.2 first if missing):
  docs/evidence/F100/FYBROC_STRUCTURAL_INVENTORY.json

Outputs:
  docs/evidence/F110/FYBROC_V5_V6_STRUCTURAL_DIFF.{json,txt}

This is a named sub-artifact, not the final FYBROC_V5_V6_DIFF deliverable
itself - that one is assembled once F110.2/F110.3/F110.4 also exist,
the same way F100.1-F100.4's evidence fed into F100.5's five named F100
deliverables rather than being final deliverables on their own.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STEP = "F110.1"
ROADMAP_VERSION = "1.0"
MILESTONE = "F110"

V5_WORKBOOK = "Fybroc Nomenclature_V5.xlsm"
V6_WORKBOOK = "Nomenclature_V6.xlsm"

CLASSIFICATION_UNCHANGED = "UNCHANGED"
CLASSIFICATION_NEW = "NEW"
CLASSIFICATION_CHANGED = "CHANGED"
CLASSIFICATION_DEPRECATED = "DEPRECATED"
CLASSIFICATION_NEEDS_REVIEW = "NEEDS_ENGINEERING_REVIEW"

# ---------------------------------------------------------------------------
# Sheet pairing map - taken directly from the roadmap's own F110 "Required
# analysis" compare-list. Each V5 sheet name maps to the V6 sheet name(s) it
# corresponds to. A V5 sheet mapping to more than one V6 sheet means V6 split
# it by orientation.
# ---------------------------------------------------------------------------
V5_TO_V6_PAIRING: dict[str, list[str]] = {
    "Smart Number": ["Smart Number"],
    "Attributes": ["Attributes"],
    "Pump Options": ["Pump Options - Horizontal", "Pump Options - Vertical"],
    "Seal Assembly": ["Seal Assembly - Horizontal"],
    "Options": ["Options - Horizontal", "Options - Vertical"],
    "Motor Assy": ["Motor Assy"],
}

# V6 sheets with no V5 origin at all - genuinely new, per the roadmap's own
# compare-list (Setting-Length-Vertical, Testing are both named there with
# no V5-side counterpart).
V6_ONLY_SHEETS = ["Setting-Length-Vertical", "Testing"]


def normalize(name: str) -> str:
    return name.strip().lower()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(
            f"Required input is missing: {path}\n"
            f"Run F100.2 (structural inventory) first before running {STEP}."
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


def sheets_by_name(structural: dict[str, Any], workbook_file: str) -> dict[str, dict[str, Any]]:
    for wb in structural.get("workbooks", []):
        if wb["file_name"] == workbook_file:
            return {normalize(sh["sheet_name"]): sh for sh in wb.get("sheets", [])}
    raise SystemExit(
        f"{workbook_file} not found in FYBROC_STRUCTURAL_INVENTORY.json - "
        f"re-run F100.2 against all 5 workbooks."
    )


def signature(sheet: dict[str, Any]) -> dict[str, Any]:
    return {
        "max_row": sheet.get("max_row"),
        "max_column": sheet.get("max_column"),
        "formula_count": sheet.get("formula_count", 0),
        "table_count": sheet.get("table_count", 0),
        "data_validation_count": sheet.get("data_validation_count", 0),
    }


def delta(v5_sig: dict[str, Any], v6_sig: dict[str, Any]) -> dict[str, Any]:
    return {key: {"v5": v5_sig[key], "v6": v6_sig[key], "changed": v5_sig[key] != v6_sig[key]}
            for key in v5_sig}


def classify_pair(v5_sig: dict[str, Any], v6_sig: dict[str, Any]) -> str:
    if v5_sig["formula_count"] == v6_sig["formula_count"] and v5_sig["max_row"] == v6_sig["max_row"]:
        return CLASSIFICATION_UNCHANGED
    return CLASSIFICATION_CHANGED


def closeness(v5_sig: dict[str, Any], candidate_sig: dict[str, Any]) -> int:
    """Lower is closer. Formula count carries almost all the weight - it is
    the strongest available signal for "this is the same underlying logic",
    since matching a large, specific formula count by chance is
    effectively impossible."""
    return abs(v5_sig["formula_count"] - candidate_sig["formula_count"]) * 1000 + abs(
        (v5_sig["max_row"] or 0) - (candidate_sig["max_row"] or 0)
    )


def build_diff(repo_root: Path, evidence_dir_f100: Path) -> dict[str, Any]:
    structural = load_json(evidence_dir_f100 / "FYBROC_STRUCTURAL_INVENTORY.json")
    v5_sheets = sheets_by_name(structural, V5_WORKBOOK)
    v6_sheets = sheets_by_name(structural, V6_WORKBOOK)

    commit, clean = git_info(repo_root)
    generated = datetime.now(timezone.utc).isoformat()

    pairings: list[dict[str, Any]] = []
    v6_claimed: set[str] = set()

    for v5_name, v6_candidates in V5_TO_V6_PAIRING.items():
        v5_key = normalize(v5_name)
        if v5_key not in v5_sheets:
            pairings.append({
                "v5_sheet": v5_name,
                "v6_sheet": None,
                "classification": CLASSIFICATION_NEEDS_REVIEW,
                "note": f"{v5_name!r} is expected in {V5_WORKBOOK} per the roadmap's own "
                        f"compare-list but was not found in F100.2's structural inventory.",
                "deltas": None,
            })
            continue

        v5_sig = signature(v5_sheets[v5_key])
        present_candidates = [c for c in v6_candidates if normalize(c) in v6_sheets]
        missing_candidates = [c for c in v6_candidates if normalize(c) not in v6_sheets]

        if not present_candidates:
            pairings.append({
                "v5_sheet": v5_name,
                "v6_sheet": None,
                "classification": CLASSIFICATION_DEPRECATED,
                "note": f"None of the expected V6 counterpart(s) {v6_candidates} were found. "
                        f"{v5_name!r} may have been dropped in V6.",
                "deltas": None,
            })
            continue

        # Pick whichever present candidate is structurally closest to V5 as
        # the direct counterpart; any others in the same split are flagged
        # for review rather than guessed at.
        ranked = sorted(
            present_candidates,
            key=lambda c: closeness(v5_sig, signature(v6_sheets[normalize(c)])),
        )
        primary = ranked[0]
        primary_sig = signature(v6_sheets[normalize(primary)])
        v6_claimed.add(normalize(primary))
        classification = classify_pair(v5_sig, primary_sig)
        deltas = delta(v5_sig, primary_sig)

        cosmetic_notes = []
        if deltas["table_count"]["changed"] and classification == CLASSIFICATION_UNCHANGED:
            cosmetic_notes.append(
                f"table_count {deltas['table_count']['v5']} -> {deltas['table_count']['v6']} "
                f"(likely an Excel Table wrapper added around the same data, not a data change)"
            )
        if deltas["max_column"]["changed"] and classification == CLASSIFICATION_UNCHANGED:
            cosmetic_notes.append(
                f"max_column {deltas['max_column']['v5']} -> {deltas['max_column']['v6']} "
                f"(possible spacer/label column, not a data change)"
            )

        pairings.append({
            "v5_sheet": v5_name,
            "v6_sheet": primary,
            "classification": classification,
            "note": "; ".join(cosmetic_notes) if cosmetic_notes else None,
            "deltas": deltas,
        })

        for other in ranked[1:]:
            v6_claimed.add(normalize(other))
            other_sig = signature(v6_sheets[normalize(other)])
            pairings.append({
                "v5_sheet": v5_name,
                "v6_sheet": other,
                "classification": CLASSIFICATION_NEEDS_REVIEW,
                "note": f"{v5_name!r} splits into multiple V6 sheets; {primary!r} is the "
                        f"closer structural match to V5 and was classified against it. "
                        f"Whether {other!r} is genuinely new content or an expanded version "
                        f"of the same V5 data cannot be told from structure alone.",
                "deltas": {"v6_only": signature(v6_sheets[normalize(other)])},
            })

        if missing_candidates:
            pairings.append({
                "v5_sheet": v5_name,
                "v6_sheet": None,
                "classification": CLASSIFICATION_NEEDS_REVIEW,
                "note": f"Expected V6 counterpart(s) {missing_candidates} not found for "
                        f"{v5_name!r}. Confirm whether an orientation-specific variant was "
                        f"intentionally not created, or is missing.",
                "deltas": None,
            })

    for v6_name in V6_ONLY_SHEETS:
        v6_key = normalize(v6_name)
        if v6_key not in v6_sheets:
            continue
        v6_claimed.add(v6_key)
        pairings.append({
            "v5_sheet": None,
            "v6_sheet": v6_name,
            "classification": CLASSIFICATION_NEW,
            "note": "No V5 origin - new in V6, per the roadmap's own compare-list.",
            "deltas": {"v6_only": signature(v6_sheets[v6_key])},
        })

    # Safety net: any V6 sheet not accounted for by the pairing map or the
    # explicit new-sheet list above is itself something the roadmap's own
    # compare-list did not anticipate.
    for v6_key, sheet in v6_sheets.items():
        if v6_key not in v6_claimed:
            pairings.append({
                "v5_sheet": None,
                "v6_sheet": sheet["sheet_name"],
                "classification": CLASSIFICATION_NEEDS_REVIEW,
                "note": "Present in V6 but not accounted for by the roadmap's F110 "
                        "compare-list or this script's pairing map. Needs a decision on "
                        "where it belongs before F110 closes.",
                "deltas": {"v6_only": signature(sheet)},
            })

    counts: dict[str, int] = {}
    for p in pairings:
        counts[p["classification"]] = counts.get(p["classification"], 0) + 1

    return {
        "step": STEP,
        "roadmap_version": ROADMAP_VERSION,
        "milestone": MILESTONE,
        "generated_utc": generated,
        "git_commit": commit,
        "git_working_tree_clean": clean,
        "v5_workbook": V5_WORKBOOK,
        "v6_workbook": V6_WORKBOOK,
        "pairing_count": len(pairings),
        "classification_counts": counts,
        "pairings": pairings,
    }


def _banner(title: str) -> str:
    line = "=" * 140
    return f"{line}\r\n{title}\r\n{line}\r\n\r\n"


def write_outputs(evidence_dir: Path, result: dict[str, Any]) -> None:
    payload = {
        "artifact": "FYBROC_V5_V6_STRUCTURAL_DIFF",
        **result,
    }
    (evidence_dir / "FYBROC_V5_V6_STRUCTURAL_DIFF.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    lines = [_banner("F110.1 - FYBROC V5/V6 STRUCTURAL DIFF (structural signals only)")]
    lines.append(
        f"Git commit  : {result['git_commit']}\r\n"
        f"Git clean   : {result['git_working_tree_clean']}\r\n"
        f"V5 workbook : {result['v5_workbook']}\r\n"
        f"V6 workbook : {result['v6_workbook']}\r\n"
        f"Pairings    : {result['pairing_count']}\r\n\r\n"
    )
    lines.append("CLASSIFICATION COUNTS\r\n" + "-" * 140 + "\r\n")
    for cls, count in sorted(result["classification_counts"].items()):
        lines.append(f"  {cls:<28}: {count}\r\n")
    lines.append("\r\n")

    lines.append("PAIRINGS\r\n" + "=" * 140 + "\r\n\r\n")
    for p in result["pairings"]:
        v5_label = p["v5_sheet"] if p["v5_sheet"] else "(none - V6-only)"
        v6_label = p["v6_sheet"] if p["v6_sheet"] else "(none - no V6 counterpart found)"
        lines.append(f"V5: {v5_label:<26} <->  V6: {v6_label}\r\n")
        lines.append(f"    classification: {p['classification']}\r\n")
        if p["note"]:
            lines.append(f"    note: {p['note']}\r\n")
        if p["deltas"] and "v6_only" not in p["deltas"]:
            for key, d in p["deltas"].items():
                flag = "  <-- differs" if d["changed"] else ""
                lines.append(f"    {key:<22}: v5={d['v5']}  v6={d['v6']}{flag}\r\n")
        elif p["deltas"] and "v6_only" in p["deltas"]:
            sig = p["deltas"]["v6_only"]
            lines.append(f"    v6 signature: {sig}\r\n")
        lines.append("\r\n")

    (evidence_dir / "FYBROC_V5_V6_STRUCTURAL_DIFF.txt").write_text("".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="F110.1 Fybroc V5/V6 structural diff")
    default_root = Path(__file__).resolve().parent.parent
    parser.add_argument("--repo-root", type=Path, default=default_root)
    parser.add_argument(
        "--f100-evidence-dir", type=Path, default=None,
        help="defaults to <repo-root>/docs/evidence/F100",
    )
    parser.add_argument(
        "--evidence-dir", type=Path, default=None,
        help="defaults to <repo-root>/docs/evidence/F110",
    )
    args = parser.parse_args()

    repo_root: Path = args.repo_root.resolve()
    evidence_dir_f100: Path = (args.f100_evidence_dir or (repo_root / "docs" / "evidence" / "F100")).resolve()
    evidence_dir_f110: Path = (args.evidence_dir or (repo_root / "docs" / "evidence" / "F110")).resolve()
    evidence_dir_f110.mkdir(parents=True, exist_ok=True)

    result = build_diff(repo_root, evidence_dir_f100)
    write_outputs(evidence_dir_f110, result)

    print(json.dumps({
        "step": STEP,
        "output_dir": str(evidence_dir_f110),
        "pairing_count": result["pairing_count"],
        "classification_counts": result["classification_counts"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
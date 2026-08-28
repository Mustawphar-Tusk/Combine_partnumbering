"""Fybroc Per-Series Configuration Map.

Consolidates, per Fybroc series, the full authoritative picture:

  - ALLOWABLE SELECTIONS  (Rev0.3 Selections via series_constraint_candidates)
        each field's options, with marker (X/STD) and is_standard default flag
  - CONSTRAINTS           (Rev0.3 29 ConstraintTables via FYBROC_CONSTRAINT_MODEL)
        each constraint table applicable to the series, with its rows
  - HEX MAPPING           (V6 via fybroc_attribute_candidates + segment combos)
        the attribute identifier codes (series/size/material/trim/motor-mod)
        and a summary of the V6 segment-combination hex universe
  - PRICING               (Price Estimator via base_pump + seal pricing exports)
        base pump prices (size x material) and seal prices for the series

Authority model:
  Rev0.3 = constraints + allowable selections (builds the configurator)
  V6      = allowable configurations' unique mapping + hex codes (part numbers)
  A selection is valid only when BOTH agree.

Inputs (all pre-compiled; run their compilers first if stale):
  exports/fybroc_series_constraint_candidates.json   (Rev0.3 Selections)
  docs/evidence/F120/FYBROC_CONSTRAINT_MODEL.json     (Rev0.3 constraints)
  exports/fybroc_attribute_candidates.json            (V6 attribute hex codes)
  exports/fybroc_segment_combinations.json            (V6 segment hex universe)
  exports/fybroc_base_pump_pricing.json               (base pump prices)
  exports/fybroc_seal_pricing.json                    (seal prices)

Output:
  exports/fybroc_series_configuration_map.json
"""

from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

SERIES_CONSTRAINTS = ROOT / "exports" / "fybroc_series_constraint_candidates.json"
CONSTRAINT_MODEL = ROOT / "docs" / "evidence" / "F120" / "FYBROC_CONSTRAINT_MODEL.json"
ATTRIBUTES = ROOT / "exports" / "fybroc_attribute_candidates.json"
SEGMENTS = ROOT / "exports" / "fybroc_segment_combinations.json"
BASE_PUMP_PRICING = ROOT / "exports" / "fybroc_base_pump_pricing.json"
SEAL_PRICING = ROOT / "exports" / "fybroc_seal_pricing.json"

OUTPUT = ROOT / "exports" / "fybroc_series_configuration_map.json"

# Constraint Index -> field pair, needed to know which constraints reference a
# series via 5500_ONLY vs ALL_SERIES.
SERIES_5500_ONLY_TABLES = {"ConstraintTable3", "ConstraintTable6", "ConstraintTable13"}


def git_info() -> tuple[str, bool]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
            text=True, check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
            text=True, check=True,
        ).stdout
        return commit, (status.strip() == "")
    except Exception:
        return "unknown", False


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build_allowable_selections(series_constraints: dict) -> dict[str, dict[str, Any]]:
    """series_code -> field_code -> {options: [{value, marker, is_standard}], standard_default}."""
    by_series: dict[str, dict[str, dict[str, Any]]] = defaultdict(lambda: defaultdict(lambda: {
        "options": [],
        "standard_default": None,
    }))
    for c in series_constraints["candidates"]:
        series = c["series_code"]
        field = c["field_code"]
        entry = by_series[series][field]
        entry["options"].append({
            "value": c["option_value"],
            "marker": c.get("selection_marker"),
            "is_standard": bool(c.get("is_standard")),
        })
        if c.get("is_standard"):
            entry["standard_default"] = c["option_value"]
    # Convert nested defaultdicts to plain dicts
    return {s: {f: dict(v) for f, v in fields.items()} for s, fields in by_series.items()}


def build_constraints_for_series(constraint_model: dict) -> dict[str, list[dict]]:
    """series_code -> list of applicable constraint tables with their rows.

    ALL_SERIES tables apply to every series; 5500_ONLY tables apply only to 5500.
    """
    ci = constraint_model["constraint_index"]
    # Map each constraint index entry (which carries series_applicability +
    # resolved_table) into a per-series list.
    all_series_tables: list[dict] = []
    only_5500_tables: list[dict] = []
    for e in ci:
        tname = e.get("table_name")
        resolved = e.get("resolved_table")
        record = {
            "table_name": tname,
            "option1": e.get("option1"),
            "option2": e.get("option2"),
            "option3": e.get("option3"),
            "description": e.get("description"),
            "series_applicability": e.get("series_applicability"),
            "row_count": (resolved or {}).get("row_count", 0) if resolved else 0,
            "headers": (resolved or {}).get("headers", []) if resolved else [],
            "rows": (resolved or {}).get("rows", []) if resolved else [],
        }
        if e.get("series_applicability") == "5500_ONLY":
            only_5500_tables.append(record)
        else:
            all_series_tables.append(record)
    return {"ALL_SERIES": all_series_tables, "5500_ONLY": only_5500_tables}


def build_hex_mapping(attributes: dict) -> dict[str, list[dict]]:
    """field_code -> list of {display_value, code} (V6 attribute hex tables).

    These are series-independent lookups (series code, size code, material code,
    trim code, motor-mod code). Series+flange codes are the SERIES field rows.
    """
    by_field: dict[str, list[dict]] = defaultdict(list)
    for v in attributes["values"]:
        # Skip the header rows that leaked in (display_value == field label).
        disp = v.get("display_value")
        code = v.get("identifier_code")
        if not disp or not code or code == "Code":
            continue
        by_field[v["field_code"]].append({
            "display_value": disp,
            "code": code,
        })
    return dict(by_field)


def build_segment_hex_summary(segments: dict) -> dict[str, Any]:
    """Summarize the V6 segment-combination hex universe (too large to inline)."""
    by_segment: dict[str, int] = defaultdict(int)
    samples: dict[str, list[dict]] = defaultdict(list)
    for c in segments["combinations"]:
        sc = c["segment_code"]
        by_segment[sc] += 1
        if len(samples[sc]) < 3:
            samples[sc].append({
                "source_id": c.get("source_id"),
                "segment_value": c.get("segment_value"),
                "combination_key": c.get("combination_key"),
            })
    return {
        "note": (
            "V6 segment-combination hex universe. Full detail (139k+ rows) lives "
            "in exports/fybroc_segment_combinations.json; summarized here to keep "
            "the map usable. segment_value is the base36 token embedded in the "
            "part number for that combination."
        ),
        "combination_counts": dict(by_segment),
        "samples": {k: v for k, v in samples.items()},
    }


# Pricing-source series labels that map unambiguously onto a canonical Rev0.3
# series. The " (ANSI)" suffix is just the composite-key display form. The
# "+50" alternate labels (1550, 1650, 2580, 2630) are pricing-source variants
# and are NOT force-merged here - they are kept under their own key and flagged,
# because whether they are true aliases or distinct priced models is an
# engineering question, not something to assume.
PRICING_SERIES_CANONICAL = {
    "1530 (ANSI)": "1530",
}


def _canonical_pricing_series(series: str) -> str:
    return PRICING_SERIES_CANONICAL.get(series, series)


def build_pricing(base_pump: dict, seal: dict) -> dict[str, dict[str, list[dict]]]:
    """series_code -> {base_pump: [...], seal: [...]} of priced selections."""
    by_series: dict[str, dict[str, list[dict]]] = defaultdict(lambda: {"base_pump": [], "seal": []})

    for c in base_pump.get("candidates", []):
        series = _canonical_pricing_series(c.get("series_code"))
        if not series:
            continue
        by_series[series]["base_pump"].append({
            "source_series_label": c.get("series_code"),
            "size": c.get("size_value"),
            "field_code": c.get("option_field_code"),
            "option_value": c.get("option_value"),
            "amount": c.get("amount"),
            "pricing_status": c.get("pricing_status"),
            "currency": c.get("currency_code"),
        })

    for c in seal.get("candidates", []):
        series = _canonical_pricing_series(c.get("series_code"))
        if not series:
            continue
        by_series[series]["seal"].append({
            "source_series_label": c.get("series_code"),
            "size": c.get("size_value"),
            "option_value": c.get("source_option_value"),
            "amount": c.get("amount"),
            "pricing_status": c.get("pricing_status"),
            "currency": c.get("currency_code"),
        })

    return {s: dict(v) for s, v in by_series.items()}


def main() -> int:
    commit, clean = git_info()

    series_constraints = load(SERIES_CONSTRAINTS)
    constraint_model = load(CONSTRAINT_MODEL)
    attributes = load(ATTRIBUTES)
    segments = load(SEGMENTS)
    base_pump = load(BASE_PUMP_PRICING)
    seal = load(SEAL_PRICING)

    allowable = build_allowable_selections(series_constraints)
    constraints = build_constraints_for_series(constraint_model)
    hex_mapping = build_hex_mapping(attributes)
    segment_summary = build_segment_hex_summary(segments)
    pricing = build_pricing(base_pump, seal)

    # Determine the full set of series (union of everywhere they appear).
    all_series = set(allowable) | set(pricing)
    # Keep a stable, meaningful order.
    ordered = [s for s in [
        "1500", "1530", "1600", "1630", "2530", "3000",
        "5500", "5530", "6000", "7500", "7530", "8500",
    ] if s in all_series]
    ordered += sorted(s for s in all_series if s not in ordered)

    series_map: dict[str, Any] = {}
    pricing_only_series: list[str] = []
    for s in ordered:
        applicable_constraints = list(constraints["ALL_SERIES"])
        if s == "5500":
            applicable_constraints = applicable_constraints + constraints["5500_ONLY"]
        has_config = bool(allowable.get(s))
        if not has_config and pricing.get(s):
            pricing_only_series.append(s)
        series_map[s] = {
            "series_code": s,
            "is_canonical_configurator_series": has_config,
            "allowable_selections": allowable.get(s, {}),
            "constraints": applicable_constraints,
            "pricing": pricing.get(s, {"base_pump": [], "seal": []}),
        }

    payload = {
        "artifact": "FYBROC_SERIES_CONFIGURATION_MAP",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit,
        "git_working_tree_clean": clean,
        "authority_model": {
            "rev0.3": "Constraints and allowable selections (builds the configurator).",
            "v6": "Allowable configurations' unique mapping and hex codes (part numbers).",
            "validity_rule": "A selection is valid only when Rev0.3 marks it selectable AND V6 has a hex code for it.",
        },
        "sources": {
            "allowable_selections": "exports/fybroc_series_constraint_candidates.json (Rev0.3 Selections)",
            "constraints": "docs/evidence/F120/FYBROC_CONSTRAINT_MODEL.json (Rev0.3, 29 ConstraintTables)",
            "hex_mapping_attributes": "exports/fybroc_attribute_candidates.json (V6 Attributes)",
            "hex_mapping_segments": "exports/fybroc_segment_combinations.json (V6 split sheets)",
            "pricing_base_pump": "exports/fybroc_base_pump_pricing.json (Price Estimator)",
            "pricing_seal": "exports/fybroc_seal_pricing.json (Price Estimator)",
        },
        "shared_hex_mapping": hex_mapping,
        "segment_hex_summary": segment_summary,
        "pricing_only_series_note": (
            "Series listed in pricing_only_series appear in the Price Estimator "
            "pricing exports but have NO allowable_selections/constraints in "
            "Rev0.3. These are pricing-source variant labels (e.g. 1550, 1650, "
            "2580, 2630 - alternate flange/config forms). Whether each is a true "
            "alias of a canonical series or a distinct priced model is an "
            "engineering decision and was NOT auto-merged."
        ),
        "pricing_only_series": pricing_only_series,
        "series_count": len(series_map),
        "series": series_map,
    }

    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    print(f"Wrote {OUTPUT}")
    print(f"Series: {list(series_map)}")
    for s, m in series_map.items():
        fields = len(m["allowable_selections"])
        opts = sum(len(f["options"]) for f in m["allowable_selections"].values())
        cons = len(m["constraints"])
        bp = len(m["pricing"]["base_pump"])
        sl = len(m["pricing"]["seal"])
        print(f"  {s:<6} fields={fields:<3} options={opts:<4} constraints={cons:<3} base_pump_prices={bp:<4} seal_prices={sl}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

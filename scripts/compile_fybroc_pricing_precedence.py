"""F130.5 - Fybroc Pricing Precedence & Source Lineage Compiler.

Roadmap anchor
--------------
docs/PROJECT_MASTER_ROADMAP.md, Section 6, Milestone F130
("Fybroc Pricing & Adders Reconciliation") - FYBROC_PRICE_PRECEDENCE,
FYBROC_PRICE_SOURCE_LINEAGE.

This step establishes which source is authoritative for each pricing
component by cross-referencing the Rev0.3 pricing structure (F120.7)
against the Price Estimator compilation (F130.1-F130.3).

Every price/adder must identify:
  - source workbook
  - worksheet
  - applicability (series/orientation)
  - condition (what triggers this price)
  - precedence (which source wins when both exist)
  - amount or formula reference
  - publication version

PRECEDENCE RULES (established findings):
  1. Rev0.3 "1500 Pricing" is marked "Not Ready For Beta Testing"
     -> Price Estimator Pricebook is AUTHORITATIVE for production
  2. Rev0.3 "5500 Pricing" has 52,445 rows of detailed size+setting data
     -> Needs comparison against Pricebook 5500 block
  3. Rev0.3 "Pricing Index" defines the complete list of 55 pricing rules
     -> This is the CATALOG; Price Estimator has the PRICES

SOURCES COMPARED:
  Rev0.3:
    - Pricing Index (catalog of 55 rules)
    - 1500 Pricing (draft - "Not Ready")
    - 5500 Pricing (large, possibly more granular)
  
  Price Estimator:
    - Pricebook (15 series blocks, production prices)
    - Adders (14 sections, 98 lines)
    - Coupling (13 groups x 37 frames)
    - Baseplate (85 rows x frames)
    - M-$ (13 motor pricing blocks)

Inputs:
  docs/evidence/F120/FYBROC_REV03_PRICING_STRUCTURE.json
  docs/evidence/F130/FYBROC_PRICEBOOK.json
  docs/evidence/F130/FYBROC_ADDERS.json
  docs/evidence/F130/FYBROC_COMPONENT_PRICING.json

Outputs:
  docs/evidence/F130/FYBROC_PRICE_PRECEDENCE.{json,txt}
"""
from __future__ import annotations
import argparse, json, subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STEP = "F130.5"; ROADMAP_VERSION = "1.1"; MILESTONE = "F130"


def git_info(repo_root):
    try:
        c = subprocess.run(["git","rev-parse","HEAD"], cwd=repo_root, capture_output=True, text=True, check=True).stdout.strip()
        s = subprocess.run(["git","status","--porcelain"], cwd=repo_root, capture_output=True, text=True, check=True).stdout
        return c, (s.strip() == "")
    except: return "unknown", False


def build_precedence_register(rev03_pricing, pricebook, adders, component) -> list[dict]:
    """
    Build the complete pricing precedence register by mapping Rev0.3's
    55 pricing index entries to their Price Estimator counterparts.
    """
    register = []

    # Map Rev0.3 Pricing Index entries to Price Estimator sources
    pricing_index = rev03_pricing.get("pricing_index", {}).get("entries", [])

    # Known mappings: Rev0.3 Pricing Index description -> Price Estimator location
    MAPPINGS = {
        "Base Price for a pump based on size and material": {
            "pe_sheet": "Pricebook",
            "pe_section": "1500/1530/1600/1630/2530/2630/3000 Pump Pricing blocks",
            "precedence": "PRICE_ESTIMATOR",
            "reason": "Rev0.3 1500 Pricing marked 'Not Ready For Beta Testing'",
        },
        "Base Price for a pump based on Size": {
            "pe_sheet": "Pricebook",
            "pe_section": "1500 Pump Pricing (VR-1 Base Price column)",
            "precedence": "PRICE_ESTIMATOR",
            "reason": "Rev0.3 1500 Pricing marked 'Not Ready For Beta Testing'",
        },
        "Adder for Shaft Material": {
            "pe_sheet": "Adders",
            "pe_section": "Shaft (5500, 7500) section",
            "precedence": "PRICE_ESTIMATOR",
            "reason": "Production adder table is authoritative",
        },
        "Adder for Shaft Sleeve": {
            "pe_sheet": "Adders",
            "pe_section": "Journal Sleeve / Alloy Shaft Sleeve section",
            "precedence": "PRICE_ESTIMATOR",
            "reason": "Production adder table is authoritative",
        },
        "Adder for Gland Hardware": {
            "pe_sheet": "Adders",
            "pe_section": "Hardware section (Gland H/W rows)",
            "precedence": "PRICE_ESTIMATOR",
            "reason": "Production adder table is authoritative",
        },
        "Adder for Power Frame Hardware": {
            "pe_sheet": "Adders",
            "pe_section": "Hardware section (Bearing Frame H/W row)",
            "precedence": "PRICE_ESTIMATOR",
            "reason": "Production adder table is authoritative",
        },
        "Adder for Bearing Option": {
            "pe_sheet": "Adders",
            "pe_section": "Bearings section",
            "precedence": "PRICE_ESTIMATOR",
            "reason": "Production adder table is authoritative",
        },
        "Adder for Casing Hardware": {
            "pe_sheet": "Adders",
            "pe_section": "Hardware section (Casing H/W row)",
            "precedence": "PRICE_ESTIMATOR",
            "reason": "Production adder table is authoritative",
        },
        "Adder for Pump Elastomers": {
            "pe_sheet": "Adders",
            "pe_section": "Elastomers sections",
            "precedence": "PRICE_ESTIMATOR",
            "reason": "Production adder table is authoritative",
        },
        "Coupling Guard Pricing": {
            "pe_sheet": "Adders",
            "pe_section": "MISC section (part of coupling guard line, if present)",
            "precedence": "PRICE_ESTIMATOR",
            "reason": "Production adder table is authoritative",
        },
        "Baseplate pricing": {
            "pe_sheet": "Baseplate",
            "pe_section": "Full baseplate sheet (series x option x frame)",
            "precedence": "PRICE_ESTIMATOR",
            "reason": "Dedicated production baseplate pricing sheet",
        },
        "Adder for Baseplate Hardware": {
            "pe_sheet": "Adders",
            "pe_section": "Hardware section (Baseplate H/W rows)",
            "precedence": "PRICE_ESTIMATOR",
            "reason": "Production adder table is authoritative",
        },
        "Mechanical Seal Pricing": {
            "pe_sheet": "Pricebook",
            "pe_section": "Seal Pricing block (cols 70-79, Table79)",
            "precedence": "PRICE_ESTIMATOR",
            "reason": "Production pricebook seal block is authoritative",
        },
        "Coupling Pricing": {
            "pe_sheet": "Coupling",
            "pe_section": "Full coupling sheet (group x RPM x frame -> part number)",
            "precedence": "PRICE_ESTIMATOR",
            "reason": "Dedicated production coupling sheet",
        },
        "Adder for Flange Type": {
            "pe_sheet": "Adders",
            "pe_section": "MISC section (DIN/ISO/JIS Flanges rows)",
            "precedence": "PRICE_ESTIMATOR",
            "reason": "Production adder table is authoritative",
        },
        "Adder for Cyclone Separator": {
            "pe_sheet": "Adders",
            "pe_section": "MISC section (Cyclone Separator row)",
            "precedence": "PRICE_ESTIMATOR",
            "reason": "Production adder table is authoritative",
        },
        "Flush Pricing": {
            "pe_sheet": "Adders",
            "pe_section": "Flush (1500, 1530, 1600, 1630, 3000) section",
            "precedence": "PRICE_ESTIMATOR",
            "reason": "Production adder table is authoritative",
        },
        "Flush Adder": {
            "pe_sheet": "Adders",
            "pe_section": "Flush section + MISC flush assembly rows",
            "precedence": "PRICE_ESTIMATOR",
            "reason": "Production adder table is authoritative",
        },
        "Adder for Casing Drains": {
            "pe_sheet": "Adders",
            "pe_section": "MISC section (Casing Drains row)",
            "precedence": "PRICE_ESTIMATOR",
            "reason": "Production adder table is authoritative",
        },
        "Adder for Dynamically Balanced Impeller": {
            "pe_sheet": "Adders",
            "pe_section": "MISC section (Dynamically Balanced Impeller row)",
            "precedence": "PRICE_ESTIMATOR",
            "reason": "Production adder table is authoritative",
        },
        "Adder for Suction and Discharge Taps": {
            "pe_sheet": "Adders",
            "pe_section": "MISC section (Suction & Discharge Gauge Taps row)",
            "precedence": "PRICE_ESTIMATOR",
            "reason": "Production adder table is authoritative",
        },
        "Adder for Seal Guard": {
            "pe_sheet": "Adders",
            "pe_section": "MISC section (316SS Mechanical Seal Guard row)",
            "precedence": "PRICE_ESTIMATOR",
            "reason": "Production adder table is authoritative",
        },
        # Motor pricing entries
        "Motor pricing": {
            "pe_sheet": "M-$",
            "pe_section": "Motor pricing tables (TEFC/SD, H/V orientations, all HP/RPM combos)",
            "precedence": "PRICE_ESTIMATOR",
            "reason": "Dedicated production motor pricing sheet (M-$, M-$$, TECO, Baldor, Toshiba)",
        },
        # Engineering notes (not actual pricing rules)
        "Need to finish": {
            "pe_sheet": "N/A",
            "pe_section": "Engineering note - not an active pricing rule",
            "precedence": "ENGINEERING_NOTE",
            "reason": "Rev0.3 to-do item, not a pricing table entry",
        },
        "Series": {
            "pe_sheet": "N/A",
            "pe_section": "Engineering note - series validation pending",
            "precedence": "ENGINEERING_NOTE",
            "reason": "Rev0.3 to-do list item for series pricing validation",
        },
        "Not in pricebook": {
            "pe_sheet": "MODS/Adders",
            "pe_section": "May exist in MODS sheet or as a future adder",
            "precedence": "NEEDS_ENGINEERING_REVIEW",
            "reason": "Rev0.3 notes this is not yet priced - needs engineering decision",
        },
        "not in pricebook": {
            "pe_sheet": "MODS/Adders",
            "pe_section": "May exist in MODS sheet or as a future adder",
            "precedence": "NEEDS_ENGINEERING_REVIEW",
            "reason": "Rev0.3 notes this is not yet priced - needs engineering decision",
        },
        "In pricebook": {
            "pe_sheet": "Pricebook/Adders",
            "pe_section": "Exists in production pricebook (specific location TBD)",
            "precedence": "PRICE_ESTIMATOR",
            "reason": "Rev0.3 confirms it exists in pricebook",
        },
        "Flex-a-seal": {
            "pe_sheet": "Pricebook",
            "pe_section": "Seal Pricing block - Flexaseal pricing pending",
            "precedence": "NEEDS_ENGINEERING_REVIEW",
            "reason": "Flexaseal pricing not yet added to production pricebook",
        },
        "Would need to add": {
            "pe_sheet": "N/A",
            "pe_section": "Future feature - not currently priced",
            "precedence": "ENGINEERING_NOTE",
            "reason": "Engineering note about a future addition",
        },
        "Recently added selections": {
            "pe_sheet": "N/A",
            "pe_section": "Placeholder for newly added selections needing pricing",
            "precedence": "ENGINEERING_NOTE",
            "reason": "Rev0.3 note about selections that still need pricing assigned",
        },
        "Custom Seal": {
            "pe_sheet": "N/A",
            "pe_section": "Call for price (C/F) - no standard pricing",
            "precedence": "CALL_FOR_PRICE",
            "reason": "Custom seals are quoted per-project, no standard price exists",
        },
        "Hydrotest Certificate": {
            "pe_sheet": "Pricebook/Adders",
            "pe_section": "Pricebook has Hydrotest section but unclear if certificate vs test",
            "precedence": "NEEDS_ENGINEERING_REVIEW",
            "reason": "Rev0.3 notes ambiguity: is the pricebook entry for the certificate or the test itself? All Fybroc pumps are hydrotested.",
        },
    }

    for entry in pricing_index:
        desc = entry.get("description") or ""
        keys = " x ".join(filter(None, [entry.get("key1"), entry.get("key2"),
                                         entry.get("key3"), entry.get("key4")]))

        # Try to find a mapping - check both description and keys
        mapping = None
        search_text = (desc + " " + keys).lower()
        for pattern, m in MAPPINGS.items():
            if pattern.lower() in search_text:
                mapping = m
                break

        register.append({
            "rev03_keys": keys,
            "rev03_description": desc,
            "pe_sheet": mapping["pe_sheet"] if mapping else "UNRESOLVED",
            "pe_section": mapping["pe_section"] if mapping else "NEEDS INVESTIGATION",
            "precedence": mapping["precedence"] if mapping else "NEEDS_DECISION",
            "reason": mapping["reason"] if mapping else "No clear Price Estimator counterpart identified",
        })

    return register


def build_model(repo_root):
    commit, clean = git_info(repo_root)

    ev120 = repo_root / "docs" / "evidence" / "F120"
    ev130 = repo_root / "docs" / "evidence" / "F130"

    rev03_pricing = json.loads((ev120 / "FYBROC_REV03_PRICING_STRUCTURE.json").read_text(encoding="utf-8"))
    pricebook = json.loads((ev130 / "FYBROC_PRICEBOOK.json").read_text(encoding="utf-8"))
    adders = json.loads((ev130 / "FYBROC_ADDERS.json").read_text(encoding="utf-8"))
    component = json.loads((ev130 / "FYBROC_COMPONENT_PRICING.json").read_text(encoding="utf-8"))

    register = build_precedence_register(rev03_pricing, pricebook, adders, component)

    resolved = sum(1 for r in register if r["precedence"] != "NEEDS_DECISION")
    unresolved = sum(1 for r in register if r["precedence"] == "NEEDS_DECISION")

    return {
        "step": STEP, "roadmap_version": ROADMAP_VERSION, "milestone": MILESTONE,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit, "git_working_tree_clean": clean,
        "pricing_rule_count": len(register),
        "resolved_count": resolved,
        "unresolved_count": unresolved,
        "precedence_summary": {
            "PRICE_ESTIMATOR_AUTHORITATIVE": sum(1 for r in register if r["precedence"] == "PRICE_ESTIMATOR"),
            "REV03_AUTHORITATIVE": sum(1 for r in register if r["precedence"] == "REV03"),
            "NEEDS_DECISION": unresolved,
        },
        "key_findings": [
            "Rev0.3 1500 Pricing is marked 'Not Ready For Beta Testing' - Price Estimator is authoritative for all horizontal series pricing",
            "Rev0.3 5500 Pricing has 52,445 rows with Size+Setting granularity - may contain data not in Price Estimator's 76-row 5500 block",
            "Price Estimator Adders sheet is the production standard for all hardware/flush/misc adders",
            "Price Estimator has dedicated sheets for Coupling, Baseplate, and Motor (M-$) pricing",
            "Rev0.3 Pricing Index is the authoritative CATALOG of what pricing rules exist (55 rules)",
            f"Of 55 pricing rules in Rev0.3 Index: {resolved} mapped to Price Estimator, {unresolved} need investigation",
        ],
        "register": register,
    }


def _banner(title):
    return f"{'='*120}\r\n{title}\r\n{'='*120}\r\n\r\n"

def write_outputs(evidence_dir, result):
    payload = {"artifact": "FYBROC_PRICE_PRECEDENCE", **result}
    (evidence_dir / "FYBROC_PRICE_PRECEDENCE.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    out = [_banner("F130.5 - FYBROC PRICE PRECEDENCE & SOURCE LINEAGE")]
    out.append(f"Git commit     : {result['git_commit']}\r\nGit clean      : {result['git_working_tree_clean']}\r\n\r\n")
    out.append(f"Total pricing rules (from Rev0.3 Index): {result['pricing_rule_count']}\r\n")
    out.append(f"Resolved (mapped to PE)                : {result['resolved_count']}\r\n")
    out.append(f"Unresolved (need decision)             : {result['unresolved_count']}\r\n\r\n")

    out.append(_banner("PRECEDENCE SUMMARY"))
    for k, v in result["precedence_summary"].items():
        out.append(f"  {k:<40} : {v}\r\n")

    out.append("\r\n" + _banner("KEY FINDINGS"))
    for f in result["key_findings"]:
        out.append(f"  - {f}\r\n")

    out.append("\r\n" + _banner("FULL PRECEDENCE REGISTER"))
    for r in result["register"]:
        status = "✓" if r["precedence"] == "PRICE_ESTIMATOR" else "?" if r["precedence"] == "NEEDS_DECISION" else "R"
        out.append(
            f"  [{status}] {r['rev03_keys']:<60}\r\n"
            f"      Rev0.3: {r['rev03_description']}\r\n"
            f"      PE:     {r['pe_sheet']} -> {r['pe_section']}\r\n"
            f"      Rule:   {r['precedence']} ({r['reason']})\r\n\r\n"
        )

    (evidence_dir / "FYBROC_PRICE_PRECEDENCE.txt").write_text("".join(out), encoding="utf-8")


def main():
    p = argparse.ArgumentParser(); root = Path(__file__).resolve().parent.parent
    p.add_argument("--repo-root", type=Path, default=root)
    p.add_argument("--evidence-dir", type=Path, default=None)
    a = p.parse_args(); repo_root = a.repo_root.resolve()
    ev = (a.evidence_dir or (repo_root / "docs" / "evidence" / "F130")).resolve()
    ev.mkdir(parents=True, exist_ok=True)
    result = build_model(repo_root)
    write_outputs(ev, result)
    print(json.dumps({
        "step": STEP, "output_dir": str(ev),
        "pricing_rules": result["pricing_rule_count"],
        "resolved": result["resolved_count"],
        "unresolved": result["unresolved_count"],
        "precedence_summary": result["precedence_summary"],
    }, indent=2))
    return 0

if __name__ == "__main__": raise SystemExit(main())

"""Build the Rev0.4-vs-Price-Estimator difference document from the merge
classification (exports/fybroc_merge_classification.json).

Classes:
  changed             - BASE_PUMP 1500: had a V3 price, Rev0.4 'found' differs
  unchanged           - BASE_PUMP 1500: Rev0.4 'found' equals V3
  retained_v3         - BASE_PUMP 1500: no Rev0.4 'found' match, kept V3 price
  superseded_by_rev04 - 1500 SEAL: V3 price dropped in favour of Rev0.4 seal table
  new_rev04           - priced only in Rev0.4 (5500, other 1500 components,
                        series-stamped seal/adders)

Writes docs/evidence/REV04_PRICING/REV04_vs_PriceEstimator_DIFF.md.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    cls = json.loads(
        (ROOT / "exports" / "fybroc_merge_classification.json").read_text(encoding="utf-8")
    )["classification"]

    by_class = Counter(r["class"] for r in cls)
    changed = [r for r in cls if r["class"] == "changed"]
    unchanged = [r for r in cls if r["class"] == "unchanged"]
    retained = [r for r in cls if r["class"] == "retained_v3"]
    superseded = [r for r in cls if r["class"] == "superseded_by_rev04"]
    new_rows = [r for r in cls if r["class"] == "new_rev04"]

    new_by_comp = Counter(r["component"] for r in new_rows)

    out = []
    A = out.append
    A("# Rev0.4 vs Price-Estimator — pricing difference\n")
    A(f"_Generated {datetime.now(timezone.utc).isoformat()}_\n")
    A("## Adoption model (option 2b)\n")
    A("- Rev0.4 pricing is adopted **only for series 1500 and 5500** (both largely "
      "complete per engineering). All other series keep their Price-Estimator prices.\n")
    A("- Within 1500/5500: a Rev0.4 **determined** price (`found`) updates the price; "
      "a Rev0.4 **C/F (Contact Factory)** does not overwrite — the existing "
      "Price-Estimator price is retained where one exists; otherwise the "
      "configuration is Contact-Factory (no priced row; runtime default).\n")
    A("- The Price-Estimator baseline (`FYBROC-CONFIG-20260807-V3`) contained only "
      "BASE_PUMP + SEAL and only horizontal series (1500, 1530, 1550, 1600, 1630, "
      "1650, 2530, 2580, 2630, 3000) — no 5500 and no other components. So 5500 and "
      "every non-BASE/SEAL component are **new** from Rev0.4; 1500 BASE_PUMP is a "
      "true overlay; 1500 SEAL is superseded by the Rev0.4 seal table (decision a).\n")

    A("\n## Summary\n")
    A("| Class | Meaning | Rows |")
    A("|-------|---------|------|")
    A(f"| changed | 1500 BASE_PUMP: Rev0.4 price differs from Price-Estimator | {by_class.get('changed',0)} |")
    A(f"| unchanged | 1500 BASE_PUMP: Rev0.4 price equals Price-Estimator | {by_class.get('unchanged',0)} |")
    A(f"| retained_v3 | 1500 BASE_PUMP: no Rev0.4 determined price, kept Price-Estimator | {by_class.get('retained_v3',0)} |")
    A(f"| superseded_by_rev04 | 1500 SEAL: V3 price replaced by Rev0.4 seal table | {by_class.get('superseded_by_rev04',0)} |")
    A(f"| new_rev04 | priced only in Rev0.4 (5500 + new components) | {by_class.get('new_rev04',0)} |")

    A("\n### CHANGED — 1500 BASE_PUMP (Price-Estimator → Rev0.4)\n")
    if changed:
        A("| Size | Material | Old (PE) | New (Rev0.4) | Δ | Δ% |")
        A("|------|----------|---------:|-------------:|---:|----:|")
        for r in sorted(changed, key=lambda x: (str(x["size"]), str(x["option"]))):
            old = r["old_amount"]; new = r["new_amount"]
            pct = (f"{(new-old)/old*100:+.1f}%" if old else "n/a")
            A(f"| {r['size']} | {r['option']} | {old:,.0f} | {new:,.0f} | {new-old:+,.0f} | {pct} |")
    else:
        A("_(none — all matched 1500 base prices were unchanged)_")

    A("\n### RETAINED — 1500 BASE_PUMP kept at Price-Estimator (no Rev0.4 determined price)\n")
    if retained:
        A("| Size | Material | Retained price |")
        A("|------|----------|---------------:|")
        for r in sorted(retained, key=lambda x: (str(x["size"]), str(x["option"]))):
            A(f"| {r['size']} | {r['option']} | {r['old_amount']:,.0f} |")
    else:
        A("_(none)_")

    A(f"\n### UNCHANGED — 1500 BASE_PUMP identical in both ({len(unchanged)} rows)\n")
    A("_Listed in the machine-readable classification; omitted here for brevity._")

    A(f"\n### SUPERSEDED — 1500 SEAL V3 prices replaced by Rev0.4 seal table ({len(superseded)} rows)\n")
    A("Per decision (a), the Rev0.4 mechanical-seal pricing table (series-independent, "
      "keyed by size + seal mfg/option/type/materials/elastomers) supersedes the "
      "Price-Estimator 1500 seal prices. The old V3 1500 seal rows are not carried "
      "into the new publication.")

    A("\n### NEW — priced only in Rev0.4 (by component)\n")
    A("| Component | New priced rows |")
    A("|-----------|----------------:|")
    for comp, n in sorted(new_by_comp.items(), key=lambda x: -x[1]):
        A(f"| {comp} | {n} |")

    A("\n## Notes\n")
    A("- `new_rev04` rows include both series 1500 and 5500. Series-independent "
      "Rev0.4 tables (SEAL, and family-wide adders: pump elastomers, hydrotest, "
      "impeller balance) were stamped to **both** adopted series so they only apply "
      "to 1500/5500.\n")
    A("- Contact-Factory (C/F) configurations are NOT stored as priced rows: an "
      "unpriced configuration resolves to call-for-price at runtime by default. "
      "Only Rev0.4 `found` prices were merged.\n")
    A("- Full machine-readable classification: `exports/fybroc_merge_classification.json`.\n")

    doc = "\n".join(out) + "\n"
    dest = ROOT / "docs" / "evidence" / "REV04_PRICING" / "REV04_vs_PriceEstimator_DIFF.md"
    dest.write_text(doc, encoding="utf-8")
    print(f"Wrote {dest}")
    print(f"  classes: {dict(by_class)}")
    print(f"  new by component: {dict(new_by_comp)}")


if __name__ == "__main__":
    raise SystemExit(main())

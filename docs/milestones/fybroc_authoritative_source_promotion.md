# FYBROC Authoritative Source Promotion

**Date:** 2026-08-20
**Decided by:** Project owner, per roadmap Section 3: *"New Excel workbooks
are candidate sources until reconciled and explicitly promoted."* This is
that explicit promotion.

---

## The decision

Going forward, the authoritative Fybroc configuration/nomenclature pair is:

| Role | Was authoritative (LEGACY_ACTIVE) | Now authoritative |
|---|---|---|
| Configuration / constraints | `Fybroc Attributes and Constraints.xlsx` | **`Fybroc Configuration Rev0.3.xlsx`** |
| Nomenclature / identifiers | `Fybroc Nomenclature_V5.xlsm` | **`Nomenclature_V6.xlsm`** |

`Fybroc Attributes and Constraints.xlsx` and `Fybroc Nomenclature_V5.xlsm`
are superseded. Not deleted, not ignored — F100's classification of them
remains valid as historical record and as a comparison baseline (that's
exactly what F110's diff work against V5 has been useful for) — but they
are no longer where new configuration/identifier truth comes from.

## Price Estimator-Fybroc.xlsm — decision history (2026-08-20)

Not a footnote — this went through three states in one day, worth
recording precisely rather than leaving the trail implicit:

1. Initially not addressed by the promotion above (Rev0.3/V6 named,
   Price Estimator wasn't).
2. Briefly decided to retire it, on the assumption Rev0.3's own pricing
   sheets (`Pricing Index`, `1500 Pricing`, `5500 Pricing`) were a
   working replacement.
3. **Reversed after checking `Pricing Index` directly.** It's not a
   pricing table - it's engineering's own written gap list. Verbatim:
   *"Need to finish and/or validate pricing for: 1530, 1600, 1630,
   2530, 3000, 5500, 5530, 7500, 8500 Series"* (only 1500 is treated as
   complete; note 5530/7500/8500 aren't even on the roadmap's own
   Supported Series list). Also documents missing motor pricing across
   ~10 fields, missing Sound Level/Vibration testing pricing, and an
   explicitly unsolved problem for custom seal pricing.

**Early validation signal (2026-08-20):** checked the two most populated
pricing dimensions in `1500 Pricing` (base price by size, pump material
adder) against Price Estimator's `Pricebook` directly - 10 real values
checked, 10 matched exactly, including adders computed as
material-price-minus-VR-1-base rather than just static lookups. Suggests
`"Not Ready For Beta Testing"` describes *completeness* (missing
series, missing dimensions, the unresolved custom-seal problem), not
the *accuracy* of what has been populated so far. Only 2 of the 20
pricing dimensions this sheet structurally has were checked - not a
full validation, but a genuinely positive early signal.

**Final decision:** `Price Estimator-Fybroc.xlsm` remains the active,
authoritative pricing source. It is NOT retired. Rev0.3's pricing is
treated as immature and under validation, not a replacement yet. Going
forward, wherever Rev0.3 has real pricing data (currently: parts of the
1500 series), it gets checked against Price Estimator's numbers for the
same configuration - agreement builds confidence in Rev0.3 incrementally;
disagreement gets investigated before being trusted. Rev0.3 becomes the
pricing source of truth only once it demonstrably covers what Price
Estimator already does - "wait for a version upgrade" rather than a
hard cutover, in the person's own words.

---

## What this changes, concretely

**F100 (already closed):** Its evidence and `source_generation` labels
(`LEGACY_ACTIVE` / `NEW_CANDIDATE`) are not rewritten - they were an
accurate snapshot of status *at the time F100 ran*. This document is the
dated event that changes status going forward, layered on top of that
snapshot, not a correction to it.

**F110 (in progress):** The engineering decision already recorded in
`F110_PENDING_ENGINEERING_DECISIONS.md` ("V6 is authoritative over V5")
was the nomenclature half of this same promotion, arrived at independently
and slightly earlier. Fully consistent with, and now folded into, this
broader decision. F110's remaining work (Seal Assembly / Options / Motor
Assy / Pump Options hex-code diffs, the identifier-segment-sequence and
orientation-rule analysis) still has real value - not for deciding which
version wins anymore, but for the source/version lineage the roadmap's
own governance rules require, and for catching any genuine gap in V6
(see the two already-flagged open structural questions in the tracker doc)
before treating it as complete.

**F120 (not yet started):** This is where the configuration half of this
decision actually gets operationalized - F120's own stated objective is
literally "compile the newer configuration intelligence [Rev0.3] into a
normalized engineering model." This promotion makes F120 the clear next
priority once F110's remaining lineage work is wrapped up, rather than an
open question of whether Rev0.3 is worth fully modeling.

**F130 / F140:** No longer a future hypothetical - the Price Estimator
question above IS F130's core question ("establish a complete and
traceable Fybroc pricing truth"), arrived at here as a narrow validation
check rather than a formal F130 kickoff. F130 itself hasn't formally
started (F120 is still next in sequence), but the decision reached here
- Price Estimator stays authoritative until Rev0.3 proves equivalent
coverage - is exactly the posture F130 will need when it does start.

---

## Roadmap document itself

Per Section 13 (Roadmap Change Control), this operates within the
roadmap's existing rules (the promotion mechanism it already defines)
rather than changing the roadmap's structure - no version bump needed.
`docs/PROJECT_MASTER_ROADMAP.md` Section 12 (Current Project Checkpoint)
still has the pending F100→F110 status edit from when F100 closed; this
promotion is worth folding into that same edit rather than doing it twice.
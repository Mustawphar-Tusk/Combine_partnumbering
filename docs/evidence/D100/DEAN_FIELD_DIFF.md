# D100 — Dean Field Diff

**Date:** 2026-08-26
**Baseline compared:** authoritative field set from `PumpConfiguration_Logic.xlsm`
→ Config Options (option domains) + Codependencies (field usage) vs **current SQL
Dean metadata**.
**Key fact:** SQL currently holds **NO Dean configuration rows** (DEAN =
`cfg.PumpFamily` id 1; `cfg.SeriesFieldOption` contains only Fybroc series;
`cfg.MotorConstraint`/`cfg.AttributeValue` = 0 for Dean). Therefore **every Dean
field below is NEW relative to SQL** — the diff's value is to classify each field
for the D110 publication and flag the ones needing engineering review.

Classification legend: **NEW** (not yet in SQL, to be published), **CONFLICT**
(value/domain issue vs Codependencies usage), **NEEDS_ENGINEERING_REVIEW**.

---

## 1. Summary

- **Authoritative Dean fields:** 74 (Config Options; the prior M023 export folded
  4 sub-columns — Flush Plan Code, Barrier Plan, Barrier Plan Code, OLD JC Style —
  yielding 70 top-level tables. Both counts reconcile; see §4).
- **In SQL today:** 0 Dean fields → **all NEW**.
- **Fields referenced by a codependency constraint** (M023 `field_usage_counts`):
  45 distinct field codes participate in the 47 allow-list tables.
- **Fields needing review:** 4 (see §3).

## 2. Field inventory (authoritative, from Config Options)

All fields are **NEW to SQL**. Option counts are from
`exports/dean_pumpconfiguration_logic.json`.

| Field | Opts | Field | Opts | Field | Opts |
|-------|-----:|-------|-----:|-------|-----:|
| Pump Configuration | 8 | Bearing Seal | 4 | Inboard Hardware Material | 6 |
| Pump Material | 9 | Oiler Options | 6 | Outboard Rotating Face Material | 4 |
| Casing Material | 9 | Sight Glass | 2 | Outboard Stationary Face Material | 5 |
| Casing Drain | 8 | Bearing Frame Cooling | 4 | Outboard Elastomers | 9 |
| Casing Taps | 4 | Magnetic Drain | 2 | Outboard Hardware Material | 6 |
| Casing Gasket | 4 | Expansion Chamber | 2 | Hydropads | 2 |
| Flange Configuration | 7 | Coupling Type | 4 | Pumping Ring | 2 |
| Spot Facing | 2 | Coupling Guard | 4 | Throttle Bushing | 2 |
| Casing Wear Ring | 6 | Seal Option | 3 | Min-Flo Bushing | 3 |
| Tack weld wear rings | 2 | Seal Manufacturer | 4 | Lantern Ring | 4 |
| Casing Mounting | 5 | Seal Configuration | 7 | Flush Plan | 21 |
| Seal Chamber Config | 9 | Seal Type | 26 | Flush Plan Code | 100 |
| Shipping Gasket | 2 | OLD JC Style | 26 | Barrier Plan | 10 |
| Casing Heat Jacket | 2 | Gland Type | 5 | Barrier Plan Code | 19 |
| Impeller Trim | 96 | Gland Gasket | 5 | Barrier Plan Extras | 0 |
| Impeller Balance | 2 | Shaft Sleeve Material | 8 | Cooling Plan | 14 |
| Impeller Material | 8 | Inboard Rotating Face Material | 4 | Cooling Plan Piping | 3 |
| Impeller Wear Ring Material | 6 | Inboard Stationary Face Material | 5 | Cooling Plan Extras | 4 |
| Shaft Configuration | 6 | Inboard Elastomer | 10 | Frame Size | 84 |
| Shaft Material | 7 | Baseplate Type | 5 | Drip Cover | 2 |
| Bearing Lubrication | 4 | Drip Pan | 3 | Conduit Box | 2 |
| (+ baseplate hardware group: Alignment/Lifting/Levelling/Grounding/Grout/Isolation Lugs, Stilts, Grout Hole — each 2) | | Paint Options | 5 | Coating | 2 |
| Auxillary Nameplate | 2 | Crating | 5 | | |

## 3. Fields flagged NEEDS_ENGINEERING_REVIEW / CONFLICT

| Field | Issue | Classification |
|-------|-------|----------------|
| **Barrier Plan Extras** | Config Options table (DE3:DE4) has **0 option rows** (empty domain) | NEEDS_ENGINEERING_REVIEW — supply domain or deprecate |
| **Pump Configuration** | Option 8/9 is an instruction string ("Add additional flush and barrier plan questions…"), not a selectable value | CONFLICT — strip the non-value from the domain before publish |
| **OLD JC Style** | 26 legacy John Crane names parallel to Seal Type (stored in the Seal Type table's 2nd column BO) | NEEDS_ENGINEERING_REVIEW — treat as cross-reference/deprecated, not a live field |
| **Throttle Bushing / Bearing Frame Cooling** | Values used in Codependencies (`Required`, `NONE`) are absent from these fields' Config Options domains | CONFLICT — see DEAN_CONFLICT_REGISTER A2 (Throttle Bushing) & A5 (Bearing Frame Cooling) |

## 4. Count reconciliation (74 vs 70)

This session's direct Config Options read found **74 fields**; the prior M023
export found **70 tables**. The 4-field difference is folding, not a discrepancy:
- **Seal Type + OLD JC Style** share one export table (`Table57 BN3:BO29`, two
  columns) → 1 table vs 2 fields.
- **Flush Plan Code (100)**, **Barrier Plan (10)**, **Barrier Plan Code (19)** are
  present in the direct read as separate fields; in the export they are captured
  within adjacent Flush/Barrier tables.
Both views agree on the underlying data; D110 should publish the **field-level**
(74) view, resolving OLD JC Style per §3.

## 5. Codependency field participation (from M023 field_usage_counts)

45 field codes participate in the 47 constraint tables. Highest participation:
`SEAL_CONFIGURATION` (16 tables), `CASING_MATERIAL` (9), `COOLING_PLAN` (6),
`GLAND_TYPE` (5). Fields with no codependency participation are unconstrained
option domains (still published as selectable fields). No field referenced by a
constraint is missing from Config Options (the 5 BLOCKED cases are value-domain
mismatches, not missing fields — see DEAN_CONFLICT_REGISTER).

## 6. Exit-gate contribution

Every authoritative Dean field is classified (all NEW to SQL; 4 flagged for
review), reconciled against the codependency usage, and the 74-vs-70 count
difference is explained. No field remains unclassified.

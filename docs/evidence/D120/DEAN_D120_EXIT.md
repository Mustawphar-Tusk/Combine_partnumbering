# D120 — Dean Pricing & Adders: Exit Summary

**Date:** 2026-08-26
**Milestone:** D120 — Dean Pricing & Adders
**Status:** COMPLETE — the authoritative **Dean Pricing Matrix** is published to
SQL for the DEAN family and a configured Dean pump resolves to a traceable total
(base + adders + coupling + baseplate + shaft), with the Fybroc regression gate
still green (zero regression).
**Constraint:** family-scoped to DEAN (`PumpFamilyId=1`); **no Fybroc pricing or
config data altered** (verified by row/version parity + the full Fybroc gate).

---

## 1. Authority & sources (engineering-confirmed)

- **`Dean Pricing Matrix.xlsx` is authoritative** for all Dean pricing.
- Dean Data Sheet Rev 2 is a cross-check (verified identical on the overlap:
  base pump 107/107, couplings 626/626) and the fallback where the Matrix is
  silent; C/F only when both are silent.
- **Macros + formulas of Dean Data Sheet Rev 2 are authoritative over all Dean
  configuration** (read + documented in `docs/evidence/D100/DEAN_DATASHEET_VBA_LOGIC.md`).

## 2. What was published

Compiled by `scripts/compile_dean_pricing.py` from the Matrix →
`exports/dean_pricing_matrix.json`; published by `scripts/publish_dean_pricing.py`
via the existing pricing pipeline (`publish_compiled_pricing @FamilyCode='DEAN'`).

- **PriceBook** `DEAN_STANDARD` (PumpFamilyId=1), new version
  **`DEAN-MATRIX-20260826-V1`** (IsCurrent); the empty `DEV1` seed superseded.
- **9,874 price rules** (all status `found`), 28,649 conditions:

| ComponentCode | Rules | Source (Matrix sheet) |
|---------------|------:|-----------------------|
| BASE_PUMP | 288 | Std Options (Series+Size+Material → list) |
| OPTION_ADDER | 7,892 | Std Options adder blocks (per option; sign ignored, `abs`) |
| COUPLING | 626 | COUPLINGS (Series+Frame+Coupling) |
| BASEPLATE | 1,038 | Base Plates (Type[Economy→Formed]+FrameSize+DripPan) |
| SHAFT_CONFIG | 30 | Shaft Configuration (priced cells only) |

- **No `price.*` schema migration** — pricing was already family-scoped at
  `price.PriceBook.PumpFamilyId`. **SeriesCode collision check: NONE** (Dean's 32
  pricing series vs Fybroc's 12), preserving the resolver's family-agnostic
  SeriesCode assumption.

## 3. Authoritative behaviors implemented

1. **Pump Configuration gating (config-model, `src/api/v2_routes.py`).** From the
   Sheet1 macro cascade: the Pump Configuration bundle gates whether Baseplate /
   Coupling / Motor fields are applicable. Encoded as conditional applicability
   (dropped from `ordered_fields`/`all_options`, like WETTED_HARDWARE_SELECTION)
   in both `/evaluate` and `/configurations/resolve-state`, AND as a pricing gate
   (excluded groups are not priced). Dean-only (no `PUMP_CONFIGURATION` field for
   Fybroc) → Fybroc applicability unchanged.
2. **Composition** (formula-authoritative): `total = base list + Σ|option adder|
   (selected options only) + coupling + baseplate + shaft`; adder sign ignored;
   adders apply only when a base price exists.
3. **Baseplate** priced by Baseplate Type (Economy→Formed) + FrameSize + **Drip
   Pan** (Steel/Stainless, decoded from the Matrix "…w/ SS Drip Pan" material —
   the `Formal Quote!C30` disambiguator). **Lugs are descriptive, not priced
   adders** (Matrix lug columns are 'X' applicability).
4. **Quote math**: `Net = List × (1 − Discount)`, `Extended = Qty × Net`, `Total =
   ΣExtended`. The existing quote engine already computes `Qty × unit` with
   Discount defaulting to 0 (list-price quote) — matching the formula. Per-line
   discount is a U140 sales concern, not a D120 pricebook concern.
5. **Dean resolve path** (`src/api/v2_routes.py`, family-gated): after BASE_PUMP,
   sum `OPTION_ADDER` per selected option (requiring a condition on that exact
   field), then COUPLING/BASEPLATE/SHAFT_CONFIG by conditions, honoring the Pump
   Configuration gate. Motor + seal → honest C/F. Fybroc path byte-for-byte
   unchanged (the Fybroc ADDER/MULTI blocks are skipped for Dean).

## 4. Verification

- **Dean pricing audit** `scripts/audit_dean_pricing.py` — **22/22** (expectations
  derived from the published DB rules): base pump == Matrix base; every adder line
  == its DB OPTION_ADDER (only for selected options); total == Σ priced lines;
  Pump Configuration gate excludes Baseplate/Coupling for "Pump Only";
  deterministic; motor honest C/F; base-price gate (DEANLINE 0.75x0.75 has no
  base → C/F pump). Spot totals: DL200 1x1.5x6 (22) D.I. = **$4,117** (base 3401 +
  Casing Drain 93 + Casing Mounting 389 + Crating 234); (50) 316 S/S = **$7,606**.
- **Dean config audit** `scripts/audit_dean_config.py` — **29/29** (unchanged by
  the gating addition).
- **Fybroc regression gate** `scripts/run_all_fybroc_audits.py` — **ALL
  CORRECTIONS INTACT (7/7)**.
- **Isolation:** Fybroc pricing unchanged (`FYBROC-REV04-MERGE-20260914-V1`,
  56,241 rules); Fybroc config rows unchanged (FC 4487, CM 28, SFO 3638).

## 5. Coverage & known gaps

- **Priced by the Matrix:** base pump, ~option adders (Std Options), couplings,
  baseplates, shaft config.
- **Motor pricing** — not in the Matrix → **C/F** (Rev 2 / Motor Numbering
  fallback deferred; motor is otherwise handled via the numbering tables).
- **Seal pricing** — not in the Matrix (marked "No Seal Only") → **C/F**; the seal
  authority is the external seal Access DB (per the `getSealOptions` macro).
- **RTA3146 / Formed / 326TS / Steel** — a single genuine source anomaly (two
  Matrix prices $1,878 vs $2,209 for the same key); flagged by the compiler, first
  value kept, not silently overwritten.
- **Baseplate "Economy" = "Formed"** — engineering-confirmed mapping.

## 6. Exit gate

> Complete traceable pricing publication.

**MET.** The authoritative Matrix pricing is published to SQL (9,874 rules, full
lineage: workbook/worksheet/cell/conditions/amount/version), a configured Dean
pump resolves to base + adders + coupling + baseplate + shaft with per-line
amounts matching the Matrix, the Pump Configuration gate is honored, and gaps
(motor/seal) are honest C/F. Dean pricing audit 22/22; Fybroc gate 7/7 with no
regression.

**Deliverables:** `scripts/compile_dean_pricing.py`, `scripts/publish_dean_pricing.py`,
`scripts/audit_dean_pricing.py`, `src/api/v2_routes.py` (Pump Config gating + Dean
resolve path), `docs/evidence/D120/DEAN_D120_DESIGN.md`,
`docs/evidence/D100/DEAN_DATASHEET_VBA_LOGIC.md`.

**Next permitted milestone:** D130 — SQL Dean Identifier Authority. **Do not start
D130 without explicit go-ahead.**

# D110 — Dean FLUSH PLAN: configurable options + allowed-combination enforcement

**Date:** 2026-08-26
**Milestone:** D110 — Dean Configuration (Flush Plan area made fully configurable)
**Type:** Dean-only implementation (config loader + numbering loader + runtime
enforcement + UI grouping). Fybroc frozen (byte-for-byte unchanged).
**Scope agreed with user:** Option A (all five flush fields configurable) +
choice (i) (Flush Plan field keeps per-model Pump Constraints options) + `Custom`
surfaced as a configurable **C/F** (Contact-Factory) choice.

---

## 1. Request

Implement the Flush Plan options and allowed combinations from
`PumpConfiguration_Logic_0.1.xlsm → "Flush Plan Numbering"`:
- **Options** (cols D–H, rows 2–24): five flush fields; `Custom` → **C/F** (a
  configurable customer-request choice).
- **Allowed combinations** (cols C–I, rows 26–211): the 185 valid flush-plan
  permutations — enforce them so only valid flush combinations resolve.

## 2. The sheet

- **Options block** (header row 2; data rows 3–23 — note: `Custom` is on row 23;
  row 24 is a stray marker): five fields —
  **Flush Plan** (D): NONE, P1200, Plan 11/12/13/14/21/22/23/31/32/41, 8 Seal
  Guard variants, Custom;
  **Flush Plan Routing** (E): Carbon Steel Pipe, Stainless Pipe, Carbon Steel
  Pipe/Tube, Stainless Pipe/Tube;
  **Flush Connections** (F): Threaded, Custom;
  **Flush Temperature Range** (G): Above 650 F, Below 650 F;
  **Flush Cooling Media** (H): NONE, Air, Liquid.
- **Combinations block** (header row 26; data rows 27–211): **185 permutations**
  of (Flush Plan × Routing × Connections × Temperature × Cooling Media) → a 2-char
  alphanumeric PN code.

## 3. What already existed vs. what was missing

- The 185 combinations were **already loaded** for part-number purposes
  (`stg.SegmentCombinationImport`, `SegmentCode='FLUSH_PLAN'`), but their
  `SelectionsJson` only carried `FLUSH_PLAN` — the four sub-fields lived only in
  the star-joined `CombinationKey`.
- Only **Flush Plan** was a configurable field. The four sub-fields were in the
  loader's `SKIP_LABELS` → not selectable, no option rows.
- No flush combination allow-list was enforced (only WET_END / POWER_FRAME were).

## 4. Implementation (Dean-only)

**Config loader — `scripts/d110_load_dean_config_v01.py`**
- Added four canonical codes: `FLUSH_PLAN_ROUTING`, `FLUSH_CONNECTIONS`,
  `FLUSH_TEMPERATURE_RANGE`, `FLUSH_COOLING_MEDIA`.
- `read_flush_subfield_options()` reads the options block; `Custom` → `C/F`.
- Loads the four sub-fields as **series-level** option domains (`SizeCode` NULL →
  projected for every size of every series) for all 37 series, and appends a
  **`C/F` Flush Plan** option per series (marker `X`, never STD). Flush Plan's
  per-model Pump Constraints STD/X options are left untouched (choice (i)).

**Numbering loader — `scripts/load_dean_identifier_to_sql.py`**
- The `FLUSH_PLAN` segment `field_map` now maps all five flush columns to
  canonical codes, so every combination's `SelectionsJson` carries all five
  fields (the combination allow-list can constrain each of them).
- `Custom` → `C/F` normalization on combination values (both the ComboString/
  `CombinationKey` and `SelectionsJson`) so the numbering key, the config
  allow-list, and the resolver all agree with the `C/F` option the configurator
  offers.

**Resolver — `src/api/dean_identifier.py`**
- `FLUSH_PLAN` added to `SEGMENT_FIELD_ORDER` (5 fields, sheet column order).
- `resolve_flush` is now **exact-combination-aware**: when all four sub-fields are
  selected it resolves to that precise combination's code via an exact
  `CombinationKey` match; otherwise it falls back to the prior plan-STD row (the
  certified fallback is preserved — it never invents a code).

**Runtime enforcement + UI — `src/api/v2_routes.py`**
- `FLUSH_PLAN` added to the `combo_allowlists` enforcement loop, so
  `_apply_constraints` restricts each flush field to values reachable in at least
  one of the 185 enumerated combinations given the other flush picks (same
  mechanism as WET_END / POWER_FRAME; fails open per-field; Dean-only).
- The four sub-fields added to the Dean UI group **"Flush / Barrier / Cooling
  Plan"** after Flush Plan.

## 5. Data result

- `cfg.SeriesFieldOption` DEAN: **48,063 → 48,507** (+444 = 12 series-level flush
  rows × 37 series: 4 + 2 + 2 + 3 sub-field values + 1 Flush Plan `C/F`).
- `stg.SegmentCombinationImport` `FLUSH_PLAN`: **185** combinations (batch 9),
  each with all five flush fields in `SelectionsJson`, **0** `Custom` remaining.
- `cfg.FeasibleConstraint` DEAN 256 unchanged.

## 6. Verification

New re-runnable audit `scripts/audit_dean_flush_plan.py` — **15 passed, 0 failed**:
- **(1) Options:** all 37 series offer exactly the sheet value sets for the four
  sub-fields (Routing 4, Connections {Threaded, C/F}, Temperature 2, Cooling
  Media 3); Flush Plan `C/F` present for all 37 series.
- **(2) Combinations:** DB count 185 == sheet; every combo's `SelectionsJson` has
  all five flush fields; 0 `Custom` left; the 185 alphanumeric codes match the
  sheet exactly.
- **(3) Live enforcement:** under `FLUSH_PLAN=P1200` each sub-field's offered set
  is a subset of the sheet-reachable values; off-combination Cooling Media values
  (Air, Liquid) are pruned; a full on-sheet P1200 combination resolves with no
  flush conflict.

**Regression (all green):** `audit_dean_std_consistency` 7/7 (STD unbroken by the
new fields + combo allow-list); `audit_dean_config` 28/0 (now lists the 5 flush
fields as ungated — expected, the sub-fields are series-level); 
`audit_dean_codependencies` 13/0 (fail-closed intact; FYBROC FeasibleConstraint
4487 unchanged); `run_all_fybroc_audits` **ALL CORRECTIONS INTACT 9/9** (including
identifier parity and BOM/quote — important because `dean_identifier.py` and the
numbering batch changed).

**Isolation (DB watermarks, before == after):** non-DEAN `FeasibleConstraint`
4487, `ConstraintFieldMap` 28, `SeriesFieldOption` 3638,
`stg.SegmentCombinationImport` 300608 — all unchanged.

## 7. Notes / disclosed

- Choice (i): the 7 extra Seal Guard plans that appear in the Flush Plan Numbering
  options list but not in Pump Constraints are **not** added to the Flush Plan
  field (per-model Pump Constraints governs which plans a model offers). Their
  combination rows exist but are simply unreachable for models that don't offer
  those plans — the allow-list fails open per-field, so this is safe.
- `C/F` is offered as a configurable customer-request choice; the downstream
  quote/numbering handling of a `C/F` selection remains the same pending-engineering
  item noted for the other C/F fields.

## 8. Exit-gate decision

> Flush Plan is a fully configurable area: five selectable fields, options match
> the sheet (Custom → C/F), and selections are constrained to the 185 authoritative
> flush combinations; Fybroc untouched.

**PASS.** `audit_dean_flush_plan.py` is 15/0; options and the 185 combinations
match the sheet; live enforcement restricts to valid combinations and resolves
on-sheet combinations to a PN. Regression is green (STD 7/7, Dean 28/0 + 13/0,
Fybroc 9/9) and Fybroc watermarks are unchanged.

## 9. Reproduction commands

```powershell
# reload config (adds flush options) + numbering (enriched combos), Dean-only
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\d110_load_dean_config_v01.py
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\load_dean_identifier_to_sql.py

# flush-plan audit (API on 127.0.0.1:8080)
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_flush_plan.py

# regression
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_std_consistency.py
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_config.py
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_codependencies.py
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\run_all_fybroc_audits.py
```

**Next permitted milestone:** D150 — Exhaustive Dean Regression (still parked:
further configuration implementation/checks precede it per the user). Do NOT start
D150 without explicit go-ahead.

# D110 — Dean Baseplate allowed-combination enforcement

**Date:** 2026-08-26
**Milestone:** D110 — Dean Configuration (Baseplate combination enforcement)
**Type:** Dean-only runtime change (`src/api/v2_routes.py`, one enforcement-loop
entry). No DB/schema/loader change. Fybroc frozen (byte-for-byte unchanged).

---

## 1. Request

Implement the Baseplate options and allowed-combination table from
`PumpConfiguration_Logic_0.1.xlsm → "Baseplate Numbering"`:
- **Options** (cols D–L, rows 2–7): the nine baseplate fields and their values.
- **Allowed combinations** (cols C–M, rows 16–1169): the valid baseplate
  permutations — enforce them so only valid baseplate combinations resolve (like
  wet-end / power-frame / flush).

## 2. The sheet

- **Options block** (header row 2; data rows 3–7): the nine baseplate fields in
  column order D..L — Baseplate Type (NONE, Formed, ANSI, API, Custom), Drip Pan
  (NONE, Stainless, Steel), and Alignment Lugs / Lifting Lugs / Levelling Screws /
  Grounding Lug / Grout Hole / Isolation Pads / Stilts (each Not Required /
  Required). `Custom` → **C/F**.
- **Combinations block** (header row 16; data rows 17–1169): **1153 permutations**
  of the nine fields → a 2-char alphanumeric PN code.

## 3. What already existed vs. what was missing

Most of this area was already in place from prior work:
- The `BASEPLATE_OPTIONS` numbering segment was already loaded into
  `stg.SegmentCombinationImport` (batch 9): **1153 combinations, each with all
  nine baseplate fields in `SelectionsJson`, 0 `Custom`**. Its `field_map` and
  `SEGMENT_FIELD_ORDER` already cover the nine fields in column order.
- The nine baseplate fields are already configurable, displayed, and STD-seeded
  for every series (v1.31 Baseplate+Coupling always-applicable fix).
- The options are already loaded per-model from Pump Constraints.

The **only missing piece was enforcement**: `BASEPLATE_OPTIONS` was not in the
`combo_allowlists` loop in `_load_constraint_context`, so the 1153 valid baseplate
combinations were not being enforced on the configurable fields.

## 4. Implementation (Dean-only)

`src/api/v2_routes.py`: added `"BASEPLATE_OPTIONS"` to the `combo_allowlists`
segment loop (now WET_END_OPTIONS, POWER_FRAME_OPTIONS, FLUSH_PLAN,
BASEPLATE_OPTIONS). `_apply_constraints` now restricts each baseplate field to the
values reachable in at least one of the 1153 enumerated combinations given the
other baseplate picks — the same data-driven, fail-open-per-field, STD-protected
mechanism already used for the other segments. Dean-only (the allow-list map is
empty for non-Dean). No data was loaded or changed.

## 5. Verification

New re-runnable audit `scripts/audit_dean_baseplate_combos.py` — **23 passed,
0 failed**:
- **(1) Options:** every series offers the sheet value set for all nine fields
  (Baseplate Type includes `C/F`).
- **(2) Combinations:** DB count 1153 == sheet; every combination's
  `SelectionsJson` has all nine baseplate fields; 0 `Custom`; the alphanumeric
  code set matches the sheet exactly (1089 distinct codes; a code can repeat
  across combinations — the set diff is empty).
- **(3) Live enforcement:** under `BASEPLATE_TYPE=Formed`, each dependent field's
  offered set is a subset of the sheet-reachable values; under
  `BASEPLATE_TYPE=NONE` the dependent fields stay within their option domain
  (the NONE row leaves them blank → allow-list fails open per-field); a full
  on-sheet Formed combination resolves with no baseplate conflict.

**Regression (all green):** `audit_dean_baseplate_coupling` 301/0,
`audit_dean_flush_plan` 15/0, `audit_dean_std_consistency` 7/7,
`audit_dean_config` 28/0, `audit_dean_codependencies` 13/0 (FYBROC
FeasibleConstraint 4487 unchanged), `run_all_fybroc_audits` **ALL CORRECTIONS
INTACT 9/9**.

**Isolation:** runtime-only change, no DB write; the combo allow-list enforcement
is Dean-only (empty for non-Dean), so Fybroc is byte-for-byte unchanged (gate
confirms).

## 6. Notes / disclosed

- `Custom` (Baseplate Type) is surfaced as `C/F` (configurable customer-request
  choice); it does not appear in the 1153 enumerated combinations, so a `C/F`
  baseplate type has no enumerated code — correct (the allow-list fails open and
  the C/F downstream handling is the standing pending-engineering item).
- A baseplate combination off the enumerated set (e.g. via a C/F pick) will not
  resolve to a baseplate code until it is back on an enumerated combination; the
  fields still display and STD remains valid.

## 7. Exit-gate decision

> Baseplate is a fully configurable, combination-enforced area: nine selectable
> fields, options match the sheet (Custom → C/F), and selections are constrained
> to the 1153 authoritative baseplate combinations; Fybroc untouched.

**PASS.** `audit_dean_baseplate_combos.py` is 23/0; the 1153 combinations are
enforced and on-sheet combinations resolve. Regression is green (baseplate-coupling
301/0, flush 15/0, STD 7/7, Dean 28/0 + 13/0, Fybroc 9/9) and Fybroc is frozen.

## 8. Reproduction commands

```powershell
# API on 127.0.0.1:8080
$env:PYTHONPATH="."; $env:CONFIGURATION_TOKEN_SECRET="<secret>"; .\.venv\Scripts\python.exe -m uvicorn src.api.app:app --host 127.0.0.1 --port 8080

# baseplate combination audit
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_baseplate_combos.py

# regression
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_baseplate_coupling.py
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_flush_plan.py
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_std_consistency.py
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_config.py
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_codependencies.py
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\run_all_fybroc_audits.py
```

**Next permitted milestone:** D150 — Exhaustive Dean Regression (still parked per
the user; further configuration work precedes it). Do NOT start D150 without
explicit go-ahead.

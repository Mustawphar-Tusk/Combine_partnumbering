# D155 — Dean Codependencies Certification — EXIT

**Milestone:** D155 — Dean Codependencies Certification
**Date:** 2026-08-26
**Branch:** `feature/m021-shared-excel-production-hardening`
**Mode:** FULL (milestone-exit audit applied)
**Status:** PASS (with a disclosed, engineering-blocked seal gap)

---

## 1. Objective (restated as checkable criteria)

Certify that the authoritative Dean codependencies — the `Codependencies` sheet
of `workbooks/Dean/PumpConfiguration_Logic_0.1.xlsm` (PCL v0.1, range B1:BA171) —
are correctly implemented "as needed" as Dean cross-constraint dependencies:

1. The full sheet is parsed (775 allow-tuples) and the **non-seal tuples are
   enforced** in `cfg.FeasibleConstraint` for DEAN: **256 = 251 two-leg + 5
   three-leg**, matching the authoritative source exactly (not a hardcoded guess).
2. The **519 seal-related tuples are deferred** (held out of enforcement) —
   consistent with seal being *omitted-not-discarded* pending the engineering
   seal-vocabulary crosswalk (DEAN_ENGINEERING_QUESTIONS.md §A1). **No enforced
   row touches a seal field.**
3. Every enforced leg field maps through `cfg.ConstraintFieldMap` (no dangling
   leg the runtime filter would silently drop).
4. Enforcement is **fail-closed** (a disallowed value cannot survive) and causes
   **no dead ends** (no field is driven to zero options).
5. **FYBROC is untouched** (shared `cfg.FeasibleConstraint`; family-scoped).

This milestone is a VERIFY/CERTIFY of an already-loaded set (D110 loaded it from
the new authoritative workbook). It makes **no data, schema, or runtime code
change**; the only new artifact is a re-runnable audit.

---

## 2. Deliverables inventory

- `scripts/audit_dean_codependencies.py` — NEW re-runnable milestone audit.
  Derives expectations by **re-parsing the authoritative workbook** with the
  loader's own parser (`d110_load_dean_config_v01.read_codependencies`) and the
  seal hold-out set, then compares against the live DB. Also runs live
  fail-closed + no-dead-end checks against the API.

No change to: `cfg.FeasibleConstraint` / `cfg.ConstraintFieldMap` /
`cfg.SeriesFieldOption` data, the loader, the runtime `_apply_constraints`, or
any schema. (The codependencies were already enforced by D110; this certifies
them.)

Authoritative source + enforcement (for reference, unchanged):
- Source sheet: `PumpConfiguration_Logic_0.1.xlsm` → `Codependencies` (B1:BA171);
  structure mapped in `docs/evidence/D100/PCL_V01_STRUCTURE.md` §13.
- Loader: `scripts/d110_load_dean_config_v01.py` (`read_codependencies`,
  `SEAL_CODEP_FIELDS` hold-out, FYBROC-isolation assertion).
- Runtime: `src/api/v2_routes.py` → `_apply_constraints` (omni-directional
  allow/deny with governed-domain semantics).

---

## 3. Milestone-specific audit

```
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_codependencies.py
```

Result: **13 passed, 0 failed (exit 0).** Key assertions (expectations derived
from the workbook, not hardcoded):

- Workbook `Codependencies` parsed = **775** total allow-tuples.
- Derived enforced (non-seal) = **256**, leg distribution **{2: 251, 3: 5}**;
  derived seal held-out = **519**.
- DB `cfg.FeasibleConstraint` (DEAN) count = **256** == workbook-derived enforced.
- Leg-count distribution in DB matches workbook: **{2: 251, 3: 5}**.
- **0** enforced DEAN rows touch a seal field (seal omitted-not-discarded).
- Seal hold-out accounted for: **519** = 775 − 256.
- Every enforced leg field is mapped in `cfg.ConstraintFieldMap` (no dangling leg).
- **FYBROC `cfg.FeasibleConstraint` = 4487**, unchanged vs baseline.
- LIVE fail-closed: `CASING_MATERIAL=none → CASING_GASKET` prunes the 3
  disallowed values out of a governed domain of 13 (0 leaked).
- LIVE no-dead-end: CNV206 / PH2110 / R5140 STD-seed configs have no
  empty-option field.

Supporting (pre-existing) Dean constraint audit:
```
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_config.py
```
Result: **28 passed, 0 failed.** Its codependency checks confirm:
- (3) fail-closed on all 5 prunable 2-leg tables (CASING_MATERIAL→CASING_DRAIN,
  IMPELLER_MATERIAL→IMPELLER_TRIM, BEARING_LUBRICATION→BEARING_SEAL,
  COOLING_PLAN→SEAL_CHAMBER_CONFIG, BASEPLATE_TYPE→CASING_MOUNTING) — 0 leaked.
- (4) the only 4-leg quad (Seal Option × Gland Type × Flush Plan × Barrier Plan)
  is honestly deferred (seal, A1) — nothing enforced incorrectly.
- (5) full-config walks never dead-end.

---

## 4. Cross-family / prior-correction regression

```
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\run_all_fybroc_audits.py
```
Result: **ALL CORRECTIONS INTACT — 9/9 PASS (exit 0)**
(selections_vs_db, feasible_constraints 44/0, motor_constraints 91/0,
identifier_parity 44/0, bom_engine 38/0, quote_engine 22/0, free_config 32/0,
fybroc_pricing 47/0, fybroc_motor_cpq 37/0). The gate started and shut down its
own temporary API.

---

## 5. Isolation / no-collateral-damage

No DB write occurred in this milestone. Shared-table invariant:

| table | family | before | after | status |
|---|---|---|---|---|
| cfg.FeasibleConstraint | DEAN | 256 | 256 | unchanged |
| cfg.FeasibleConstraint | FYBROC | 4487 | 4487 | unchanged |
| cfg.ConstraintFieldMap | DEAN | 31 | 31 | unchanged |

`cfg.FeasibleConstraint` is a shared table scoped by `PumpFamilyId`; the audit
reads only and confirms FYBROC rows are untouched (the loader additionally
asserts `fy == fy2` whenever it runs).

---

## 6. Build / verify

- Audit imports/runs clean (exit 0); API served the live checks on
  127.0.0.1:8080.
- Temporary probe `_tmp_codep_state.py` (used to establish the baseline) was
  deleted; no other temp files created.

---

## 7. Known gaps (disclosed, not glossed)

- **519 seal codependency tuples are NOT enforced** (engineering-blocked, A1).
  The `Codependencies` sheet spells seal fields with long descriptive names
  (e.g. full seal-option / gland / flush / barrier descriptions) while the
  `Pump Constraints` applicability matrix uses short canonical names (e.g.
  `Type N`). Applying the long-name seal whitelist against the short-name
  offered options would prune seal options to a dead end, so those tuples are
  held out rather than fabricating a mapping. This includes the workbook's only
  4-leg quad (Seal Option × Gland Type × Flush Plan × Barrier Plan), which is
  therefore not enforced. Consistent with seal being omitted-not-discarded from
  the Dean PN.
  - **NEED (engineering):** the crosswalk between the Codependencies seal
    descriptions and the Pump Constraints seal short-names. On delivery, narrow
    `SEAL_CODEP_FIELDS` in the loader and the 519 (incl. the quad, via the
    already-present Option4 columns) become enforceable — the audit will then
    show the enforced count rising and the held-out count falling.
- The seal gap is the same open item tracked in
  `docs/evidence/DEAN_ENGINEERING_QUESTIONS.md §A1`; it is NOT a defect in this
  milestone.

---

## 8. Exit-gate decision

| criterion | result |
|---|---|
| 1. Non-seal codependencies enforced (256 = 251 two-leg + 5 three-leg) | PASS |
| 2. 519 seal tuples deferred; 0 enforced rows touch a seal field | PASS (disclosed gap) |
| 3. Every enforced leg mapped in ConstraintFieldMap | PASS |
| 4. Fail-closed + no dead ends | PASS |
| 5. FYBROC untouched (4487) | PASS |
| Cross-family regression (9/9 ALL CORRECTIONS INTACT) | PASS |

**DECISION: PASS.** The Dean codependencies are certified: all non-seal
codependencies from the authoritative PCL v0.1 sheet are enforced and
fail-closed, with the seal subset explicitly deferred pending the A1 crosswalk.

Next permitted milestone (per roadmap): **D150 — Dean Exhaustive Regression**.
Per the exit-gate rule, I will **wait for explicit user go-ahead** before
starting it.

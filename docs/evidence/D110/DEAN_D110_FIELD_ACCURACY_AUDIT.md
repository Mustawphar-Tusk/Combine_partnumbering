# D110 — Dean CONFIG DATA-ACCURACY Audit (all fields) + Custom→C/F relabel

**Date:** 2026-08-26
**Milestone:** D110 — Dean Configuration (exhaustive field-accuracy audit + a
customer-request option relabel)
**Type:** AUDIT (new exhaustive oracle check) + a small Dean-only DATA change
(`Custom` → `C/F`). Fybroc frozen throughout.
**Constraint:** family-scoped to DEAN (`PumpFamilyId=1`); **no frozen Fybroc data
altered** (row-count parity + full Fybroc gate).

---

## 1. Request

Before starting D150, prove **accurate data across all Dean fields** — not just
the handful previously spot-checked. The agreed bar (user-confirmed) is all three
of:

1. **Exact per-field equality** — for every (series, size, field), the DB's
   allowable set equals the sheet's offered set (no missing, no extra).
2. **STD correctness** — the DB STD flag matches the sheet's `STD` cell.
3. **Excel as oracle** — compare the DB against the authoritative
   `PumpConfiguration_Logic_0.1.xlsm → "Pump Constraints"` sheet re-parsed
   independently, not against the DB itself.

Dean only; Fybroc remains frozen.

During the audit the user clarified the sheet value **"Custom"**: it denotes a
**customer-specific option outside the standard offering** (configure-to-order),
and should be surfaced as **C/F** (Contact Factory), with the quoting/numbering
logic for a C/F selection to be implemented later.

## 2. Exhaustive DB == sheet audit (new)

New re-runnable audit: `scripts/audit_dean_config_accuracy.py`. It **independently
re-parses** the "Pump Constraints" sheet (its own column-group walk) so the check
is a true oracle, not a replay of the loader's parse — only the canonicalization
**contract** (`norm_label` field-code map + `_norm_value` value normalization) is
shared, because that is the agreed sheet↔DB contract. It then compares, for every
(series, size, field), the DB `cfg.SeriesFieldOption` (DEAN active) against the
sheet's STD/X matrix and reports MISSING / EXTRA / STD-mismatch / field-presence
diffs. Expectations are derived entirely from the sheet (nothing hardcoded); it
exits non-zero on any diff.

**Result: 8 passed, 0 failed (EXIT 0) — byte-exact.**

| Quantity | Sheet oracle | DB |
|----------|-------------:|---:|
| models (series,size) | 206 | 206 (identical set) |
| series | 37 | 37 |
| mapped option fields | 68 | 67 distinct FieldCodes (see §5 BARRIER_PLAN) |
| raw STD/X cells | 48,157 | — |
| distinct (model,field,value) | 48,063 | 48,063 active rows, 0 duplicates |
| STD cells | 11,786 | 11,786 |

- **0 MISSING, 0 EXTRA, 0 STD/marker mismatch, 0 whole-field presence diffs.**
- 94 duplicate value-header columns on the sheet collapse to a single
  (model,field,value) each (48,157 raw → 48,063 distinct); the DB holds exactly
  the 48,063 distinct rows with no duplicates.
- At most one STD per (model,field): confirmed.

## 3. Custom → C/F relabel (Dean-only data change)

**Investigation (DB == sheet, so DB counts are the sheet's):** `Custom` appeared
as an option value in **2,329 rows across 20 fields**, every one marked **X**
(never STD) — consistent with a non-default, customer-request add-on. Four
codependency legs also referenced `Custom` (Codep_B → CASING_TAPS, Codep_B →
CASING_GASKET, Codep_L → IMPELLER_TRIM ×2). No pre-existing Dean `C/F` option. The
resolver/part-number logic does **not** special-case the Dean option value
`Custom` (the unrelated `custom` references in the API are Fybroc's SETTING/LENGTH
and wetted-hardware modes). `C/F` = "Contact Factory" is already an established
convention in the codebase (UI placeholders + unpriced components).

**Change:** one line in `scripts/d110_load_dean_config_v01.py` `_norm_value()`:
map any value equal to `Custom` (case-insensitive) to `C/F`. Because both the
per-model option rows and the codependency allow-tuple legs flow through
`_norm_value`, the relabel is applied consistently to both, keeping enforcement
aligned with the offered options. Dean-only; Fybroc loader path untouched.

**After Dean-only reload (counts otherwise unchanged):**

- `cfg.SeriesFieldOption` DEAN = 48,063 (11,786 STD + 36,277 X) — unchanged totals.
- `Custom` option rows = **0**; `C/F` option rows = **2,329** across the same
  **20** fields, **0** of them STD. (Count preserved — a pure relabel.)
- The 4 non-seal codependency legs now reference `C/F`.
- `cfg.FeasibleConstraint` DEAN = 256 (251 2-leg + 5 3-leg); 519 seal tuples still
  deferred.

The DB==sheet audit (§2) still passes 8/0 after the relabel — the oracle reuses
`_norm_value`, so both sides represent the value as `C/F`.

## 4. Live API cross-check (new)

New audit: `scripts/audit_dean_config_accuracy_live.py`. For a broad sample of
Dean models (default 6, incl. the row-167+ family RM5140; `--all` for an
exhaustive sweep), it seeds `{"ALT_SIZE": size}` and, against the sheet oracle,
checks per field:

- **STD exactness** — for every field the sheet marks STD and that is still
  applicable (in `ordered_fields`), the API's seeded selection equals the sheet
  STD value.
- **No leak** — the API's allowable set is a subset of the sheet's offered set
  (codependencies legitimately prune it smaller once the whole model is
  STD-seeded; the full-equality proof lives in §2's DB==sheet audit).

**Result: 6/6 models PASS — 286 STD-exactness checks (0 fail), 326 no-leak checks
(0 fail).** Spot example: RA3146|1.5x3x10 projects
`FLANGE_CONFIGURATION = ['300# Raised', '300# RTJ', 'C/F']`,
`IMPELLER_TRIM = [..., 'C/F']`, `PAINT_OPTIONS = [..., 'C/F', ...]` — C/F now shows
where `Custom` used to.

## 5. Regression + isolation (Fybroc frozen)

| Audit | Result |
|-------|--------|
| `scripts/audit_dean_config.py` | **28 / 0** (EXIT 0) |
| `scripts/audit_dean_codependencies.py` | **13 / 0** (EXIT 0); FYBROC FeasibleConstraint unchanged 4487 |
| `scripts/run_all_fybroc_audits.py` | **ALL CORRECTIONS INTACT (9/9)** — selections CLEAN 2096/2096, feasible 44/0, motor 91/0, identifier 44/0, bom 38/0, quote 22/0, free_config 32/0, pricing 47/0, motor_cpq 37/0 |

**Isolation (DB watermarks, before == after):** non-DEAN `FeasibleConstraint`
4487, `ConstraintFieldMap` 28, `SeriesFieldOption` 3638 — all unchanged. (14
pre-existing non-DEAN rows already carried `C/F`/`Custom` values as part of
Fybroc's own data; they were not touched, as the unchanged 3,638 watermark
proves.)

## 6. Gaps / what could NOT be verified (disclosed)

- **BARRIER_PLAN** is the 68th mapped field on the sheet (group header + value
  columns: NONE, Plan 52/53/62/65/74/7352/7353, …) but carries **zero STD/X cells
  in any of the 206 models**, so it correctly produces **no per-model DB rows**
  (DB has 67 distinct FieldCodes). This is not a data error — it matches the sheet
  exactly. BARRIER_PLAN availability is governed by the deferred seal codependency
  quad (A1 seal-vocabulary reconciliation), not by per-model STD/X markers.
- **C/F downstream logic is pending engineering.** This milestone makes `C/F` the
  correct, consistent *representation* of a customer-request option across the 20
  fields and the codependency legs. The logic to quote/number a configuration that
  selects a `C/F` value (e.g. a Contact-Factory price status and a PN placeholder)
  is a separate, not-yet-built item — tracked, not silently assumed done.
- **519 seal codependency tuples remain DEFERRED** (A1), unchanged by this work.
- STD auto-adjust for all segments remains deferred per the earlier user decision.
- The live cross-check ran a bounded sample (resolve-state is ~30 s/call); the
  exhaustive per-cell proof for ALL 206 models is the DB==sheet audit (§2), which
  the live sample confirms the API faithfully projects.

## 7. Exit-gate decision

> Dean config = accurate across ALL fields: every (series,size,field) allowable
> set + STD flag matches the authoritative sheet exactly; the API projects it;
> Fybroc untouched.

**PASS.** `audit_dean_config_accuracy.py` proves the DB is a byte-exact image of
the "Pump Constraints" sheet across all 206 models and 68 fields (8/0, 0 diffs,
STD 11,786==11,786). The `Custom → C/F` relabel is applied consistently (2,329
rows/20 fields + 4 codep legs) with the DB==sheet audit still 8/0. The API projects
the data exactly (live 6/6, 286+326 checks, 0 fail). Regression is green
(28/0, 13/0, Fybroc 9/9) and Fybroc watermarks are unchanged (4487/28/3638). The
only open items are the disclosed pending-engineering gaps in §6.

## 8. Reproduction commands

```powershell
# relabel is in the loader; reload Dean-only (idempotent, asserts FYBROC unchanged)
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\d110_load_dean_config_v01.py

# exhaustive DB == sheet accuracy (no API needed)
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_config_accuracy.py

# live API cross-check (API on 127.0.0.1:8080; --all for every model, slow)
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_config_accuracy_live.py

# regression (Dean audits need API on 8080; Fybroc gate needs 8080 free)
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_config.py
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_codependencies.py
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\run_all_fybroc_audits.py
```

**Next permitted milestone:** D150 — Exhaustive Dean Regression. **Do not start
D150 without explicit go-ahead.**

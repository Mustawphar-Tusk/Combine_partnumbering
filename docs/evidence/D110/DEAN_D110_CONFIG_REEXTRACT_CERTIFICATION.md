# D110 — Dean Configuration RE-EXTRACT Certification (STD + allowable, full sheet)

**Date:** 2026-08-26
**Milestone:** D110 — Dean Configuration (re-extract / re-certification)
**Type:** VERIFY-ONLY re-extraction. The authoritative loader was re-run against
the exact user-specified column map and full row range; the result was
**byte-identical to the published baseline** (zero schema/loader/data/runtime
change). This document certifies that the published Dean config (STD + allowable
options, per series/size) is a faithful, complete extraction of the authoritative
source.
**Constraint:** family-scoped to DEAN (`PumpFamilyId=1`); **no frozen Fybroc data
was altered** (proven by row-count parity + the full Fybroc gate).

---

## 1. Request

Re-extract Dean's configuration — STD and allowable option values for ALL Dean
series and size combinations — from
`workbooks/Dean/PumpConfiguration_Logic_0.1.xlsm`, sheet **"Pump Constraints"**,
per the user's explicit column map, and the user's explicit row range decision:
**"the full load: 4–209: full sheet"** (206 models).

### User column map (as given)

- Identity: **A** = A Number, **B** = Series, **C** = Size.
- 67 option-group blocks on the sheet, each a contiguous column span with the
  group label on **row 2** and the value headers on **row 3**, data in the rows
  below. Representative spans the user listed (all verified below):
  Pump Configuration **E–L**, Pump Material **N–V**, Casing Material **X–AF**,
  Impeller Trim **CN–GH**, Seal Type **JX–LC**, Frame Size **RC–UH**,
  Crating **WA–WE**.

## 2. What was verified against the sheet (Task 1)

`PumpConfiguration_Logic_0.1.xlsm → "Pump Constraints"`: `max_row=233`,
`max_col=603`. Row 2 = group headers, row 3 = value headers, **data rows 4–209
= 206 models**. Columns A/B/C = A Number / Series / Size.

Every column boundary in the user's map was checked against the live headers and
matched exactly, e.g.:

| Group | Column span | Values | Match |
|-------|-------------|-------:|:-----:|
| Pump Configuration | E–L | 8 | ✓ |
| Pump Material | N–V | 9 | ✓ |
| Casing Material | X–AF | 9 | ✓ |
| Impeller Trim | CN–GH | 99 | ✓ |
| Seal Type | JX–LC | 32 | ✓ |
| Frame Size | RC–UH | 84 | ✓ |
| Crating | WA–WE | 5 | ✓ |

**Row-range note (disclosed):** the written spec referenced identity rows 3–166
(163 models), but rows 167–209 carry real models (RM5140 family @167 … Deanline
@209), not blanks. Per the user's explicit instruction the **full sheet
(rows 4–209, 206 models)** was loaded.

## 3. Loader reconciliation (Task 2) — why no new extractor was written

The existing authoritative loader
`scripts/d110_load_dean_config_v01.py → read_pump_constraints()` **already**
implements the user's exact column map and the full row range:

- It reads row-2 group headers + row-3 value headers and assigns each value column
  to its nearest-left group (the same contiguous-span model the user described).
- `norm_label()` maps every row-2 group label to a canonical SFO field code;
  **all 68 row-2 groups map with 0 skipped** — identical to the user's 67-group
  list plus the `Cooling Plan Routing → COOLING_PLAN_PIPING` alias.
- Per-cell markers: `STD` → standard (`IsStandard=1`), `X` → allowable
  (`IsStandard=0`), blank → not offered for that model. Reload is idempotent,
  Dean-only, and asserts FYBROC unchanged.

Hand-coding 67 literal column spans would have duplicated what the loader already
does correctly, so the loader was used as-is (Tasks 3–6). Re-running it reproduced
the published data exactly.

## 4. Re-load result (Tasks 5–6)

- **Dry-run:** `206 models, 37 series, 68 mapped option fields, 11,786 STD cells`,
  0 unmapped groups; codependencies 775 (leg distribution {2: 588, 3: 22,
  4: 165}).
- **Real reload (Dean-only):** `cfg.SeriesFieldOption` DEAN = **48,063**;
  `cfg.FeasibleConstraint` DEAN = **256** (251 two-leg + 5 three-leg); 519 seal
  codependency tuples held out (pending A1 seal-vocabulary crosswalk);
  `cfg.ConstraintFieldMap` DEAN = 31.
- **Isolation — FYBROC untouched (before == after):** `FeasibleConstraint` 4487,
  `ConstraintFieldMap` 28, `SeriesFieldOption` 3638.
- **Net change:** `git status --porcelain` empty — **zero file/DB diff** vs the
  published baseline. The loader already matched the spec, so the re-extract is a
  certification, not a mutation.

## 5. Live verification (Task 7)

Via `/api/v2/families/DEAN/configurations/resolve-state` (local API on
127.0.0.1:8080). Sampled series across the sheet, including the row-167+ models:

| Series (row) | resolve valid | SIZE field | sizes | after size seed |
|--------------|:-------------:|:----------:|------:|-----------------|
| RA3146 | True | present | 14 | STD seeded 65, no empty-option field |
| PH2110 | True | present | 5  | STD seeded 57, no empty-option field |
| DL200  | True | present | 2  | STD seeded 56, no empty-option field |
| R5140  | True | present | 17 | STD seeded 57, no empty-option field |
| RM5140 (row 167+) | True | present | 17 | STD seeded 51, no empty-option field |
| Deanline (row 209) | True | present | 2 | STD seeded 63, no empty-option field |

Every sampled model resolves valid, exposes its SIZE domain, seeds STD defaults on
size selection, and offers non-empty allowable sets across all fields (no dead
ends). The size field key in `allowable_options` is `SIZE`; each field's value is
a plain list of allowable value strings.

## 6. Regression (Task 8)

Run with `PYTHONUNBUFFERED=1`, API foreground on 8080 for the Dean audits; the
Fybroc gate starts its own temp API (8080 freed first).

| Audit | Result |
|-------|--------|
| `scripts/audit_dean_config.py` | **28 passed, 0 failed** — "models in DB: 206"; STD auto-seed == DB STD (0 mismatched); per-size applicability (API options ⊆ DB offered, 0 leaking); size differentiation; codependency fail-closed (0 leaked); no dead ends |
| `scripts/audit_dean_codependencies.py` | **13 passed, 0 failed** — DB DEAN FeasibleConstraint 256 == workbook non-seal (251 2-leg + 5 3-leg); 519 seal held out; all legs mapped; **FYBROC FeasibleConstraint unchanged 4487**; live fail-closed |
| `scripts/run_all_fybroc_audits.py` | **ALL CORRECTIONS INTACT (9/9)** — selections 2096/2096, feasible 44/0, motor 91/0, identifier 44/0, bom 38/0, quote 22/0, free_config 32/0, pricing 47/0, motor_cpq 37/0 |

**Isolation confirmed:** FYBROC `FeasibleConstraint` 4487 and selections 2096
unchanged across the re-extract and both gates.

## 7. Gaps / what could NOT be verified (disclosed, non-blocking)

- **519 seal codependency tuples remain DEFERRED** (held out of enforcement)
  pending the A1 seal-vocabulary crosswalk (long descriptive names in
  `Codependencies` vs short canonical `Type N` in `Pump Constraints`). This is the
  same pre-existing, documented gap (see D155 / roadmap v1.26); the re-extract did
  not change it.
- **Casing Heat Jacket** and **Shipping Gasket** are offered options in the config
  but by prior user instruction do **not** drive the wet-end PN (handled in the
  wet-end numbering allow-list — a separate concern, unchanged here).
- STD auto-adjust for all segments remains deferred per the earlier user decision
  ("we will implement standard fields later"); unchanged by this re-extract.

## 8. Exit-gate decision

> Dean config = complete, authoritative extraction of Pump Constraints STD +
> allowable per (series, size); options project correctly; invalid combinations
> fail closed; no unexplained empty-option state; Fybroc untouched.

**PASS.** The authoritative loader re-extracts exactly the user's column map over
the full sheet (rows 4–209, 206 models, 68 fields, 11,786 STD cells), the live API
projects STD + allowable correctly for sampled series across the whole sheet, the
Dean audits pass (28/0, 13/0), and the Fybroc regression gate is ALL CORRECTIONS
INTACT (9/9) with FYBROC row counts unchanged. The re-extract produced zero diff
(the published data already matched the spec), so this milestone step is a
verification/certification with no code or data mutation.

## 9. Reproduction commands

```powershell
# dry-run / reload (Dean-only, idempotent)
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\d110_load_dean_config_v01.py --dry-run
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\d110_load_dean_config_v01.py

# Dean audits (API on 127.0.0.1:8080)
$env:PYTHONPATH="."; $env:CONFIGURATION_TOKEN_SECRET="<secret>"; .\.venv\Scripts\python.exe -m uvicorn src.api.app:app --host 127.0.0.1 --port 8080
$env:PYTHONPATH="."; $env:PYTHONUNBUFFERED="1"; .\.venv\Scripts\python.exe scripts\audit_dean_config.py
$env:PYTHONPATH="."; $env:PYTHONUNBUFFERED="1"; .\.venv\Scripts\python.exe scripts\audit_dean_codependencies.py

# cross-family regression gate (needs 8080 free; starts its own temp API)
$env:PYTHONPATH="."; $env:PYTHONUNBUFFERED="1"; .\.venv\Scripts\python.exe scripts\run_all_fybroc_audits.py
```

**Next permitted milestone:** D150 — Exhaustive Dean Regression. **Do not start
D150 without explicit go-ahead.**

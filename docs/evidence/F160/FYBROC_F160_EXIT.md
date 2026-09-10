# F160 — Fybroc Excel Oracle Harness — EXIT

**Milestone:** F160 (Excel Oracle Harness)
**Roadmap anchor:** docs/PROJECT_MASTER_ROADMAP.md, Section 6, Milestone F160
**Exit gate (roadmap):** *"Repeatable Excel-oracle tests operate safely against
disposable workbook copies."*

## What F160 achieves

A trustworthy, safe, repeatable mechanism that drives **real Microsoft Excel**
with the authoritative `workbooks/Fybroc/Nomenclature_V6.xlsm` workbook as an
**independent engineering oracle**, and compares what the workbook's own formulas
produce against what our API/SQL produces. This is the harness F170 (exhaustive
regression) builds on. F160 proves the harness *works and is safe* — not
exhaustive coverage (that is F170).

## Decisions (agreed with product owner)

- **Compare scope (b): Part Number + segment codes.** Specifically the leading
  **identity** — the leading PN segment (`F` + series + size + material + trim)
  and the four identity segment codes (series/size/material/trim). That is the
  part both systems derive independently from the same core selection, so it is a
  genuine cross-check. Downstream option/seal/motor segments depend on option
  selections that differ between workbook defaults and the API's STD walk;
  exhaustive lock-step comparison of those is F170.
- **Oracle workbook:** `Nomenclature_V6.xlsm` (authoritative nomenclature).
- **Approach A (real Excel via COM)** — chosen and succeeded; the fallback
  (workbook-extracted truth table) was not needed.

## The harness

- `scripts/fybroc_excel_oracle.py` — drives a **disposable copy** of the workbook
  through a **dedicated Excel instance** (`DispatchEx`, so it never attaches to or
  disturbs a user's open Excel), populates the "Smart Number" sheet inputs,
  recalculates, and reads back the Part Number + all segment codes. Handles both
  orientations. Writes `docs/evidence/F160/FYBROC_EXCEL_ORACLE_RESULTS.{json,txt}`.
- `scripts/fybroc_oracle_compare.py` — runs the Excel oracle **and** the API/SQL
  resolve over the same representative matrix and asserts the leading identity +
  identity segment codes match. Writes `FYBROC_ORACLE_COMPARE.{json,txt}`.

### Ground truth established (Smart Number sheet)

Verified by COM inspection:

| Flow | Series in | Flange in | Size/Mat/Trim in | Compact PN | Segment row |
|------|-----------|-----------|-------------------|-----------|-------------|
| Horizontal | (14,6) | (15,6) | (14,7)/(14,8)/(14,9) | D9 | 13 |
| Vertical   | (39,6) | (40,6) | (39,7)/(39,8)/(39,9) | D34 | 38 |

Segment columns (both flows): brand=4, series=5, size=7, material=8, trim=9,
pump_options=11, seal_mfg=15, seal_assy=16, options=19, frame=22, motor_assy=23,
motor_mods=26, testing=29.

### Data-type rule (why the old harness returned #N/A)

The workbook's XLOOKUP / dynamic-array formulas are type-sensitive. Empirically
confirmed:

- SERIES `2530 / 3000 / 5500` must be written as an **integer**; every other
  series must be written as **text**.
- SIZE and TRIM must always be written as **text** (force `NumberFormat='@'`),
  else Excel coerces e.g. `6.000` → `6` and the trim XLOOKUP misses.

Writing values without forcing these formats made the horizontal series/trim
segments return `#N/A` (the old F170 evidence showed 0/10 — an *oracle-side*
failure, not a SQL failure). With the type rule applied, **6/6 representative
cases compute** across horizontal and vertical.

## Safety (exit-gate requirement)

- The authoritative workbook is **never** opened for write and **never** modified.
- Every run operates on a fresh **disposable copy** in a temp dir, deleted after.
- A **dedicated** Excel instance is used (`DispatchEx`).
- **No VBA macros** are executed — pure formula recalculation only.

## Result

Excel oracle vs API/SQL identity comparison — **6/6 PASS**:

| Case | Excel leading | API leading |
|------|---------------|-------------|
| 1500 / ANSI / 1x1.5x6 / VR-1 / 6.000 | FA11CA | FA11CA |
| 1500 / ANSI / 1x2x10 / VR-1A / 9.250 | FA35FC | FA35FC |
| 1530 / ANSI / 1.5x3x8 / VR-1 / 7.000 | FB61DA | FB61DA |
| 1600 / ANSI / 2x3x6 / VR-1 / 5.500 | FC71BE | FC71BE |
| 3000 / ANSI / 1x1.5x6 / VR-1 / 6.000 | FF11CA | FF11CA |
| 5500 / ANSI / 1x2x10 / VR-1 / 8.000 (vertical) | FG31EA | FG31EA |

## Bug the oracle caught (and the fix)

Building the oracle immediately paid off: it surfaced a **real F150 defect**.

**Symptom:** one case returned HTTP 503, masking a SQL
`Violation of UNIQUE KEY constraint` on `cfg.ConfiguredProduct.PartNumber`
(duplicate `FA11CA-0001-S03-01-1400S-XXX-00`).

**Root cause:** the resolve endpoint built the canonical configuration JSON with
`json.dumps(body.selections)` — **key order depended on how the client assembled
the request**. The configuration *signature* is a SHA-256 of that JSON, and reuse
is keyed on the signature. So the **same pump configuration**, sent with a
different key order, produced a **different signature** → reuse missed → the
INSERT collided with the existing row's `UNIQUE(PartNumber)`.

**Fix (recommendation 3, per product owner):** canonicalize the JSON with
`sort_keys=True, separators=(",", ":")` in `src/api/v2_routes.py` before hashing.
The signature is now a deterministic function of the configuration **content**,
independent of key order. SQL re-hashes the exact same canonical bytes via
`HASHBYTES`, so Python↔SQL signature parity is preserved.

**Data migration:** legacy `cfg.ConfiguredProduct` rows carried old,
order-dependent signatures. Those rows are regenerable test data with **zero**
downstream references (`cfg.BOMHeader` and `quote.QuoteLine` were empty), so
`scripts/migrate_normalize_configured_products.py` (guarded, `--confirm`, refuses
if any row is referenced) cleared the 19 Fybroc rows; they repopulate with
normalized signatures on next resolve.

### Product-owner rule verified

> PN and SKU are reusable when the same configuration is selected, and differ
> when the configuration is different.

Confirmed end-to-end:

- same config, same order → same PN + SKU (existing=True)
- same config, **different key order** → same PN + SKU (existing=True) *(the
  previously-broken case)*
- different config (VR-1 → VR-1A) → different SKU + signature

## Regression gate

`scripts/run_all_fybroc_audits.py` → **ALL CORRECTIONS INTACT** after the fix:
selections 2096=2096, feasible 14/14, motor 91/91, identifier parity 36/36.

## Notes / follow-ups (not blocking F160)

- The Excel oracle is Windows + Excel + pywin32 dependent, so it is **not** added
  to `run_all_fybroc_audits.py` (which must stay runnable headless). It is an
  on-demand oracle, run on a machine with Excel; F170 will drive it at scale.
- The deployed `cfg.usp_GenerateSKU` (format `F<series>-<8hex><versionLetter>`)
  differs from the older source in `sql/22_Create_Identifier_Generation.sql`
  (format `F<series>-V1-<8hex>`). The deployed one is authoritative and matches
  stored SKUs; the source drift should be reconciled in a later hardening pass.

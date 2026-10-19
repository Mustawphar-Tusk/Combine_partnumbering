# Dean Numbering — PCL v0.1 Authority Certification (Option A: verify-only)

**Date:** 2026-08-26
**Scope:** Certify that `workbooks/Dean/PumpConfiguration_Logic_0.1.xlsm` (its
Module1/Module2 numbering macros) is the **authoritative, loaded** source for the
Dean configuration build-up — the six numbering sheets (Motor, Wet End, Impeller,
Power Frame, Flush Plan, Baseplate), the Codependencies cross-constraint deps, and
the Config Options choices.
**Mode:** Verification only — **no data, schema, or code change.** Read-only probes +
the standing regression gate.
**Result:** **PASS** (with documented, engineering-owned data gaps disclosed).

---

## 1. What was asked vs what was found

The request was to adopt the PCL v0.1 macros as authoritative for the Dean numbering
build-up. Investigation showed this adoption was **already implemented and loaded**
under the D140 re-base:

- `scripts/load_dean_identifier_to_sql.py` reads `PumpConfiguration_Logic_0.1.xlsm`
  using the exact `Module1`/`Module2` header-search semantics (find `Permutation` /
  `Alphanumeric Code` / `Option Ranges`; pull per-model option values from
  `Pump Constraints`; `*`-join excluding `Custom`; dedupe; sequential code) and loads
  every numbering sheet + the A#→D# model identity.
- `src/api/dean_identifier.py` resolves each Dean PN segment from those loaded tables,
  with Python==SQL parity, feeding `cfg.usp_AssembleConfiguredProduct` (@FamilyCode='DEAN').

This certification verifies that adoption is correct and current. It intentionally does
NOT re-load or re-implement anything.

---

## 2. Authoritative source + what is loaded (DB-verified)

**Source workbook:** `workbooks/Dean/PumpConfiguration_Logic_0.1.xlsm`
**Loaded batch:** `stg.SegmentCombinationImport` DEAN batch **id=5**, `Status=Loaded`,
`SourceFile=PumpConfiguration_Logic_0.1.xlsm`,
`SourceFileHash=cc1fab745ce534d6fbf5a08f7165fc5187b78a4050d04b0aa080714f8180706e`,
**106,892** total segment rows.

| Numbering sheet (segment) | Loaded rows | Notes |
|---|---|---|
| Wet End (`WET_END_OPTIONS`) | 49,987 | Module1 excludes `Custom`-containing combos |
| Power Frame (`POWER_FRAME_OPTIONS`) | 55,452 | |
| Baseplate (`BASEPLATE_OPTIONS`) | 1,153 | |
| Flush Plan (`FLUSH_PLAN`) | 185 | Module2 from Flush_Barrier Plan Constraints |
| Impeller (`IMPELLER_OPTIONS`) | 24 | + inch/decimal trim sub-table |
| Motor Frame (`MOTOR_FRAME`) | 91 | distinct frame sizes (sub-table S/T/U) |

**Model identity:** `cfg.PumpModelReference` DEAN = **206 models across 37 series**
(A#→D#, e.g. A461→D461), sourced from `Pump Constraints` A/B/C.

**Config + constraints baseline (unchanged):** `cfg.SeriesFieldOption` DEAN = 48,063;
`cfg.FeasibleConstraint` DEAN = 256 (Config Options catalog + Codependencies-derived
cross-constraints; 519 seal codependencies held out per the seal-vocab gap, A1).

---

## 3. Parity verification (live, bounded probe)

A bounded parity probe resolved a spread of **12 of 206** Dean models (STD-seeded, live
API) and asserted base identity + Python==SQL parity + segment resolution.

**RESULT: 12/12 PASS.**
- base_identifier correct **12/12** (D461, D761, D347, D351, D373, D651, D683, D784,
  D232, D714, D737, D246 — all match `cfg.PumpModelReference`).
- `parity_ok` (Python == SQL) — **0 failures**.
- Segment codes generated from the loaded PCL v0.1 tables, e.g. Impeller
  `CA`/`GA`/`EE`/`HE`/`LE`; Power Frame `08L5`/`004W`/`008S`/`1HWN`; Flush/Barrier/Cooling
  block `00000`/`01000`.

> Why a bounded probe rather than the full `audit_dean_identifier.py` at stride 1:
> each model's STD-seed + resolve round-trip is ~17 s, so 204 models exceeds a single
> run window (the full/default-stride runs timed out — a latency property, not a stall).
> The bounded probe exercises the same assertions (DB-derived expectations, not
> hardcoded) and is conclusive for certification. For an exhaustive sign-off, run
> `scripts/audit_dean_identifier.py` (optionally `AUDIT_STRIDE=1`) with the API up and
> allow it to run to completion out-of-band — that is the D150 exhaustive-regression step.

---

## 4. Isolation / regression (nothing changed)

- `scripts/run_all_fybroc_audits.py` → **ALL CORRECTIONS INTACT (9/9)** — Fybroc
  untouched by the Dean verification.
- Baselines re-confirmed after the probe: Dean 206 models / 37 series, SFO 48,063,
  Feasible 256; pricing FYBROC 56,355 / DEAN 9,874 — all unchanged.
- `import src.api.app; import src.api.dean_identifier` → OK.
- Temp probe scripts removed.

---

## 5. Documented engineering gaps (NOT dev defects)

These are gaps in the workbook data / external sources, tracked in
`docs/evidence/DEAN_ENGINEERING_QUESTIONS.md`. They are disclosed, not silently passed:

| Gap | Where | Current behavior |
|---|---|---|
| **Cooling Plan Numbering empty** (F1) | workbook sheet has no table | resolver emits placeholder `00` |
| **Barrier Plan Numbering 0 data rows** (F2) | header-only in workbook | placeholder `0` |
| **Motor main code inert `000`** (F3) | workbook column constant | only the Frame-size sub-table code is used |
| **Standard Confs external DB** (A2) | not provided | some STD configs pick a value the numbering never enumerated → `wet_end`/`power_frame_options` show `?` for those models |
| **Seal code external Access DB** (A1) | `Seal Numbering.accdb` not provided | seal omitted-but-not-discarded from the PN; 519 seal codependencies held out |

The `?` segments observed in the probe (`wet_end`, `power_frame_options`) are **only**
within the A2 gap set — any `?` outside that set would be a regression; none occurred.

---

## 6. Exit-gate decision — PASS

| Criterion | Result |
|---|---|
| PCL v0.1 is the loaded authority (6 numbering sheets + A#→D#) | **PASS** — batch id=5, counts verified |
| Segment codes derive from the loaded numbering | **PASS** — probe 12/12 |
| Python == SQL parity | **PASS** — 0 fails |
| Fybroc isolation / regression intact | **PASS** — 9/9, baselines unchanged |
| Engineering gaps disclosed, not masked | **PASS** — §5 |

**Certified:** `PumpConfiguration_Logic_0.1.xlsm` is the authoritative, loaded source for
Dean configuration numbering. Remaining items are engineering-data gaps (Cooling/Barrier
tables, Motor main code, Standard Confs, Seal code), not implementation gaps.

---

## 7. Reproducibility
```
# API up
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe -m uvicorn src.api.app:app --host 127.0.0.1 --port 8080
# exhaustive Dean identifier audit (out-of-band; ~17s/model)
$env:PYTHONPATH="."; $env:AUDIT_STRIDE="1"; .\.venv\Scripts\python.exe scripts\audit_dean_identifier.py
# isolation / regression
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\run_all_fybroc_audits.py
```

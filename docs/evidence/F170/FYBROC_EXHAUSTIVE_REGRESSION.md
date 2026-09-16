# F170 — Fybroc Exhaustive Regression

**Date:** 2026-08-26
**Code baseline:** commit `70c69d2` (branch `feature/m021-shared-excel-production-hardening`)
**Metadata publication:** id=2 `F140-corrections-v1`
**Pricing publication:** id=7 `FYBROC-REV04-MERGE-20260914-V1`
**Status:** ✅ PASS — zero unexplained engineering failures

> This document supersedes the earlier `FYBROC_REGRESSION_RESULTS.txt/.json`
> in this folder, which captured a stale Excel-COM oracle run (0/10, horizontal
> COM VLOOKUP limitation) against an outdated part-number format. The current
> authoritative regression is the three-layer package below.

---

## 1. Objective

Prove Fybroc configuration completeness across every supported series and the
full configure → constrain → resolve → price → BOM → quote path, with every
established correction guarded by a re-runnable audit.

## 2. Regression package (three layers)

### 2.1 Correction gate — `scripts/run_all_fybroc_audits.py`

**RESULT: ALL CORRECTIONS INTACT.**

| Audit | Result | Guards |
|-------|--------|--------|
| audit_selections_vs_db.py | CLEAN | Selections X/STD applicability + V6 flange authority vs DB (2096 rows) |
| audit_feasible_constraints.py | 14 / 14 | Feasible-constraint fail-closed (NOT-ALLOWED / ALLOW-LIST / MIXED) + valid walks |
| audit_motor_constraints.py | 91 / 91 | All 4 Motor Constraint relationships across 7 motor-bearing series |
| audit_identifier_parity.py | 44 / 44 | SQL-authoritative PN/SKU; Python==SQL parity; SKU↔PN 1:1; reuse determinism |
| audit_bom_engine.py | 38 / 38 | BOM generation + signature parity (python==sql); BOM reuse |
| audit_quote_engine.py | 22 / 22 | Quote line/total integrity, persistence, reproducible render |
| audit_free_config.py | 32 / 32 | Free-edit resolve-state: STD seed, omni-directional allowable, non-destructive conflict reporting |

### 2.2 Excel oracle — `scripts/fybroc_oracle_compare.py`

**RESULT: 6 / 6** — actual Microsoft Excel calculation == API/SQL identity.

| Case | Excel | API | Match |
|------|-------|-----|-------|
| 1500 / ANSI / 1x1.5x6 / VR-1 / 6.000 | FA11CA | FA11CA | ✅ |
| 1500 / ANSI / 1x2x10 / VR-1A / 9.250 | FA35FC | FA35FC | ✅ |
| 1530 / ANSI / 1.5x3x8 / VR-1 / 7.000 | FB61DA | FB61DA | ✅ |
| 1600 / ANSI / 2x3x6 / VR-1 / 5.500 | FC71BE | FC71BE | ✅ |
| 3000 / ANSI / 1x1.5x6 / VR-1 / 6.000 | FF11CA | FF11CA | ✅ |
| 5500 / ANSI / 1x2x10 / VR-1 / 8.000 | FG31EA | FG31EA | ✅ |

### 2.3 Per-series exhaustive batch — `scripts/audit_series_batch.py`

Drives the exact two calls the UI makes — `POST /configurations/resolve-state`
(set the option) and `POST /configured-products/resolve` (resolve + price) — for
every option of every field (large fields sampled at cap=40), isolated and
cumulative, for all 10 series. **RESULT: 0 errors across 1,466 resolve-state +
1,466 resolve/pricing calls.**

| Series | Fields | resolve-state calls | resolve calls | Errors |
|--------|-------:|--------------------:|--------------:|-------:|
| 1500 | 46 | 221 | 221 | 0 |
| 1530 | 40 | 175 | 175 | 0 |
| 1600 | 45 | 189 | 189 | 0 |
| 1630 | 39 | 160 | 160 | 0 |
| 2530 | 29 | 142 | 142 | 0 |
| 3000 | 42 | 176 | 176 | 0 |
| 5500 | 36 | 239 | 239 | 0 |
| 5530 | 26 | 132 | 132 | 0 |
| 7500 |  4 |  22 |  22 | 0 |
| 8500 |  4 |  10 |  10 | 0 |

## 3. Test-dimension coverage (F170 exit gate)

| Dimension | Covered by |
|-----------|-----------|
| Every supported series (10) | Batch + gate |
| Horizontal + vertical | 1500/1530/1600/1630/2530/3000 (H), 5500/5530 (V) |
| All sizes / material families | Batch (every ALT_SIZE, every PUMP_MATERIAL option) |
| Standard + optional configurations | STD seed + every option per field |
| Seals / motors / motor mods / coupling / baseplate / testing | Batch (all option fields) + resolve component pricing |
| Pricing + adders | resolve `component_pricing` (found / C/F) each config |
| Invalid combinations | Feasible + free_config audits (fail-closed / conflict report) |
| Configuration reuse | identifier + BOM audits (existing_configuration / existing_bom) |
| Part Number / SKU / API response | identifier parity 44/44 + oracle 6/6 |
| Configuration signature | identifier + BOM signature parity |

## 4. Formally accepted deviations

These are known, engineering-acknowledged data realities — not engineering
failures — and are documented so they are explicit rather than silent.

1. **7500 / 8500 — sparse metadata.** Only 4 configurable fields each (vs 26-46
   on other series); pricing largely Contact-Factory. Configuration resolves
   correctly for what is defined. Engineering to supply fuller config/pricing
   in a future revision.
2. **6000 / 7530 — no configuration data.** Not present in the active metadata
   publication; require engineering to define options before support.
3. **Vertical motor_assy / horizontal seal_assy combo-table gaps.** Some SFO
   values do not match a MOTOR_ASSEMBLY / SEAL_ASSEMBLY combination row (data
   gap, not architecture); such segments resolve to a placeholder rather than
   failing.
4. **Excel COM oracle — horizontal-series limitation.** Data-validation VLOOKUPs
   in Nomenclature_V6 fail when series/flange are written via COM without the
   full Named-Range dependency chain. The API/SQL is the authority; the oracle
   confirms parity on the cases it can drive (6/6). Superseded operationally by
   the API-driven flow.
5. **Pricing scope (Rev0.4 adoption).** Full Rev0.4 pricing was adopted for 1500
   & 5500; other series retain Price-Estimator pricing, so their adders show
   Contact-Factory where Rev0.4 did not supply a value. This is the agreed
   option-2b scope, tracked per-config via `component_pricing`.

## 5. Exit gate

> Zero unexplained engineering failures. All accepted deviations formally documented.

**MET.** Correction gate ALL CORRECTIONS INTACT; oracle 6/6; per-series batch
0 errors across all 10 series; deviations enumerated in §4.

**Next milestone:** F180 — Fybroc Signoff & Freeze.

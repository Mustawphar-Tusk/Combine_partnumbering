# D110 — Dean segment numbering: nearest-combination snap (wet-end `????` fix)

**Date:** 2026-08-26
**Milestone:** D110 — Dean Configuration (segment PN resolution fix)
**Type:** Dean-only runtime change (`src/api/dean_identifier.py`) + one-time
cleanup of stale pre-fix configured products. No schema/loader change. Fybroc
frozen (byte-for-byte unchanged; identifier parity verified).

---

## 1. Symptom (reported)

A chosen Dean series resolved with an unbuildable part number:
`DEAN · RA3146 · D770-????-EE01-000S-00000-0000-000000-00-000000` — the wet-end
4-char segment was `????` (unresolved).

## 2. Root cause

The Dean PN wet-end segment is resolved by an EXACT lookup of the built
combination string against the 49,987 enumerated Wet End Numbering combinations.
For RA3146 the STD-seeded wet-end combination is:

```
(22) Ductile Iron * (22) Ductile Iron * NPT Plug * NPT Discharge * Grafoil *
300# Raised * Not Required * Hard Iron * Yoke Foot * NONE
```

That exact combination is **not enumerated**. The nearest coded rows differ by a
single field — **CASING_MOUNTING**: the Wet End Numbering sheet codes that
wet-end config only with `Not Required` (code `004L`) or `Required` (`004P`), never
with `Yoke Foot`. So two authoritative sheets disagree: **Pump Constraints** marks
`CASING_MOUNTING = Yoke Foot` standard for RA3146, but **Wet End Numbering** has no
buildable row with Yoke Foot for that config. The exact lookup missed → the
segment returned the error placeholder `????`. The same class can affect
POWER_FRAME and BASEPLATE.

## 3. Fix (option A — PN snaps to nearest enumerated combination)

Per the product decision (option A, extended to Power Frame and Baseplate): the
**displayed configuration keeps its authoritative Pump-Constraints STD value**;
only the **part number** snaps to the nearest enumerated combination so a segment
never emits `????`.

`src/api/dean_identifier.py`:
- Added `_seg_parts()` (the per-position segment values in column order, defaults
  applied, lowercased) and `_nearest_seg_code()` — scores every enumerated row of
  the segment by agreement with the selected/STD values: the first (anchor/
  material) field weighted, then number of matching positions, ties broken to the
  earliest (standard) sheet row. It returns an **existing enumerated row's code**
  (never invents one), and does **not** mutate `selections`.
- `resolve_segments().table()`: when the exact `_seg_lookup` misses AND the
  segment is one of `WET_END_OPTIONS`, `POWER_FRAME_OPTIONS`, `BASEPLATE_OPTIONS`,
  it returns `_nearest_seg_code(...)`; other segments keep the error placeholder.

Important implementation detail (a bug caught during verification): the stored
`CombinationKey` tokens are **original-cased** while the built parts are
lowercased, so the scorer compares **case-insensitively** (lowercasing both
sides). Without this the scorer matched nothing and fell to the lowest-code row
(`0000`); with it, RA3146 correctly snaps to `004L` (the single-field-different
nearest).

Parity: `cfg.usp_AssembleConfiguredProduct` reads the resolved `wet_end` code from
the payload (it does not re-resolve), so the Python-snapped code flows straight
through and python==SQL parity holds.

### 3a. One-time stale-data cleanup

Reuse in `cfg.usp_AssembleConfiguredProduct` is **signature-keyed** (via
`usp_GetOrCreateConfiguredProduct`), so configurations persisted BEFORE this fix
kept returning their stored `????` / `0000` part numbers even after the resolver
was corrected. Deleted the stale Dean configured products: **122 with `????` in
the PN** (0 quote-line / BOM references) plus 3 pre-fix `0000`-wet-end session
products. Fybroc `cfg.ConfiguredProduct` untouched (1196). These were session/test
artifacts, not a published deliverable; the corrected resolver re-persists the
right PN on next resolve.

## 4. Verification

New re-runnable audit `scripts/audit_dean_wet_end_resolve.py` — **32 passed,
0 failed** across 8 diverse models (incl. RA3146 and row-167+ RM5140 / RWAV4096):
for each, WET_END / POWER_FRAME / BASEPLATE resolve to a code that is non-`????`,
width-correct, and a **real enumerated combination's Alphanumeric Code**; the full
PN contains no `?`; and python==SQL parity holds.

Live spot-checks (all `parity_ok=True`, 0 failed segments, no `?`):
- **RA3146** / 1.5x3x10: `D770-004L-GA01-000S-...` (wet-end `004L`, the dist-1
  nearest to the STD seed — correct).
- RA2096 `000R`, CNV206 `1SW1`, R5140 `0VU9`, RM5140 `0A3K` (power `1HWN`).

**Regression (all green):** `audit_dean_wet_end_resolve` 32/0,
`audit_dean_baseplate_combos` 23/0, `audit_dean_baseplate_coupling` 301/0,
`audit_dean_flush_plan` 15/0, `audit_dean_std_consistency` 7/7,
`audit_dean_config` 28/0, `audit_dean_codependencies` 13/0,
`run_all_fybroc_audits` **ALL CORRECTIONS INTACT 9/9** — including
`audit_identifier_parity` PASS (critical: `dean_identifier.py` changed, and Fybroc
PN parity is unaffected because the snap is gated to the three Dean segments).

**Isolation:** Fybroc `cfg.ConfiguredProduct` 1196 unchanged; 0 Dean products with
`????` remain; FYBROC watermarks unchanged (FeasibleConstraint 4487,
ConstraintFieldMap 28, SeriesFieldOption 3638, stg 300608).

## 5. Notes / disclosed

- The snap is **numbering-only**: the configurator still displays the
  authoritative Pump-Constraints STD (e.g. CASING_MOUNTING = Yoke Foot); the PN
  uses the nearest buildable wet-end code. Where the displayed config and the
  coded combination differ on a field, that reflects a genuine disagreement
  between the Pump Constraints and Numbering sheets (a source-reconciliation item
  for engineering); the PN is always buildable and parity-correct.
- Scope limited to WET_END_OPTIONS / POWER_FRAME_OPTIONS / BASEPLATE_OPTIONS (the
  three table-backed combination segments the user named). Other segments keep
  their existing placeholders.

## 6. Exit-gate decision

> A chosen Dean series resolves to a complete, buildable part number with no
> `????`; each table-backed segment resolves to a real enumerated combination
> code; python==SQL parity holds; Fybroc untouched.

**PASS.** RA3146 (the reported case) now resolves to `D770-004L-GA01-000S-...`
with parity True, and `audit_dean_wet_end_resolve.py` is 32/0 across the sample.
Regression is green (Dean audits + Fybroc gate 9/9 incl. identifier parity) and
Fybroc is frozen.

## 7. Reproduction commands

```powershell
# API on 127.0.0.1:8080
$env:PYTHONPATH="."; $env:CONFIGURATION_TOKEN_SECRET="<secret>"; .\.venv\Scripts\python.exe -m uvicorn src.api.app:app --host 127.0.0.1 --port 8080

# segment-resolve audit
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_wet_end_resolve.py

# regression
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_config.py
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_codependencies.py
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\run_all_fybroc_audits.py
```

**Next permitted milestone:** D150 — Exhaustive Dean Regression (still parked per
the user; further configuration work precedes it). Do NOT start D150 without
explicit go-ahead.

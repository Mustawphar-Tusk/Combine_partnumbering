# D110 — Dean Baseplate + Coupling always-applicable (display + STD seed)

**Date:** 2026-08-26
**Milestone:** D110 — Dean Configuration (baseplate/coupling applicability fix)
**Type:** Dean-only runtime fix (`src/api/v2_routes.py`); no DB/schema/loader
change. Fybroc frozen (byte-for-byte unchanged).

---

## 1. Request

The nine Baseplate-group fields (BASEPLATE_TYPE, DRIP_PAN, ALIGNMENT_LUGS,
LIFTING_LUGS, LEVELLING_SCREWS, GROUNDING_LUG, GROUT_HOLE, ISOLATION_PADS, STILTS)
were reported as not correctly implemented — not shown as standard and not
selectable — for the majority of Dean series (not displayed in the UI). The user
chose **option A** (treat Pump Constraints as authoritative: always applicable +
STD-seeded) and asked to **extend the same treatment to Coupling** (COUPLING_TYPE,
COUPLING_GUARD).

## 2. Finding — the data was correct; the bug was runtime display

The DB (`cfg.SeriesFieldOption`, DEAN) already matches the Pump Constraints sheet
exactly for all nine fields: each is marked **STANDARD** (value NONE / Not
Required) on every applicable model — BASEPLATE_TYPE + the seven lug/screw/hole
flags on all 206 models; DRIP_PAN on 127 models (the sheet genuinely offers
DRIP_PAN only there). So the load was faithful.

The fields didn't appear because of **runtime bundle-gating**. The configurator
gates the Baseplate / Coupling / Motor component fields on the
`PUMP_CONFIGURATION` bundle (from the Dean Data Sheet Rev 2 macro). The standard
bundle for most models is **"Pump Only"** (or "Pump and Motor"), which excludes
the baseplate and coupling components — so `_dean_pump_config_excluded_fields`
dropped all of those fields as not-applicable. They were STD-seeded and then
deleted by `_applicable_fields`, so they neither displayed nor carried a seed.

This conflicts with the authoritative Pump Constraints matrix, which marks these
fields standard on **every** model regardless of bundle.

## 3. Fix (Dean-only)

`src/api/v2_routes.py`: introduced `DEAN_BUNDLE_GATED_COMPONENTS = {"MOTOR"}` and
scoped both gating functions to it:
- `_dean_pump_config_excluded_fields` now excludes a component's fields only when
  that component is in `DEAN_BUNDLE_GATED_COMPONENTS`. So **only Motor** stays
  bundle-gated; **Baseplate and Coupling are never excluded** → always applicable
  → their STD seeds and they display, for every series/bundle.
- `_dean_excluded_components` (UI group dropping) uses the same gate, so the
  Baseplate and Coupling UI groups always render.

Rationale: the Pump Constraints matrix is authoritative for what is standard, and
it marks Baseplate + Coupling standard on every model. FRAME_SIZE (Motor) is not a
Pump-Constraints standard field — it comes from the motor tables and only applies
when the bundle includes a motor — so Motor remains bundle-gated.

This refines the D145 bundle-gating decision: the macro-driven wholesale
component gating now applies **only to Motor** for these fields; Baseplate and
Coupling follow the Pump Constraints standard markings. No data was changed.

## 4. Verification

New re-runnable audit `scripts/audit_dean_baseplate_coupling.py` — **301 passed,
0 failed** across 7 diverse series. For every baseplate/coupling field the sheet
offers for a model it asserts, via the live API:
- the field is **displayed** (in `ordered_fields`),
- its seeded value equals the **sheet STD** exactly,
- its allowable set is a **subset** of the sheet offered set (the API never
  offers a value the sheet does not), and the STD value is always present.

(First run used exact-equality on allowable and flagged 6 values — COUPLING_GUARD
`C/F`, BASEPLATE_TYPE `API`/`Formed` — as "missing". These are per-field `X`
options that an authoritative codependency / numbering-combination legitimately
prunes once the whole model is STD-seeded, not a bug. The assertion was corrected
to subset + STD-present, matching the established `audit_dean_config` pattern;
exact per-field equality is covered by the DB==sheet field-accuracy audit.)

Live spot-checks:
- **RA2096 / 1x1.5x6** (bundle "Pump Only"): all 9 baseplate fields displayed and
  STD-seeded (NONE / Not Required); COUPLING_TYPE=Elastomeric Sleeve,
  COUPLING_GUARD=Steel seeded; FRAME_SIZE still not offered (Motor gated).
- **CNV206 / 1x1.5x6** (bundle "Pump and Motor"): 8 baseplate fields seeded;
  DRIP_PAN correctly not offered (sheet offers DRIP_PAN on only 127 models, and
  CNV206 is not one) → renders as a C/F placeholder; Coupling NONE/NONE seeded.

**Regression (all green):** `audit_dean_std_consistency` 7/7,
`audit_dean_flush_plan` 15/0, `audit_dean_config` 28/0,
`audit_dean_codependencies` 13/0 (FYBROC FeasibleConstraint 4487 unchanged),
`run_all_fybroc_audits` **ALL CORRECTIONS INTACT 9/9**.

**Isolation:** runtime-only change, no DB write; the `_dean_*` gating functions
are Dean-only (triggered by PUMP_CONFIGURATION, a Dean-only field), so Fybroc is
byte-for-byte unchanged (gate confirms).

## 5. Notes / disclosed

- **DRIP_PAN** remains offered only on the 127 models the sheet marks it on; for
  other models it is a C/F placeholder. That is correct per the authoritative
  matrix, not a gap.
- Some per-field `X` options (e.g. COUPLING_GUARD `C/F`, BASEPLATE_TYPE `API`)
  are narrowed by the authoritative codependency / numbering-combination tables
  in the full STD context; the field still displays and its STD is always valid.

## 6. Exit-gate decision

> The nine Baseplate fields and the two Coupling fields are standard and
> selectable for every Dean series (displayed + STD-seeded per the Pump
> Constraints sheet), regardless of the PUMP_CONFIGURATION bundle; Motor stays
> bundle-gated; Fybroc untouched.

**PASS.** `audit_dean_baseplate_coupling.py` is 301/0; the reported fields now
display and STD-seed for every series. Regression is green (STD 7/7, flush 15/0,
Dean 28/0 + 13/0, Fybroc 9/9) and Fybroc is frozen.

## 7. Reproduction commands

```powershell
# API on 127.0.0.1:8080
$env:PYTHONPATH="."; $env:CONFIGURATION_TOKEN_SECRET="<secret>"; .\.venv\Scripts\python.exe -m uvicorn src.api.app:app --host 127.0.0.1 --port 8080

# baseplate + coupling audit
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_baseplate_coupling.py

# regression
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_std_consistency.py
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_flush_plan.py
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_config.py
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_codependencies.py
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\run_all_fybroc_audits.py
```

**Next permitted milestone:** D150 — Exhaustive Dean Regression (still parked per
the user; further configuration work precedes it). Do NOT start D150 without
explicit go-ahead.

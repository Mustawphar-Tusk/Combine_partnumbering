# U150 — Free-Edit Configuration (omni-directional, non-destructive)

## Goal

Make the configurator UI free-edit instead of a strict top-down walk:

1. **STD auto-populate** — selecting a series pre-fills the STANDARD (STD) value
   for every configurable field that has one, so the user starts from a complete,
   valid configuration instead of an empty form.
2. **Omni-directional allowable options** — every field's valid options are
   computed against *all the other* current selections (not just upstream ones),
   so a downstream pick can legitimately narrow an upstream field and an upstream
   field stays correctable after downstream picks.
3. **Non-destructive upstream correction** — changing a field keeps every
   still-valid selection; only fields the change *invalidates* are re-resolved
   (auto-reset to STD when valid, else dropped), and every reset/drop is reported.

The authoritative constraints (feasible + motor + combine HP→RPM) are reused
unchanged, so the free-edit path can never admit a combination the linear walk
would reject.

## Approach (Approach A — additive, zero regression to the correction gate)

The existing linear-walk endpoint `POST /configurations/evaluate` is left
**untouched** so the correction-regression gate stays green. A **new** endpoint
was added alongside it, and the UI was pointed at the new one.

- Extracted the feasible/motor/combine filtering that `/evaluate` performed
  inline into a single module-level helper
  `_apply_constraints(cursor, pub_id, family_id, series, selections, allowable)`
  in `src/api/v2_routes.py`. `/evaluate` now calls the helper (behaviorally
  identical — proven by the unchanged gate). This is the *single authoritative*
  constraint filter now shared by both endpoints.
- Added `POST /families/{family}/configurations/resolve-state`
  (`FreeConfigRequest` → `FreeConfigResponse`). The linear-walk
  `EvaluateResponse` model was not modified.

### Algorithm (`resolve-state`)

1. Load the series option catalog + STD defaults from `cfg.SeriesFieldOption`.
2. If `selections` is empty, seed every field that has an `IsStandard` value.
3. Fixpoint loop (bounded): drop no-longer-applicable fields (conditional
   applicability, e.g. `WETTED_HARDWARE_SELECTION`); then for each selected
   field compute its allowable options given **all the other** selections. If the
   value is still valid, keep it. If invalidated: reset to STD when STD is valid,
   else take the first remaining valid option, else drop. Record reset/dropped.
4. Recompute per-field allowable options for every applicable field, resolve
   identifier (PN segment) codes, and return the complete state.

## Standard-default reality

Not every field carries an engineering STD in the workbook. At the active
publication, series **1500** has **31** STD-flagged fields and **15** without;
series **5500** has **21** with and **17** without. The un-defaulted fields are
genuinely user-choice (pump size, motor HP/RPM, impeller trim, setting/length,
etc.). `resolve-state` seeds STD wherever one exists and leaves the rest **unset
but fully editable** with their constraint-correct options — the honest behavior,
matching what `/evaluate` exposes. "STD for every field" therefore means "STD for
every field that defines one."

## UI (`ui/configurator.html`)

Rewritten to a free-edit grid: every applicable field is an always-editable
dropdown (no locked/current gating). STD is pre-selected; each card shows a
`std` / `custom` / `not set` tag and a colored left border. On any change the UI
POSTs `resolve-state` with `changed_field`, applies the returned state, and a
notice banner plus a per-card marker surface exactly which fields were
auto-adjusted or cleared. "Reset to Standard" re-seeds STD; "Generate Part Number
& SKU" resolves the completed configuration unchanged.

## Verification

- **Correction gate** `scripts/run_all_fybroc_audits.py` → **ALL CORRECTIONS
  INTACT**: selections-vs-DB clean, feasible 14/14, motor 91/91, identifier
  parity 44/44, BOM 38/38, quote 22/22, **free_config 30/30**.
- **F160 Excel oracle** `scripts/fybroc_oracle_compare.py` → **6/6** (Excel ==
  API identity across the representative matrix).
- **New audit** `scripts/audit_free_config.py` (registered in the gate) proves,
  for series 1500 and 5500: STD seed completeness, allowable integrity (non-empty
  + STD within), non-destructive upstream correction, invalidation is
  auto-reset/dropped **and reported**, and the resulting config resolves with
  `parity_ok`.
- Free-config resolves: 1500 → `FA11AA-0001-S03-01-1400S-XXX-00`,
  5500 → `FG11AA-0000-01-1400S-XXX-00`, both `parity_ok=True`.

## Files

- `src/api/v2_routes.py` — `_apply_constraints` helper + `resolve-state` endpoint
  and `FreeConfigRequest`/`FreeConfigResponse` models; `/evaluate` now calls the
  shared helper (unchanged behavior).
- `ui/configurator.html` — free-edit grid on `resolve-state`.
- `scripts/audit_free_config.py` — new focused audit.
- `scripts/run_all_fybroc_audits.py` — registers the new audit in the gate.

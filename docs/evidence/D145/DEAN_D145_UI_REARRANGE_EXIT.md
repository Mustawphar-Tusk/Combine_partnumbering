# D145 — Dean UI Selection-Hierarchy Rearrangement — EXIT

**Milestone:** D145 — Dean UI Selection-Hierarchy Rearrangement (presentation-only)
**Date:** 2026-08-26
**Branch:** `feature/m021-shared-excel-production-hardening`
**Mode:** FULL (milestone-exit audit applied)
**Status:** PASS

---

## 1. Objective (restated as checkable criteria)

Align the Dean configurator UI field ORDER and GROUPING to the authoritative
**Dean Data Sheet Rev 2.xlsm** (Smart Number B3:AL26 + Data Sheet B12:I71 + the
Dean Pump Specification Sheet), as a **presentation-only** change:

1. Dean config fields are returned in the authoritative Smart-Number order (not
   alphabetical), via a Dean-specific hierarchy.
2. Dean config is grouped into the authoritative **10 groups** (Pump
   Information, Impeller, Power Frame, Coupling, Pump Seal, Flush/Barrier/Cooling
   Plan, Motor, Baseplate, Testing & Documentation, Additional Options), in
   order, delivered as an additive `field_groups` response field.
3. Empty/unselectable authoritative fields render as **C/F** (Contact Factory),
   NOT hidden — EXCEPT fields a `PUMP_CONFIGURATION` bundle deliberately
   excludes (those are omitted, since the user chose not to include that
   component), and identity fields (SERIES/SIZE/ALT_SIZE) which are owned by the
   Series/Size selectors, not the field grid.
4. **Part-Number assembly, parity, and the certified PCL v0.1 numbering are
   unchanged** (presentation only).
5. **Fybroc is byte-unchanged** — flat render (`field_groups == []`), original
   Fybroc field order preserved.

---

## 2. Deliverables inventory

Code (presentation layer only — NO schema, loader, or data changes):

- `src/api/v2_routes.py`
  - `DEAN_FIELD_GROUPS` — authoritative 10-group → real `cfg.SeriesFieldOption`
    field-code map.
  - `DEAN_FIELD_HIERARCHY` (flattened from the groups) + `_DEAN_HIERARCHY_INDEX`.
  - `_family_hierarchy_index()`, and family-aware `_hierarchy_rank(field, family)`
    / `_order_fields(fields, family)` (Fybroc path unchanged by default).
  - `_field_groups_payload(ordered_fields, family, selections)` — emits the
    grouped structure; each field carries `placeholder` (True ⇒ C/F). Bundle-
    excluded component groups are dropped; identity fields are omitted.
  - `_dean_excluded_components()` + `_DEAN_GROUP_TO_COMPONENT` — map a bundle's
    excluded components to the authoritative UI groups so a fully-excluded
    component group is dropped wholesale (not shown as all-C/F).
  - `EvaluateResponse` and `FreeConfigResponse` gained
    `field_groups: list[dict]` (default `[]`); both the `/configurations/evaluate`
    and `/configurations/resolve-state` return sites now populate it and thread
    `family_upper` into ordering.
- `ui/configurator.html`
  - New `fieldGroups` client state (populated from `data.field_groups`).
  - `renderAllFields` branches: grouped render (group header + cards + disabled
    C/F placeholder rows) when `field_groups` is present (Dean); flat render
    otherwise (Fybroc — unchanged). Card builder refactored into
    `buildFieldCard`; new `buildPlaceholderCard` for C/F rows.
  - CSS for `.group-header` (full-row banner), `.field-card.is-cf`, `.tag.cf`.

Audit:

- `scripts/audit_dean_ui_rearrange.py` — re-runnable milestone audit (see §3).

No DB migration, no metadata publish, no config/data file change.

---

## 3. Milestone-specific audit

`scripts/audit_dean_ui_rearrange.py` (API running locally):

```
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_ui_rearrange.py
```

Result: **40 passed, 0 failed (exit 0).** Covered:

- Dean resolve-state for PH2110, DL200, RA3146, R5140:
  - fields in authoritative hierarchy order;
  - `field_groups` present, groups in authoritative order;
  - every group field carries `{field, placeholder}`;
  - bundle-excluded fields omitted (not C/F); identity fields not in the grid;
  - no present (selectable) field mislabeled as C/F.
- Bundle gating: "Pump Only" ⇒ Coupling + Baseplate groups omitted; full bundle
  ("Pump, Baseplate, Coupling and Motor") ⇒ Coupling (2 real), Baseplate (9
  real), Motor (FRAME_SIZE real) appear.
- Fybroc isolation: `field_groups == []`, Fybroc hierarchy order preserved.
- PN unchanged: PH2110 and DL200 STD configs still resolve to a PN + SKU.

---

## 4. Cross-family / prior-correction regression

```
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\run_all_fybroc_audits.py
```

Result: **ALL CORRECTIONS INTACT — 9/9 PASS (exit 0).**

| audit | result |
|---|---|
| audit_selections_vs_db | PASS (2096/2096 rows, clean) |
| audit_feasible_constraints | PASS (44/44) |
| audit_motor_constraints | PASS (91/0) |
| audit_identifier_parity | PASS (44/0) |
| audit_bom_engine | PASS (38/0) |
| audit_quote_engine | PASS (22/0) |
| audit_free_config | PASS (32/0) — exercises resolve-state (the edited endpoint) |
| audit_fybroc_pricing | PASS (47/0) |
| audit_fybroc_motor_cpq | PASS (37/0) |

`audit_free_config.py` directly exercises `/configurations/resolve-state` for
Fybroc (series 1500, 5500) and confirms the family-aware edit left the Fybroc
free-edit behavior, allowable options, non-destructive re-resolution, and PN
parity unchanged.

---

## 5. Isolation / no-collateral-damage

This milestone made NO DB change. Dean + shared baselines re-counted after the
work (expected = baseline):

| invariant | before (baseline) | after | status |
|---|---|---|---|
| Dean SeriesFieldOption rows | 48063 | 48063 | unchanged |
| Dean FeasibleConstraint rows | 256 | 256 | unchanged |
| Dean PumpModelReference models | 206 | 206 | unchanged |
| Dean series | 37 | 37 | unchanged |

(Verified via a one-off DB count check; now subsumed by the regression gate's
`audit_selections_vs_db` for Fybroc and the counts above for Dean.)

Backward compatibility of the API contract: `field_groups` is an ADDITIVE
response field defaulting to `[]`, so existing clients (including the Fybroc UI
path) are unaffected.

---

## 6. Build / verify

- `import src.api.app; import src.api.v2_routes` → **imports OK** after every edit.
- Live API started on 127.0.0.1:8080; all probes above executed against it.
- Temporary scripts created during the work (`_tmp_verify_pn.py`,
  `_tmp_fybroc_series.py`, `_tmp_isolation.py`) were deleted.

---

## 7. Known gaps (disclosed, not glossed)

These are pre-existing engineering gaps surfaced (now as honest **C/F**
placeholders) by the authoritative layout — they are NOT introduced by this
milestone and NOT selectable yet:

- **Motor** group: only `FRAME_SIZE` is a real Dean field. `MOTOR_HP`,
  `MOTOR_SPEED`, `MOTOR_VOLTAGE`, `MOTOR_PHASE_HERTZ`, `MOTOR_CONTROL`,
  `MOTOR_ENCLOSURE`, `MOTOR_EFFICIENCY`, `C_FACE_ADAPTER_OPTION`,
  `MOTOR_MANUFACTURER`, `MOTOR_OPTIONS` → C/F (external motor DB / unbuilt).
- **Testing & Documentation** group: entirely C/F (`PERFORMANCE_TESTING`,
  `HYDRO_TEST`, `VIBRATION`, `SOUND_LEVEL`, `GENERAL_INSPECTION`,
  `DOCUMENTATION_1..4` — no Dean options exist yet).
- **Flush / Barrier / Cooling Plan**: `BARRIER_PLAN` / `BARRIER_PLAN_EXTRAS` →
  C/F (no Dean options); `FLUSH_PLAN`, `COOLING_PLAN`, `COOLING_PLAN_PIPING`,
  `COOLING_PLAN_EXTRAS` are real.

C/F rows are disabled (non-editable) and carry no PN segment, so they cannot
affect numbering. They exist purely to keep the spec-sheet layout complete per
the product decision.

---

## 8. Exit-gate decision

| criterion | result |
|---|---|
| 1. Authoritative field order (Dean) | PASS |
| 2. Authoritative 10-group presentation | PASS |
| 3. C/F for unbuilt; bundle-excluded omitted; identity omitted | PASS |
| 4. PN assembly / parity unchanged | PASS |
| 5. Fybroc byte-unchanged (flat, original order) | PASS |
| Cross-family regression (9/9 ALL CORRECTIONS INTACT) | PASS |
| Isolation (Dean baselines unchanged) | PASS |

**DECISION: PASS.**

Next permitted milestone (queued, per project plan): the **PCL v0.1
Codependencies** workstream — implement the `Codependencies` sheet (B1:BA171) as
Dean cross-constraint dependencies "as needed", reconciled against D110's 256
enforced tuples + 519 held-out seal tuples. **Awaiting explicit user go-ahead
before starting.**

# Fybroc Suction/Discharge Taps — Pricing Bridge Exit Evidence

**Milestone slice:** Wire the Fybroc Suction Discharge Taps field (V6 `Pump Options -
Horizontal` E3:E4) to its Rev0.4 `1500 Pricing` adder (CS–CV) so the selected option
resolves to the sheet price; unpriced series show C/F.
**Family:** FYBROC (PumpFamilyId 2) — frozen at F180; DEAN (1) untouched.
**Date:** 2026-08-26
**Mode:** FULL (pricing runtime change with cross-family blast radius).
**Active pricing publication:** `FYBROC-REV04-MERGE-20260914-V1` — **unchanged** (no republish).

---

## 1. Deliverables & exit-gate criteria

**Objective:** Selecting a Suction Discharge Taps option for 1500 must resolve to the
Rev0.4 `1500 Pricing` "Adder for Suction and Discharge Taps" (CS–CV, rows 6–43) price
for that size + option; series without configured pricing show **C/F** as a placeholder.

**Criteria:**
1. `1500` + `not supplied` → **$0**; `1500` + `supplied` → **$1041**, matching the sheet, across sizes.
2. A series with no configured pricing (e.g. 2530) → **C/F** for this component.
3. Cross-family regression `run_all_fybroc_audits.py` = **ALL CORRECTIONS INTACT**.
4. Dean isolation: no DB write; Dean pricing unchanged.

---

## 2. Root cause (why it was C/F despite priced rows existing)

Three vocabularies were in play and the runtime pricing lookup only bridged two of them:

| Layer | Field code | Values |
|---|---|---|
| V6 field domain (E3:E4) | source | `No Suction Discharge Tapss` / `Suction Discharge Taps` |
| Selectable option (`cfg.SeriesFieldOption`) | `SUCTION_DISCHARGE_TAPS` | `no suction discharge taps` / `suction discharge taps` |
| Priced row (`price.PriceRule.SourceOptionValue`) | `SUCTION_DISCHARGE_TAPS` | `Not_Supplied_by_Fybroc` ($0) / `Supplied_by_Fybroc` ($1041) |

The 38 priced rows (per 1500 size) already existed and were correct. But the runtime
`_price_component` matched the **selection value** against `SourceOptionValue` with only
case/space/underscore normalization — `no suction discharge taps` ≠ `not supplied by
fybroc` → **no match → C/F.** The authoritative reconciliation already lived in
`config/runtime_profiles/fybroc_value_equivalences.json` (used by the config engine),
but the **pricing path never consulted it.**

---

## 3. Fix (general, data-driven, no data reload) — `src/api/v2_routes.py`

- **`_value_equivalence_map(family)`** (module-level, cached): loads the equivalence
  profile into `{FIELD_CODE -> {normalized_value -> {equivalent raw values}}}`. A
  profile value ending in `*` (the STANDARD-default marker) is registered both by its
  exact normalized form and as a **prefix alias**, so the selectable `no suction
  discharge taps` matches the profile's `No Suction Discharge Tap*`.
- **`_EQUIV_FIELD_ALIAS`**: maps the runtime SFO field code to the profile's field code
  where they differ (`SUCTION_DISCHARGE_TAPS → SUCTION_DISCHARGE`,
  `CYCLONE_SEPERATOR → CYCLONE_SEPARATOR`).
- **`_price_component(component_code, selection_value, field_code)`**: now tries the raw
  selection value **and** every value in its equivalence group (exact + prefix), so a
  selected option resolves to its priced row. The call site passes `field_code=sel_field`.

This is family-safe and data-only-read: **no `price.*`/`cfg.*` write, no publication
minted.** Series without priced rows (any component/series lacking a `found` rule) still
return `None` → C/F, satisfying the placeholder requirement.

---

## 4. Verification (commands + numbers)

### 4.1 Suction/Discharge resolves to the sheet price (the deliverable)
Extended `scripts/audit_fybroc_pricing.py` (expectations read from the CS–CV table at
runtime; the sheet read width was widened from col 90 to 104 because CV = column 100):
```
.\.venv\Scripts\python.exe scripts\audit_fybroc_pricing.py
```
→ **35 passed, 0 failed** (was 27; +8 suction/discharge assertions):
- `1500 / {1x1.5x6, 2x3x8, 3x4x10, 6x8x13} / no suction discharge taps` → **$0** (sheet 0)
- `1500 / same sizes / suction discharge taps` → **$1041** (sheet 1041)

Live confirmation: `no suction discharge taps` → `found $0 (Not_Supplied_by_Fybroc)`;
`suction discharge taps` → `found $1041 (Supplied_by_Fybroc)`. A **2530** config (no
pricing rows) → **C/F** — the requested placeholder behavior.

### 4.2 Bonus regression fix (same bridge)
**Casing Drains** now also resolves (`not supplied by fybroc` → $0,
`Not_Supplied_by_Fybroc`); it was silently C/F before for the same vocabulary reason.
(Cyclone Separator remains C/F — its priced label differs from its equivalence group;
that is a separate data question and correctly shows the honest C/F placeholder.)

### 4.3 Cross-family / prior-correction regression
Port 8080 freed first (gate spins its own temp API):
```
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\run_all_fybroc_audits.py
```
→ **ALL CORRECTIONS INTACT (9/9):** selections (2096=2096), feasible constraints (44/44),
motor constraints (91/0), identifier parity (44/0), BOM (38/0), quote (22/0), free config
(32/0), **pricing (35/0)**, motor CPQ (37/0).

### 4.4 Isolation
Runtime-only change (a value-equivalence bridge in the pricing lookup): no DB write, no
republish. FYBROC pricing rules 56241 / DEAN 9874 unchanged; both current publications
unchanged. Isolation holds by construction.

### 4.5 Build/verify
```
.\.venv\Scripts\python.exe -c "import src.api.app; import src.api.v2_routes"
```
→ `imports OK`. All `scripts/_tmp_*` probe scripts removed.

---

## 5. Exit-gate decision — PASS

| # | Criterion | Result |
|---|---|---|
| 1 | 1500 suction/discharge resolves to sheet price ($0 / $1041) | **PASS** — audit 35/0 |
| 2 | Unpriced series (2530) → C/F placeholder | **PASS** |
| 3 | run_all_fybroc_audits ALL CORRECTIONS INTACT | **PASS** — 9/9 |
| 4 | Dean isolated; no DB write | **PASS** |

---

## 6. Known gaps / disclosures

- **Other adders with a label mismatch benefit from the same bridge** (Casing Drains now
  resolves). Cyclone Separator's priced label doesn't share its equivalence group value,
  so it stays C/F — a data reconciliation item, not a runtime bug. Flagged for a future
  pricing-vocabulary pass.
- **Non-1500 series show C/F for this component by design** until their pricing is
  configured (they have no `found` rows for `SUCTION_DISCHARGE_TAPS`). This is the
  requested placeholder behavior, not a defect.
- The bridge relies on `config/runtime_profiles/fybroc_value_equivalences.json`; adding a
  new supplied/not-supplied field requires an equivalence group there (guarded indirectly
  by the sheet-derived pricing audit).

---

## 7. Reproducibility — exact commands
```
.\.venv\Scripts\python.exe scripts\audit_fybroc_pricing.py
Get-NetTCPConnection -LocalPort 8080 -State Listen | %{Stop-Process -Id $_.OwningProcess -Force}
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\run_all_fybroc_audits.py
.\.venv\Scripts\python.exe -c "import src.api.app; import src.api.v2_routes"
```

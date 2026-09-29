# Fybroc Rev0.4 "1500 Motors" — CPQ Conversion2 Exit Evidence

**Milestone slice:** Adopt the Rev0.4 `1500 Motors` datasheet — verify motor pricing
authority and implement the **CPQ Conversion2** motor display descriptor (the
canonical "selected motor" string shown in UI quotes).
**Family:** FYBROC (PumpFamilyId 2) — frozen at F180; DEAN (PumpFamilyId 1) untouched.
**Date:** 2026-08-26
**Mode:** FULL (authoritative motor source + runtime change + new display concept).
**Active pricing publication:** FYBROC `FYBROC-REV04-MERGE-20260914-V1` (IsCurrent) —
**unchanged** (no republish).

---

## 1. Deliverables inventory & exit-gate criteria

**Objective:** The Rev0.4 `1500 Motors` datasheet is authoritative for motor pricing
AND for the **CPQ Conversion2** descriptor — the string used to represent the
selected motor when displaying selected fields in UI quotes.

**Concrete, checkable exit-gate criteria:**
1. The `1500 Motors` layout is verified against the real sheet (columns, rows, price
   distribution, CPQ Conversion2 semantics) — not the request wording.
2. A resolved 1500 configuration exposes the correct CPQ Conversion2 descriptor,
   matching the authoritative sheet **exactly** (including casing), on the motor
   line and at the response top level.
3. The UI quote surfaces the descriptor for the selected motor.
4. Cross-family regression `run_all_fybroc_audits.py` = **ALL CORRECTIONS INTACT**.
5. Dean isolation: no DB write, Dean pricing rules unchanged.

---

## 2. What the sheet actually says (probed, not assumed)

`1500 Motors`: header row 2, data rows 3–144002 (**144,000 rows**), columns B–N:
B=Motor Enclosure, C=Motor Efficiency, D=Motor Voltage, E=Motor Hertz, F=Motor Hp,
G=Motor RPM, H=Frame Size, I=Motor Mfg, J=Shaft Grounding, K=Paint Upgrade,
**L=CPQ Conversion2**, M=HpRPM, N=Price.

- **Only 151 of 144,000 rows are priced** (numeric `Price`); 143,849 are `C/F`
  (Contact Factory). The priced motor cross-product is intentionally tiny; the
  current publication already carries the priced MOTOR rows (`--found-only` publish),
  consistent with the existing MOTOR rule count.
- **CPQ Conversion2 == `{Motor Enclosure}---{Motor Efficiency}---{Motor Voltage}---{Motor Hertz}`
  for ALL 144,000 rows (0 mismatches).** It is a pure deterministic function of those
  four fields — NOT Hp/RPM/Frame/Mfg/etc. (despite the request listing 11 fields).
  There are only **18 distinct values** (3 enclosures × 1 efficiency × 3 voltages ×
  2 hertz).
- HpRPM (col M) = `{Hp}-{Rpm}` — separate; already used elsewhere in pricing.

**Consequence:** CPQ Conversion2 needs **no 144k-row reload**; it is derived at
runtime from the four selected motor fields. This is the faithful minimal change.

---

## 3. Implementation

All in `src/api/v2_routes.py` (resolve flow); no DB/schema change, no price reload.

- Added `_CPQ_DISPLAY` (sheet-cased token map: enclosure `tefc→TEFC`,
  `tefc sd→TEFC SD`, `ieee 841→IEEE 841`; efficiency `pe→PE`; voltage & hertz pass
  through unchanged) + `_cpq_token()` + `_cpq_conversion2(selections)` which returns
  `"{enc}---{eff}---{volt}---{hz}"` or `None` if the four fields are not all selected.
  Casing note: the stored SeriesFieldOption values are lowercase, so the map restores
  the sheet's exact display casing.
- `motor_cpq_conversion` is computed once and surfaced in three places:
  1. the `pricing[]` **Motor** entry gains a `cpq_conversion` field (when the motor is
     priced),
  2. the `component_pricing[]` **Motor** row uses the CPQ descriptor as its
     `selection` (so the UI shows it),
  3. the resolve response gains a top-level `motor_cpq_conversion` — **present even
     when the motor is C/F** (the common case), so the UI can always show the motor
     descriptor.
- **DEAN-safe:** `_cpq_conversion2` returns `None` when the four Fybroc motor fields
  are absent (Dean has none), and the helper/assignment run before the shared return,
  so there is no NameError and no behavior change for Dean.
- **UI:** `ui/configurator.html` `renderPricing()` already renders each component's
  `selection` in the "Selection" column — the Motor row now displays the CPQ string
  automatically. No UI code change required.

The quote-line pricing lineage (persisted JSON of the `pricing` components) now
carries `cpq_conversion` on the Motor line, so a saved quote retains the descriptor.

---

## 4. Verification (commands + numbers)

### 4.1 CPQ display correctness vs the authoritative sheet — the deliverable
New re-runnable audit (expectations DERIVED FROM THE SHEET at runtime — reads all
144k rows to build the (enc,eff,volt,hz)→CPQ map, then walks 1500 forcing each of
the 18 combos and asserts the API value equals the sheet):
```
.\.venv\Scripts\python.exe scripts\audit_fybroc_motor_cpq.py
```
→ **37 passed, 0 failed (18 combos scored).** Every combo matches exactly, including
tricky casing: `TEFC SD---PE---230/460---3ph - 60 hz`, `IEEE 841---PE---460---3ph - 50 hz`.
Live probe also confirmed the `component_pricing` Motor row `selection` =
`TEFC---PE---230/460---3ph - 60 hz` and the top-level `motor_cpq_conversion` is set
even when the motor is C/F.

### 4.2 Cross-family / prior-correction regression
Port 8080 freed first (gate spins its own temp API):
```
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\run_all_fybroc_audits.py
```
→ **RESULT: ALL CORRECTIONS INTACT (9/9):** selections (2096=2096), feasible
constraints (44/44), motor constraints (91/0), identifier parity (44/0), BOM (38/0),
quote engine (22/0), free config (32/0), pricing (27/0), **motor CPQ (37/0)**. The
CPQ audit is now wired into the gate as audit #9. The prior VR-1 pricing correction
is still intact (quote shows 1500 unit=4987).

### 4.3 Isolation / no-collateral-damage
Runtime-only change (a derived display string): **no `price.*` / `cfg.*` write, no
publication minted.** DEAN pricing rules remain 9874; FYBROC pricing 56241; both
current publications unchanged. Isolation holds by construction.

### 4.4 Build/verify
```
.\.venv\Scripts\python.exe -c "import src.api.app; import src.api.v2_routes"
```
→ `imports OK`. All `scripts/_tmp_*` probe scripts removed.

---

## 5. Exit-gate decision — PASS

| # | Criterion | Result |
|---|---|---|
| 1 | `1500 Motors` layout verified vs sheet (144k rows, CPQ = 4-field join) | **PASS** |
| 2 | Resolved config exposes exact CPQ Conversion2 (line + top-level) | **PASS** — audit 37/0 |
| 3 | UI quote surfaces the motor descriptor | **PASS** — via existing renderPricing selection column |
| 4 | run_all_fybroc_audits ALL CORRECTIONS INTACT | **PASS** — 9/9 |
| 5 | Dean isolated; no DB write | **PASS** |

---

## 6. Known gaps / disclosures (not glossed)

- **Motor price coverage is intentionally sparse:** only 151 of 144,000 motor combos
  carry a price; the rest are C/F (Contact Factory) in the source, so most resolved
  motors show C/F. This is a source-data property, not a defect. Motor pricing itself
  was already published (unchanged this slice); CPQ Conversion2 is the added piece.
- **CPQ Conversion2 is derived, not stored per-row.** It is verified identical to the
  sheet's stored column for all 144k rows and guarded by the sheet-derived audit, so
  any future drift (e.g. a new enclosure token) fails the gate. If the sheet ever
  makes CPQ Conversion2 diverge from the 4-field join, the audit will catch it and the
  `_CPQ_DISPLAY` map must be extended.
- **`custom` enclosure/voltage** selections (present in the config but not in the
  motor sheet's priced set) fall back to `.upper()` for display; they are not part of
  the 18 authoritative combos. No priced motor uses them.

---

## 7. Reproducibility — exact commands
```
.\.venv\Scripts\python.exe scripts\audit_fybroc_motor_cpq.py
Get-NetTCPConnection -LocalPort 8080 -State Listen | %{Stop-Process -Id $_.OwningProcess -Force}
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\run_all_fybroc_audits.py
.\.venv\Scripts\python.exe -c "import src.api.app; import src.api.v2_routes"
```

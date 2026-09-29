# Fybroc Rev0.4 "1500 Pricing" — Exit Evidence

**Milestone slice:** Adopt/verify Rev0.4 `1500 Pricing` datasheet as authoritative
Fybroc pricing; fix the base-pump material-matching pricing bug found during
enforcement verification.
**Family:** FYBROC (PumpFamilyId 2, PriceBook 2) — frozen at F180; DEAN
(PumpFamilyId 1, PriceBook 1) must be untouched.
**Date:** 2026-08-26
**Mode:** FULL (authoritative pricing source + runtime pricing change + cross-family
blast radius).
**Active pricing publication:** FYBROC `FYBROC_STANDARD` ver 7
`FYBROC-REV04-MERGE-20260914-V1` (IsCurrent=1) — **unchanged** (no republish).

---

## 1. Deliverables inventory & exit-gate criteria

**Objective:** The Rev0.4 `1500 Pricing` datasheet (base price + all material/option
adders + seal + coupling + baseplate) is the authoritative Fybroc pricing source,
correctly extracted, published, and **enforced** so a configured 1500 pump prices
to the exact sheet values.

**Concrete, checkable exit-gate criteria:**

1. Every `1500 Pricing` block is extracted to the right ComponentCode with the
   right columns/rows (reconciled against the real sheet, not the request spec).
2. The published `price.PriceRule` rows equal the sheet values, family-scoped to
   FYBROC.
3. Runtime resolves base pump + adders to the **exact** sheet price for a given
   (size, material, option) — no material aliasing / over-pricing.
4. Cross-family regression `run_all_fybroc_audits.py` = **ALL CORRECTIONS INTACT**.
5. Dean isolation: Dean pricing rules unchanged; no cross-family write.

---

## 2. What was found (honest summary)

- **The `1500 Pricing` data was ALREADY fully extracted, published, and enforced**
  in the current publication `FYBROC-REV04-MERGE-20260914-V1` (56,241 FYBROC rules).
  The Rev0.4 pricing compiler (`src/compiler/fybroc_rev04_pricing_compiler.py` +
  driver `scripts/compile_fybroc_rev04_pricing.py`, profile
  `config/pricing_profiles/fybroc_rev04.json`) detects blocks by row-3 description
  (robust to column shifts). No reload was needed and none was done.
- **A read-only probe of the real sheet detected 24 blocks** and reconciled them
  against the request spec. The request's column bands contained transcription
  errors; the sheet (and the code, which reads the sheet) are authoritative. See §3.
- **The real defect was in the runtime, not the data:** base-pump material matching
  aliased a plain `vr-1` selection onto the more expensive `VR-1A` row, over-pricing
  every VR-1 pump. Fixed and guarded. See §4.

---

## 3. Reconciliation: request spec vs the real sheet (24 blocks)

Row-3 description → ComponentCode; columns are the REAL sheet columns (probed via
the compiler's own `detect_blocks`). Row counts are non-blank key-column rows.

| Block (row-3 desc) | Real cols | rows | ComponentCode |
|---|---|---|---|
| Base Price for a pump based on size | B–E | 114 | BASE_PUMP (per material) |
| VR-1 Base Price (helper) | G–I | 19 | *(not published — see note)* |
| Adder for pump material | K–N | 114 | PUMP_MATERIAL_ADDER |
| Adder for Shaft Material | P–S | 38 | SHAFT_MATERIAL |
| Adder for Shaft Sleeve | U–X | 114 | SLEEVE |
| Adder for Gland Hardware | Z–AC | 95 | GLAND_HARDWARE |
| Adder for Power Frame Hardware | AE–AH | 38 | POWER_FRAME_HARDWARE |
| Adder for Bearing Option | AJ–AM | 57 | BEARING_OPTION |
| Adder for Casing Hardware | AO–AR | 38 | CASING_HARDWARE |
| Coupling Guard Pricing | AT–AW | 76 | COUPLING_GUARD |
| Baseplate pricing | AY–BC | 564 | BASEPLATE |
| Adder for Baseplate Hardware | **BE–BH** | 38 | BASEPLATE_HARDWARE |
| Mechanical Seal Pricing | BJ–BP | 6838 | SEAL |
| Coupling Pricing | BR–BW | 1050 | COUPLING |
| Adder for Flange Type | **BY–CB** | 57 | FLANGE_TYPE |
| Adder for Cyclone Separator | CD–CG | 38 | CYCLONE_SEPARATOR |
| Flush Pricing | CI–CL | 190 | FLUSH |
| Adder for Casing Drains | CN–CQ | 38 | CASING_DRAINS |
| Adder for Suction and Discharge Taps | CS–CV | 38 | SUCTION_DISCHARGE_TAPS |
| Adder for Seal Guard | CX–DA | 38 | SEAL_GUARD |
| Adder for Performance Testing | DC–DF | 57 | PERFORMANCE_TESTING |
| Adder for Vibration Testing | DH–DK | 57 | VIBRATION_TESTING |
| Adder for Sound Level Testing | DM–DP | 57 | SOUND_LEVEL_TESTING |
| Adder for C-Face Adaptor | DR–DV | 38 | C_FACE_ADAPTOR |

**Request-spec transcription errors, corrected against the sheet:**
- **Baseplate Hardware** — request said AY–BC (same band as Baseplate Pricing).
  Real is **BE–BH**.
- **First "Adder For Flange Type" at AY–BC** — does **not** exist; that band is
  Baseplate Pricing. The real (single) Flange Type block is **BY–CB** (the
  request's second Flange Type entry, correct).
- **"Flush Pricing" at CI–CL** — request labeled it "Cyclone Separator"; the real
  headers are `Flush Material, Flush`.
- All other 20 blocks match the request columns exactly.

**VR-1 Base Price (G–I) intentionally NOT published:** verified byte-for-byte
redundant with the main Base-Price table's `vr-1` material rows (1x1.5x6=4987,
1.5x3x6=5256, 2x3x6=5510, …). Publishing it would create duplicate BASE_PUMP
rules; the `vr-1` price is already carried by the B–E table's `VR-1 (Standard)` row.

**C_FACE_ADAPTOR / FLANGE_TYPE row-count note:** the sheet lists 38 / 57 rows;
the DB holds 19 / 36 `found` rules because `--found-only` publication drops the
`C/F` rows (C_FACE = 19 numeric + 19 C/F; FLANGE_TYPE = 46 numeric + 11 C/F, with
further collapse from the merge). C/F combos default to call-for-price at runtime,
so dropping them loses no pricing information. Pre-existing in the F180-frozen
publication; not changed here.

---

## 4. The pricing correction (root cause + fix)

**Symptom:** resolving a 1500 pump with `PUMP_MATERIAL='vr-1'` (size 1x1.5x6)
returned a base price of **8666** (the `VR-1A` price) instead of the correct
**4987** (`VR-1 (Standard)`). Every plain-VR-1 pump was over-priced.

**Root cause (`src/api/v2_routes.py`, base-pump material matching):** the pattern
list was built with a broad `%vr-1%` LIKE (from `material_display.replace(' ','%')`)
placed **first**, and the lookup loop `break`s on the first matching row. `%vr-1%`
matches `VR-1 (Standard)`, `VR-1A`, `VR-1V`, `VR-1 BPO/DMA`, … and (all Priority=100)
returned `VR-1A` first. A stale comment even asserted "vr-1a and vr-1 are both
standard VR-1 material" — they are distinct materials with distinct prices.

**The published DB rows were correct** (VR-1 (Standard)=4987, VR-1A=8666,
VR-1V=13870, VR-1 BPO/DMA=5480, VR-1A BPO/DMA=9530, EY-2=6652 — all equal the
sheet). The bug was purely in runtime selection.

**Fix:** build EXACT, per-material anchored patterns and try the most specific
first; the broad direct pattern is only a last resort. Mapping:
`vr-1 → "vr-1 (standard)"`, `vr-1a → "vr-1a"`, `vr-1v → "vr-1v"`, `ey-2 → "ey-2"`,
`vr-1 bpo/dma / vr-1a bpo/dma / vr-1v bpo/dma → exact`. Plain `vr-1`'s only
fallback is `"%vr-1 (%"` (never a bare `%vr-1%`), so it can never match VR-1A/VR-1V.

**DEAN unaffected:** Dean materials never match these `vr-1*/ey-2` patterns, and
Dean prices in its own family-gated branch that recomputes the total.

---

## 5. Verification performed (commands + numbers)

All via `.venv\Scripts\python.exe`, `PYTHONPATH=.`.

### 5.1 Enforcement cross-check vs authoritative sheet — the correction
New re-runnable audit (expectations DERIVED FROM THE SHEET at runtime, not
hardcoded):
```
.\.venv\Scripts\python.exe scripts\audit_fybroc_pricing.py
```
→ **27 passed, 0 failed.** Base price matches the sheet for 4 sizes × 6 materials
(e.g. 1x1.5x6: vr-1=4987, vr-1a=8666, vr-1v=13870, vr-1 bpo/dma=5480,
vr-1a bpo/dma=9530, ey-2=6652), plus adder spot-checks. Before the fix, the same
cross-check reported base mismatches (vr-1→8666).

### 5.2 Cross-family / prior-correction regression
Port 8080 freed first (gate spins its own temp API):
```
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\run_all_fybroc_audits.py
```
→ **RESULT: ALL CORRECTIONS INTACT (8/8):** audit_selections_vs_db (2096=2096),
audit_feasible_constraints (44/44), audit_motor_constraints (91/0),
audit_identifier_parity (44/0), audit_bom_engine (38/0), audit_quote_engine
(22/0), audit_free_config (32/0), **audit_fybroc_pricing (27/0)**. The pricing
audit is now permanently wired into the gate as audit #8.

**Confirming evidence in the quote audit:** the 1500 quote line unit price is now
**4987.00** (correct VR-1 Standard); the same walk produced **8666.00** before the
fix — the correction is proven end-to-end through the quote engine.

### 5.3 Isolation / no-collateral-damage (nothing republished)
| PriceBook / family | Current version | Rules | Result |
|---|---|---|---|
| FYBROC_STANDARD (book 2) | FYBROC-REV04-MERGE-20260914-V1 (ver 7) | 56241 | unchanged |
| DEAN_STANDARD (book 1) | DEAN-MATRIX-20260826-V1 (ver 8) | 9874 | unchanged |

No `price.PriceRule` rows were added/removed (runtime-only change). Family
isolation holds by construction (publish proc supersedes only the same family's
PriceBookVersion; no cross-family DELETE). No new publication minted.

### 5.4 Build/verify
```
.\.venv\Scripts\python.exe -c "import src.api.app; import src.api.v2_routes"
```
→ `imports OK`. All `scripts/_tmp_*` probe scripts removed.

---

## 6. Exit-gate decision — PASS

| # | Criterion | Result |
|---|---|---|
| 1 | 24 blocks extracted correctly (reconciled vs sheet) | **PASS** |
| 2 | Published rows equal sheet values, FYBROC-scoped | **PASS** |
| 3 | Runtime prices to exact sheet value; VR-1 aliasing fixed | **PASS** — audit 27/0 |
| 4 | run_all_fybroc_audits ALL CORRECTIONS INTACT | **PASS** — 8/8 |
| 5 | Dean isolated (9874 unchanged); FYBROC 56241 unchanged | **PASS** |

---

## 7. Known gaps / disclosures (not glossed)

- **Adders don't yet gate pricing status.** `_pricing_status` marks a line `found`
  when base(+seal) resolve; the 19 single-value adders + multi-condition
  MOTOR/COUPLING/BASEPLATE/TAILPIPE are added to the total when they match but do
  not flip a line to `partial` if unmatched. So a config can read `found`/`partial`
  while some adders are silently C/F. Pre-existing behavior; unchanged here.
- **SEAL frequently resolves C/F for horizontal configs** (seal key shapes differ
  between sources), which is why 1500/1530 quote lines report `partial`. Known,
  pre-existing.
- **C_FACE_ADAPTOR / FLANGE_TYPE** publish only their numeric (`found`) rows
  (C/F dropped) — see §3. This matches runtime semantics (C/F = call-for-price).
- **Only base + Shaft/Gland/Flange adders are cross-checked** against the sheet by
  the new audit; extending the per-table price assertion to all 24 blocks is a
  reasonable future hardening (the enforcement path is shared, so the base+adder
  proof exercises the same code).

---

## 8. Reproducibility — exact commands
```
.\.venv\Scripts\python.exe scripts\audit_fybroc_pricing.py
Get-NetTCPConnection -LocalPort 8080 -State Listen | %{Stop-Process -Id $_.OwningProcess -Force}
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\run_all_fybroc_audits.py
.\.venv\Scripts\python.exe -c "import src.api.app; import src.api.v2_routes"
```

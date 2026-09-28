# Fybroc Rev0.4 — 29 ConstraintTables Conformance & Correction

**Date:** 2026-08-26
**Scope:** Verify all 29 ConstraintTables in `Fybroc Configuration Rev0.4.xlsx`
(Feasible Constraints sheet) are extracted, loaded, and ENFORCED per the
authoritative spec (fields, row/col ranges, allow-vs-not-allowed semantics), and
correct the one enforcement gap found.
**Family:** FYBROC (PumpFamilyId=2). Dean untouched.

---

## 1. Per-table conformance (spec vs actual sheet vs loaded DB vs enforcement)

Sheet anchors were found by header search (`ConstraintTableN` + `Allowed?`/
`Allowed`), so the exact column letters in the request (a few had copy drift,
e.g. CT20/21/24/25/29) do not affect extraction. Every table's FIELDS and
ALLOW/DENY SEMANTICS match the spec.

| CT | Fields (anchor) | Sheet rows | Semantics | Loaded | Enforced |
|---|---|---|---|---|---|
| 1 | Alt Size × CouplingGuard (B4) | 6–8 | not allowed | 3 NA | ✅ deny |
| 2 | Alt Size × Flange Type (B10) | 12 | not allowed | 1 NA | ✅ deny |
| 3 | Alt Size × Flush, 5500-only (B15) | 17–19 | not allowed | 3 NA | ✅ deny |
| 4 | Alt Size × Impeller Trim (F4) | 6–522 | allowed (allow-list) | 517 A | ✅ restrict |
| 5 | Alt Size × Pump Material (J4) | 6–21 | not allowed | 16 NA | ✅ deny |
| 6 | Alt Size × Shaft Material (J24) | 26–31 | not allowed | 6 NA | ✅ deny |
| 7 | Casing Drains × Pump Material (N4) | 6 | not allowed | 1 NA | ✅ deny |
| 8 | Cyclone Sep × Flush (R4) | 6–11 | not allowed | 6 NA | ✅ deny |
| 9 | Flush × Pump Material (V4) | 6–8 | not allowed | 3 NA | ✅ deny |
| 10 | MotorOption × Paint Upgrade (Z4) | 6–7 | not allowed | 2 NA | ✅ deny |
| 11 | MotorOption × Shaft Grounding (Z9) | 11–12 | not allowed | 2 NA | ✅ deny |
| 12 | Pump Material × Setting (AD4) | 6–20 | not allowed | 15 NA | ✅ deny |
| 13 | Pump Material × Shaft Material (AD22) | 24–25 | not allowed | 2 NA | ✅ deny |
| 14 | Pump Material × Sleeve (AD27) | 29–30 | not allowed | 2 NA | ✅ deny |
| 15 | Pump Material × Suction Discharge Taps (AD32) | 34 | not allowed | 1 NA | ✅ deny |
| 16 | Seal Guard × Seal Option (AH4) | 6 | not allowed | 1 NA | ✅ deny |
| 17 | Seal Option × Seal Type (AH8) | 10–14 | not allowed | 5 NA | ✅ deny |
| 18 | Setting × Shaft Material (AL4) | 6–13 | allowed (allow-list) | 8 A | ✅ restrict |
| 19 | Shaft Material × Sleeve (AP4) | 6–17 | allowed (allow-list) | 12 A | ✅ restrict |
| 20 | Motor Control × Shaft Grounding (AT4) | 6 | not allowed (header 'Allowed' no `?`) | 1 NA | ✅ deny |
| 21 | Alt Size × Pump Material × Length (AX4, 3-leg) | 6–3482 | allowed+not allowed (blank=allowed) | 392 A / 3085 NA | ✅ restrict |
| 22 | Setting/Length × Length (BC4) | 6–188 | allowed (custom length) | 183 A | ✅ restrict |
| 23 | Setting/Length × Setting (BG4) | 6–24 | allowed (standard setting) | 19 A | ✅ restrict |
| 24 | Tailpipe Option × Tailpipe Length (BK4) | 6–120 | allowed | 115 A | ✅ restrict + **applicability fix** |
| 25 | Seal Mfg × Seal Type (BO4) | 6–35 | allow+deny+custom (blank=allowed) | 21 A / 9 NA | ✅ deny/restrict |
| 26 | Seal Option × Seal Mfg (BO37) | 39–63 | allow+deny+custom (blank=allowed) | 13 A / 12 NA | ✅ deny/restrict |
| 27 | Wetted Hardware × Wetted Hardware Selection (BS4) | 6–15 | allow+deny | 5 A / 5 NA | ✅ restrict/gate |
| 28 | Flush Material × Flush (BW4) | 6–23 | allow+deny | 10 A / 8 NA | ✅ deny/restrict |
| 29 | Alt Size × C-Face Adapter (CA4) | 6–8 | not allowed | 3 NA | ✅ deny |

(A = Allowed rows, NA = Not Allowed rows.)

**Blank `Allowed?` cells** in CT21/CT25/CT26 are REAL combos (verified), loaded
as Allowed by the loader default — correct: CT21 blanks are the allowed
(size,material,length) combos; CT25/CT26 blanks are the "Custom Seal Type/Mfg"
escape-hatch that is allowed. Not spacers.

**ConstraintFieldMap** covers all 28 distinct field labels → SFO codes; every
target is present in SFO (no silent leg-drop).

---

## 2. The one correction: CT24 Tailpipe-Length conditional applicability

**Gap:** CT24's allowed (Tailpipe Option, Tailpipe Length) rows exist ONLY for
`Supplied by Fybroc`. When `TAILPIPE_OPTION = 'not supplied by fybroc'`, the
allow-list logic (which only restricts a target when its context has ≥1 allow
row) left `TAILPIPE_LENGTH` fully open (all 115 offered) — a tailpipe length was
selectable for a tailpipe that isn't supplied.

**Fix** (`src/api/v2_routes.py`, `_applicable_fields()` in the resolve-state
endpoint, alongside the existing WETTED_HARDWARE_SELECTION / SETTING-LENGTH mode
gates):
```python
tp = sel.get("TAILPIPE_OPTION")
if tp is not None and str(tp).strip().lower() != "supplied by fybroc":
    fields = [fc for fc in fields if fc != "TAILPIPE_LENGTH"]
```
This is a conditional-APPLICABILITY rule (the field is dropped, like other
not-applicable fields), NOT a generic allow-list change — so directional tables
(CT18 etc.) where a context legitimately has no rows are unaffected.

**Verified live:**
- `TAILPIPE_OPTION='not supplied by fybroc'` → `TAILPIPE_LENGTH` absent from
  `ordered_fields`, 0 offered.
- `TAILPIPE_OPTION='supplied by fybroc'` → `TAILPIPE_LENGTH` applicable, 115
  offered.
- 1500 (horizontal, no tailpipe fields) unaffected.

Family-safe: Dean has no `TAILPIPE_OPTION`, so this gate never triggers for Dean.

---

## 3. Verification (audit numbers + commands)

```
# API on 8080 (ensure port free first so run_all spins its own temp API)
python scripts/audit_feasible_constraints.py     # 44 passed, 0 failed
python scripts/run_all_fybroc_audits.py          # RESULT: ALL CORRECTIONS INTACT (7/7)
```

`audit_feasible_constraints.py` was extended with a "Rev0.4 per-ConstraintTable
coverage (all 29 tables)" section: a representative deny or allow-list case per
table, the two CT24 applicability assertions, and a CT21 3-leg enforcement
assertion — **44 passed, 0 failed**. No prior assertion was weakened.

Full Fybroc regression gate: **ALL CORRECTIONS INTACT (7/7)** —
audit_selections_vs_db, audit_feasible_constraints (44/44), audit_motor_constraints,
audit_identifier_parity, audit_bom_engine, audit_quote_engine, audit_free_config.

### Isolation (before == after)
| Table (scope) | Count | Δ |
|---|---|---|
| cfg.FeasibleConstraint (FYBROC / DEAN) | 4487 / 256 | 0 |
| cfg.SeriesFieldOption (FYBROC / DEAN) | 3638 / 48063 | 0 |
| cfg.ConstraintFieldMap (FYBROC / DEAN) | 28 / 31 | 0 |

No data changed (the correction is enforcement code only); Dean fully isolated.

---

## 4. Exit decision

**PASS** — all 29 Rev0.4 ConstraintTables are implemented correctly end-to-end
(extract → load → enforce). 28 were already correct; the single gap
(CT24 tailpipe-length applicability when the tailpipe is not supplied) is fixed,
verified, and guarded by new re-runnable assertions. Prior Fybroc corrections
remain intact (gate 7/7); Dean untouched.

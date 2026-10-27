# Dean Motor Numbering + Price Adders — Exit Evidence

**Milestone:** Adopt the new `workbooks/Dean/Motor Numbering.xlsm` as the authoritative
Dean motor source. Replace the old inert/frame-only motor with a real 10-field motor
spec → 4-char Combined Alphanumeric Code (brand letter + 3-char base), enforce the
34,084 enumerated combinations, and price the motor (numeric where present, C.F.
otherwise). Dean-only; Fybroc frozen. FULL milestone.
**Result:** PASS (with one disclosed pre-existing + two disclosed data gaps). See exit-gate
decision at the bottom.

---

## 1. Deliverables

| Artifact | Type | Note |
|---|---|---|
| `scripts/load_dean_motor_numbering.py` | NEW | Parses `Pricing` sheet: options `Q1:AC72`, combos `R95:AG34179`. Loads MOTOR_SPEC combos, 9 motor option fields, motor price. **Strictly Dean-family-scoped** on every write. |
| `src/api/dean_identifier.py` | EDIT | MOTOR_SPEC segment (10 fields, width 4) + `resolve_motor_spec()`; motor PN group = the 4-char code; `motor_options=''`. FRAME_SIZE canonicalized (UPPER + VP→HP) at resolve. |
| `src/api/v2_routes.py` | EDIT | Dean pricing branch resolves motor price from `price.DeanMotorPrice`; MOTOR_SPEC added to `combo_allowlists`. |
| `scripts/audit_dean_motor_numbering.py` | NEW | Re-runnable milestone audit (27 checks). |
| `scripts/audit_dean_config_accuracy.py` | EDIT | Excludes motor-domain fields (authored by Motor Numbering.xlsm, not Pump Constraints). |
| DB | DATA (Dean-only) | MOTOR_SPEC 34,084 combos (DEAN batch 9); 9 motor option fields × 37 series (1,813 rows); FRAME_SIZE canonicalized in place; `price.DeanMotorPrice` 34,084 rows (491 numeric / 33,593 C.F.). |

## 2. Authoritative source (confirmed from the workbook)
`Pricing` sheet. Options `Q1:AC72` = the motor option fields. Combinations `R95:AG34179`
= 34,084 allowed motor specs, each a 4-char Combined code + a Price. Price column: **491
numeric, 33,593 `C.F.`** (verified). Brand→letter: ABB/Baldor B, Leeson L, Marathon M,
Nidec N, Siemens S, TECO T, Toshiba H, WEG W, Dean Choice X. Code width uniformly 4.

## 3. FRAME_SIZE reconciliation (per user direction)
- User decisions: motor workbook authoritative (Option 1); `143t`→`143T` (UPPER);
  `…VP`≡`…HP` (engineering). **Do NOT tamper with each series' applicable frame set.**
- Implementation: FRAME_SIZE values **canonicalized in place** (UPPER + VP→HP), de-duping
  case collisions; each series keeps exactly the frames it already allowed (applicability
  preserved; nothing added/removed). After canon: 68 of the 71 motor frames overlap series
  applicability; 21 applicable "big" frames (`404*`, `449T`, `364T/TC`, `365T/TC`, …) have
  **no motor combination** in this workbook; 3 motor-only `HP` frames aren't applicable to
  any series.

## 4. Milestone audit — `scripts/audit_dean_motor_numbering.py`
Command: `$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_motor_numbering.py` (API on 8080).
Result: **27 passed, 0 failed.** Covers: 34,084 combos all 4-char & unique; valid brand
letter; DeanMotorPrice 491 numeric / 33,593 C.F.; 9 motor fields offered for all 37 Dean
series; FRAME_SIZE canonical; live priced combo (`T00T` → $661.23 **found** in total,
py==SQL parity); no-combo frame (`404T` → clean `0000`, C/F, no `?` in PN, parity);
Fybroc isolation (non-Dean SFO 2096, SegmentCombinationImport 300608 unchanged).

## 5. Cross-family / prior-correction regression
`scripts/run_all_fybroc_audits.py` → **ALL CORRECTIONS INTACT (9/9)**: selections_vs_db,
feasible_constraints, motor_constraints, identifier_parity, bom_engine, quote_engine,
free_config, fybroc_pricing, fybroc_motor_cpq.

Core Dean audits: `audit_dean_config.py` 28/0; `audit_dean_wet_end_resolve.py` 32/0.

## 6. Isolation
Fybroc watermarks unchanged across the milestone: `cfg.FeasibleConstraint` 4743,
non-Dean `cfg.SeriesFieldOption` 2096, non-Dean `stg.SegmentCombinationImport` 300608,
`cfg.ConfiguredProduct` non-DEAN 1196. Verified in the motor audit (§4) and the Fybroc
gate's `audit_selections_vs_db` (CLEAN).

## 7. INCIDENT (detected, contained, resolved) — Fybroc collateral delete
During development, the **first** loader run had an un-scoped
`DELETE FROM cfg.SeriesFieldOption WHERE FieldCode IN (<9 motor fields>)` that deleted
**16 Fybroc `MOTOR_CONTROL` rows** (Fybroc shares the `MOTOR_CONTROL` field code).
- Detected by `audit_selections_vs_db.py` (expected 2096, had 2080, 16 MISSING).
- **Restored** by re-running Fybroc's own canonical loader `scripts/load_all_series.py`
  (strictly `PumpFamilyId=2`) → audit CLEAN (2096). Dean untouched by the restore.
- **Fixed** the loader: every DELETE/UPDATE is now `PumpFamilyId=DEAN`-scoped; the
  watermark uses `PumpFamilyId<>DEAN`. Re-ran clean; Fybroc gate 9/9.
- Lesson recorded: `cfg.SeriesFieldOption` is SHARED and Fybroc reuses some field codes
  (`MOTOR_CONTROL`, `FRAME_SIZE`); Dean writes MUST be family-scoped, with
  `audit_selections_vs_db.py` as a checkpoint after any Dean SFO write.

## 8. Known gaps (disclosed, not blocking)
- **Motor price mostly C/F (by source):** 33,593 of 34,084 combinations are `C.F.` in the
  workbook; only 491 carry a number. Loaded faithfully — numeric where present, C/F
  otherwise. Not a defect; it's the source state.
- **21 applicable frames have no motor combination** (`404*`, `449T`, `364T/TC`,
  `365T/TC`, `405T/TC`, `444T/TC/TSC`, `445T/TC/TSC`, `447T/TC/TSC`). A config on those
  frames resolves the motor group to the clean `0000` placeholder and prices C/F (never a
  `????` PN). Pending engineering adding those motor combos.
- **No standard frame per series:** `Pump Constraints` marks all frames `X` (applicable),
  none `STD`. So a freshly-STD-seeded Dean config has FRAME_SIZE unset → motor `0000`
  until a frame is chosen. Faithful to the source (no standard frame exists).
- **PRE-EXISTING (not this milestone): `scripts/audit_dean_config_accuracy.py`** has a
  residual 444-row EXTRA for series-level **Flush Plan** sub-fields (created 2026-10-26,
  the D110 Flush milestone — a day BEFORE motor work on 2026-10-27). This standalone audit
  (not part of the Fybroc gate) does not model D110's series-level flush fields. The motor
  milestone's own EXTRA was removed by excluding motor-domain fields; the residual flush
  divergence is pre-existing and out of scope here. Verified by row CreatedAt timestamps.

## 9. Exit-gate decision — PASS
| Criterion | Verdict |
|---|---|
| 34,084 motor combos loaded, 4-char unique codes, valid brand | PASS |
| Motor price numeric (491) / C.F. (33,593) matches source | PASS |
| Motor PN segment = 4-char code; py==SQL parity | PASS |
| Numeric motor price flows to total; C/F otherwise | PASS |
| No-combo frame → clean `0000` (never `????`) | PASS |
| 9 motor fields offered per Dean series; FRAME_SIZE canonical + applicability preserved | PASS |
| Fybroc gate 9/9 ALL CORRECTIONS INTACT; isolation watermarks unchanged | PASS |

**Motor Numbering milestone PASS.** Returning to the CPQ roadmap: resume at **Phase D
(Accounts/contacts)** on the user's go-ahead. D150 remains PARKED.

# Fybroc Rev0.4 Motor Constraints — Exit Evidence

**Milestone slice:** FYBROC Rev0.4 Motor Constraints authoritative adoption + enforcement verification
**Family:** FYBROC (PumpFamilyId 2) — frozen; DEAN (PumpFamilyId 1) must be untouched
**Date:** 2026-08-26
**Mode:** FULL (authoritative-source adoption + enforced-table verification + cross-family blast radius)
**Active publication:** pub 2 (`F140-corrections-v1`, VersionCode as in cfg.MetadataPublication)

---

## 1. Deliverables inventory & exit-gate criteria

**Objective:** Make the Rev0.4 `Motor Constraints` datasheet the authoritative
source of Fybroc motor gating (allowable Alt Size × Frame Size × MotorHpRpm ×
MotorType per series), extracted correctly, loaded family-safe into
`cfg.MotorConstraint`, and enforced at runtime.

**Concrete, checkable exit-gate criteria:**

1. Extractor reproduces the real Rev0.4 sheet layout exactly — every series
   block's start column and every mini-table's row count derived from the sheet
   (not hardcoded), 19 blocks total.
2. `cfg.MotorConstraint` (active pub, FYBROC) holds exactly that data: 3278 rows,
   with the per-(scope × dimension-pair) counts matching the sheet.
3. Loader is family-safe (FYBROC-scoped DELETE + INSERT; no un-scoped DELETE).
4. Runtime enforces the allow-lists (no illegal MOTOR_HP / MOTOR_RPM /
   FRAME_SIZE value leaks past the API) for every series that has motor rules.
5. Cross-family regression `run_all_fybroc_audits.py` = **ALL CORRECTIONS
   INTACT** (7/7).
6. Dean isolation: Dean row counts unchanged; `cfg.MotorConstraint` DEAN = 0.

---

## 2. What was actually found (honest summary)

**The Rev0.4 Motor Constraints data, its extractor, its family-safe loader, and
its runtime enforcement were ALREADY correct and in place** (Rev0.4 Motor
Constraints content is byte-identical to Rev0.3, per the v1.15 workbook-wide
diff, and was already loaded). This slice therefore **verified** authority and
enforcement against the real sheet rather than re-writing anything. Re-running
the extractor produced a **byte-identical model** (only the `generated_utc`
timestamp changed).

**The user's request spec contained two transcription errors, which the sheet and
the existing code do NOT share** (the code reads the real sheet, so it was already
right):

- **3000 series columns.** The request placed 3000 at columns AH–AR — identical to
  2530. The real sheet's row-2 series banners put **3000 at AV (col 48)**:
  Alt×Frame **AV–AX**, Alt×HpRpm **AZ–BB**, Frame×HpRpm **BD–BF**. AH–AR is 2530
  only.
- **1500/1600 Alt×HpRpm band.** The request gave F–G (2 columns, no `Allowed?`).
  The real sheet has an `Allowed?` column at **H**, so this band is 3 columns
  (F–H) like every other mini-table.

Both were confirmed by a read-only probe of
`workbooks/Fybroc/Fybroc Configuration Rev0.4.xlsx` sheet "Motor Constraints"
(row-5 header scan + row-2 banner scan + per-band non-blank row counts).

---

## 3. Verified Rev0.4 layout (from the sheet, not the spec)

Row-2 series banners → block start columns: 1500/1600=B(2), 1530/1630=T(20),
2530=AH(34), **3000=AV(48)**, 5500=BJ(62), 5530=BX(76). Each mini-table = 3
columns (Dim1, Dim2, `Allowed?`) followed by 1 blank spacer column; header row 5,
data from row 6, extent read dynamically to the first blank key cell.

| Series | Alt×Frame | Alt×HpRpm | Frame×HpRpm | HpRpm×MotorType | block total |
|--------|-----------|-----------|-------------|-----------------|-------------|
| 1500 and 1600 | B–D (282) | F–H (525) | J–L (55) | N–P (170) | 1032 |
| 1530 and 1630 | T–V (152) | X–Z (375) | AB–AD (38) | — | 565 |
| 2530 | AH–AJ (96) | AL–AN (200) | AP–AR (40) | — | 336 |
| 3000 | AV–AX (76) | AZ–BB (78) | BD–BF (56) | — | 210 |
| 5500 | BJ–BL (201) | BN–BP (417) | BR–BT (50) | — | 668 |
| 5530 | BX–BZ (134) | CB–CD (303) | CF–CH (30) | — | 467 |

**Total = 3278 rows across 19 blocks.** The extractor output
(`docs/evidence/F120/FYBROC_MOTOR_CONSTRAINT_MODEL.json`) matched every one of
these 19 counts exactly, and the DB (`cfg.MotorConstraint`, active pub, FYBROC)
matched them exactly.

**Value semantics — pure allow-list.** Each `Allowed?` column contains a single
token throughout: `Allowed` for most blocks, `X` for 2530 Alt×Frame, 5530
Alt×Frame, and 5530 Alt×HpRpm. There are **no deny rows and no mixed columns**
(distinct-value tally per column confirms one token each). A present (Dim1,Dim2)
row = an allowed combination; `X` vs `Allowed` is a cosmetic presence marker, not
a deny. The runtime index-builder loads every present row as allowed and does not
filter on the token — correct for allow-list semantics.

---

## 4. Verification performed (commands + numbers)

All run with the project venv `.venv\Scripts\python.exe`, `PYTHONPATH=.`.

### 4.1 Extractor reproduces the sheet
```
.\.venv\Scripts\python.exe scripts\compile_fybroc_motor_constraint_model.py
```
→ `motor_constraint_block_count=19`, `total_motor_constraint_rows=3278`. All 19
per-block counts matched the read-only probe of the sheet. Re-run diff vs the
committed JSON = only `generated_utc` / `git_working_tree_clean` changed (zero
data change), proving the extractor is stable and the data was already
authoritative.

### 4.2 DB holds the authoritative data, family-safe
`cfg.MotorConstraint` (active pub 2): **FYBROC = 3278, DEAN = 0.** Per-(scope ×
dimension-pair) counts matched section 3 exactly. Loader
`scripts/load_motor_constraints_to_sql.py` deletes/inserts scoped to
`MetadataPublicationId=? AND PumpFamilyId=?` (FYBROC) — family-safe; no reload was
needed this slice because the data already matched.

### 4.3 Runtime enforcement — standing audit
```
.\.venv\Scripts\python.exe scripts\audit_motor_constraints.py
```
→ **91 passed, 0 failed.** For 7 series (1500/1530/1600/1630/2530/3000/5500) ×
4 Alt sizes each, the API's offered MOTOR_HP / MOTOR_RPM / FRAME_SIZE options are
a faithful subset of the DB allow-lists (no illegal leaks), and every series
completes a full valid walk. Expectations derived from the DB, not hardcoded.

### 4.4 5530 (not in the standing audit's series list) — targeted probe
5530 was verified separately (scope `5530`, 4 Alt sizes): MOTOR_HP and FRAME_SIZE
offered options had **no leaks** vs the DB allow-lists, and the 5530 valid walk
**COMPLETE**. (This gap in the standing audit's series list is noted in §6.)

### 4.5 Cross-family / prior-correction regression
```
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\run_all_fybroc_audits.py
```
→ **RESULT: ALL CORRECTIONS INTACT (7/7):** audit_selections_vs_db (2096=2096
clean), audit_feasible_constraints (44/44), audit_motor_constraints (91/0),
audit_identifier_parity (44/0), audit_bom_engine (38/0), audit_quote_engine
(22/0), audit_free_config (32/0). Port 8080 was freed before the run (the gate
spins its own temp API).

### 4.6 Isolation / no-collateral-damage (before == after; nothing reloaded)
| Table (family) | Baseline | Actual | Result |
|---|---|---|---|
| Dean FeasibleConstraint | 256 | 256 | unchanged |
| Dean SeriesFieldOption | 48063 | 48063 | unchanged |
| Dean MotorConstraint | 0 | 0 | unchanged |
| Fybroc MotorConstraint | 3278 | 3278 | unchanged |
| Fybroc FeasibleConstraint | 4487 | 4487 | unchanged |

`cfg.MotorConstraint` has an additive, non-null-defaulted `PumpFamilyId` column
already in place; the shared schema is backward-compatible. No shared-table row
counts changed (no data reload occurred this slice).

### 4.7 Build/verify
```
.\.venv\Scripts\python.exe -c "import src.api.app; import src.api.v2_routes"
```
→ `imports OK`. Temp probe scripts (`scripts/_tmp_*`) were removed after use.

---

## 5. Exit-gate decision — PASS

| # | Criterion | Result |
|---|---|---|
| 1 | Extractor reproduces real Rev0.4 layout (19 blocks, dynamic extents) | **PASS** — all 19 counts matched sheet |
| 2 | `cfg.MotorConstraint` = 3278 FYBROC, counts match sheet | **PASS** |
| 3 | Loader family-safe (FYBROC-scoped) | **PASS** |
| 4 | Runtime enforces allow-lists, no leaks, valid walks complete | **PASS** — audit 91/0 + 5530 probe |
| 5 | `run_all_fybroc_audits.py` ALL CORRECTIONS INTACT 7/7 | **PASS** |
| 6 | Dean isolated; DEAN MotorConstraint = 0 | **PASS** |

---

## 6. Known gaps / disclosures (not glossed)

- **`F_MotorHpRpm × F_Motor Type` block is loaded but INERT for gating.** This
  block exists only for 1500/1600 (170 rows) and maps HpRpm → allowed composite
  motor-type spec strings (e.g. `TEFC_PE_230/460-3-60`). The runtime configurator
  has **no single `MOTOR_TYPE` field** — motor type is decomposed into separate
  fields (MOTOR_ENCLOSURE, MOTOR_EFFICIENCY, MOTOR_VOLTAGE, MOTOR_HERTZ, etc.), so
  this allow-list is stored but not enforced. **Pending engineering:** decide
  whether to gate the decomposed motor fields from this block. Data is present
  and correct; enforcement is not wired.
- **Standing motor audit series list.** `audit_motor_constraints.py` sweeps
  1500/1530/1600/1630/2530/3000/5500 but not **5530** (verified this slice by a
  separate targeted probe — 0 leaks, walk complete). Recommend adding 5530 to the
  standing audit's `SERIES` list in a future LEAN pass so it is guarded
  automatically.
- **7500 / 8500** have no motor-constraint rules in the sheet (the same
  8-of-10-series coverage as the Constraints sheet). This is a source-data
  property, not a defect.

---

## 7. Reproducibility — exact commands
```
# read-only sheet probe (temp, removed after use) confirmed layout + row counts
.\.venv\Scripts\python.exe scripts\compile_fybroc_motor_constraint_model.py
.\.venv\Scripts\python.exe scripts\audit_motor_constraints.py
Get-NetTCPConnection -LocalPort 8080 -State Listen | %{Stop-Process -Id $_.OwningProcess -Force}
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\run_all_fybroc_audits.py
.\.venv\Scripts\python.exe -c "import src.api.app; import src.api.v2_routes"
```

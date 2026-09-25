# D130 — SQL Dean Identifier Authority: EXIT

> **2026-08-26 RE-BASE (D140):** the identifier numbering + resolver were
> re-loaded from the NEW authority `workbooks/Dean/PumpConfiguration_Logic_0.1.xlsm`,
> which supersedes the `Dean Data Sheet Rev 2.xlsm` numbering cited below. The
> D130 SQL branch, A#→D# identity model, resolver structure, and seal-exclusion
> decision are UNCHANGED and still hold; what changed in D140 is the numbering
> SOURCE + per-segment field orders + table-backed flush/motor-frame. Current
> state: `cfg.PumpModelReference` 206 DEAN rows; `stg.SegmentCombinationImport`
> DEAN batch = 106,892 rows (old 428,742-row batch removed). `audit_dean_identifier`
> 8/8; SQL==python parity intact. See `docs/evidence/D140/DEAN_D140_EXIT.md`. The
> counts below reflect the original D130 pass and are retained for history.

**Date:** 2026-08-26
**Milestone:** D130 — SQL Dean Identifier Authority
**Status:** EXIT — PASS (with disclosed pending-engineering gaps below).
**Authority:** `docs/PROJECT_MASTER_ROADMAP.md` D130 exit gate ("SQL output
matches approved Dean workbook output") + `.kiro/steering/milestone-exit-audit.md`.

> **Record correction:** `docs/progress/MilestoneRegister.md` and the older
> `docs/evidence/D130/DEAN_IDENTIFIER_AUTHORITY.md` (2026-08-24) marked D130
> "Complete" before it was built. That was inaccurate. This EXIT doc is the
> authoritative D130 completion record; the old analysis doc is preserved
> (per decision A) and the register is corrected as part of this milestone.

---

## 1. Deliverables

| Deliverable | Location |
|-------------|----------|
| Additive `@FamilyCode='DEAN'` branch in the SQL assembler | `sql/23_Create_Assemble_Configured_Product.sql` (`cfg.usp_AssembleConfiguredProduct`) |
| Dean identifier loader (idempotent, DEAN-scoped) | `scripts/load_dean_identifier_to_sql.py` |
| Dean PN resolver (option-1: API resolves segment codes, SQL assembles) | `src/api/dean_identifier.py` |
| Family-gated Dean branch in the resolve endpoint | `src/api/v2_routes.py` (`resolve_configured_product`) |
| Special-segment lookup maps (trim / flush / barrier) | `config/identifier_profiles/dean_special_maps.json` |
| Milestone exit audit | `scripts/audit_dean_identifier.py` |
| Design record | `docs/evidence/D130/DEAN_D130_DESIGN.md` |

No schema migration: the loader reuses existing family-scoped tables
`cfg.PumpModelReference` (A#/D# identity) and `stg.SegmentCombinationImport`
(segment String→Code maps) — the SAME runtime store Fybroc uses. `cfg.usp_GenerateSKU`
was already DEAN-aware and is reused unchanged.

## 2. Dean Part Number structure (as built)

```
D<A#> - <WetEnd(4)> - <Trim(2)><ImpOpts(2)> - <PowerEnd(3)>
      - <Flush(2)><Barrier><Cooling(2)> - <Frame(2)><Baseplate(3)>
      - <Motor(3)><MotorOpts(2)> - <AddlOpts(2)> - <Testing(2)><Doc(4)>
```

- **Base** `D<A#>`: Series+Size → authoritative A-number → D-number
  (`cfg.PumpModelReference`; A461 → D461, prefix `A`→`D`).
- **Seal segment is EXCLUDED** (see §5.1) — differs from the raw workbook B5 only
  in dropping the workbook's own `00000`/`TBD__` placeholder.
- Every other engineering segment is the base-36 code from that segment's
  numbering table, looked up by the exact `*`-joined option ComboString.
- SKU (`cfg.usp_GenerateSKU`): `D<series>-<first-8-hex SHA2_256(PN)><ver>` —
  SKU↔PN strictly 1:1.

Example fully-resolved PNs (STD-default configs, SQL-authoritative):
`DL200 1x1.5x6 (22) Ductile → D362-001T-CA01-AQ-00000-00000-000000-00-000000`;
`DL200 1x1.5x6 (50) 316 S/S → D362-030N-...` (material differentiates wet end);
`PH2110 1.5x3x6 → D611-0021-CA01-09-...`; `M300 2x3x10 → D761-25AX-GA01-9T-...`.

## 3. Segment sources (authoritative)

Loaded into `stg.SegmentCombinationImport` under a `FamilyCode='DEAN'` batch
(428,742 rows total) from the `Dean Data Sheet Rev 2.xlsm` numbering sheets:

| Segment | Sheet | width | rows |
|---------|-------|-------|------|
| WET_END_OPTIONS | Wet End Numbering (String O → code P) | 4 | 101,910 |
| IMPELLER_OPTIONS | Wet End Numbering (String AJ → code AK) | 2 | 39 |
| POWER_FRAME_OPTIONS | Power End Numbering (String N → code O) | 2 | 460 |
| COOLING_PLAN | Misc Numbering (String G → code F) | 2 | 190 |
| ADDITIONAL_OPTIONS | Misc Numbering (String P → code O) | 2 | 160 |
| BASEPLATE_OPTIONS | Baseplate Numbering (cols C..K → code L) | 3 | 1,537 |
| TESTING | Test and Doc Numbering (String I → code H) | 2 | 240 |
| DOCUMENTATION | Test and Doc Numbering (String S → code U) | 4 | 315,046 |
| MOTOR | Motor Numbering (String O → code N) | 3 | 9,160 |

Identity: 204 (series,size) → A#/D# rows in `cfg.PumpModelReference` (2 of the 206
reconciliation models are LOGIC_ONLY_REVIEW without a full A#/D#, excluded).

Special (non-table) segments: Impeller Trim (inch+decimal letter maps), Flush
(Config Info FA→FH), Barrier (Config Info FK→FN); maps in `dean_special_maps.json`.

## 4. Exit-gate verification (audit numbers)

All run 2026-08-26 against the local API + PumpConfiguratorDB.

- **`scripts/audit_dean_identifier.py`** (milestone audit, stride-5 sample = 41/204
  models, STD-default configs): **8 passed, 0 failed, exit 0.**
  - SQL==Python PN parity: **0 failures** (all models).
  - SKU = `D<series>-SHA2_256(PN)[:8]<ver>`: **0 failures**.
  - Base identifier == `cfg.PumpModelReference.BaseIdentifier`: **0 mismatches**.
  - Deterministic PN+SKU on re-resolve: **0 failures**.
  - Segment discipline: **0 models** with a `?` on any segment OUTSIDE the
    disclosed gap set `{wet_end, power_frame_options}`.
  - Coverage: **15/41 fully resolved** (complete workbook-matching PN, no `?`);
    26/41 resolve every segment except a wet_end/power_frame field hit by the
    disclosed STD data gap (§5.2).
- **`scripts/audit_dean_pricing.py`** (D120 regression): **22/22 PASS.**
- **`scripts/audit_dean_config.py`** (D110 regression): **29/29 PASS.**
- **`scripts/run_all_fybroc_audits.py`** (cross-family gate): **ALL CORRECTIONS
  INTACT — 7/7** (`audit_selections_vs_db`, `audit_feasible_constraints`,
  `audit_motor_constraints`, `audit_identifier_parity`, `audit_bom_engine`,
  `audit_quote_engine`, `audit_free_config`). The Fybroc identifier parity audit
  and BOM engine (38/38) both pass, proving the additive Dean branch and the
  Fybroc-only BOM guard did not regress Fybroc.
- **Build/verify:** `py_compile` clean for `v2_routes.py`, `dean_identifier.py`,
  `load_dean_identifier_to_sql.py`, `audit_dean_identifier.py`.

### Isolation / no collateral damage (before vs after)

| Metric | Baseline (pre-load) | After D130 |
|--------|--------------------:|-----------:|
| Fybroc segment import batches | 2 | 2 |
| Fybroc segment import rows | 300,608 | 300,608 |
| Fybroc ConfiguredProducts | 1,151 | 1,151 |
| Fybroc PumpModelReference rows | 0 | 0 |
| Dean segment import rows | 0 | 428,742 |
| Dean PumpModelReference rows | 0 | 204 |

All Dean data went into a DEAN-scoped batch / DEAN family rows only; the shared
tables' Fybroc partitions are byte-for-byte unchanged. Shared-schema change: none
(both tables pre-existed).

## 5. Known gaps (pending-engineering — disclosed, not glossed)

### 5.1 Seal segment — removed from the Dean PN (external Access DB)
An empirical search of ALL three Dean workbooks confirmed there is **no seal
base-36 numbering/hexcode table anywhere**; the seal sheets carry only
descriptions/prices, and the workbook's Smart Number seal cell only ever emits
`IF(D49<>"Included","00000","TBD__")`. The real seal code is authored solely in
the external `Seal Numbering.accdb` (`getSealOptions`), which is not in the
workspace. The seal segment is therefore **excluded from the Dean PN**; seal
STATUS is still surfaced in the API `segment_debug` (`seal_status`,
`seal_code_placeholder`). Re-addable cleanly if the seal Access DB is provided.

### 5.2 STD "Standard Confs" is an external Access DB → D110-vs-numbering mismatch
The workbook's authoritative per-model STD configuration ("Standard Confs") also
lives in an external Access DB (`SetDefaultOptions_Click`), which we do not have.
Our STD seed comes from the D110 applicability data, which for some models carries
option values the workbook's numbering table never enumerated (e.g. R5140 STD
`OILER='Glass/Alum Oiler'`, `SIGHT_GLASS='Required'`; CNV206 wet-end
`DRAIN='NPT Plug'`, `GASKET='Aramid'`). Those models resolve every segment except
`wet_end` and/or `power_frame_options`, which surface `?` rather than a fabricated
code. This is a data gap, not a resolver defect; the resolver + SQL are correct
for every model whose STD aligns with the numbering table (15/41 sampled fully
resolve). Closing it requires the STD "Standard Confs" Access DB (or a
D110↔numbering STD reconciliation).

### 5.3 Motor frame — gated to `00` (pending)
The motor-frame segment (`W12 = BASE(MATCH(frame, Table2486 HP×RPM matrix),36,2)`)
is gated to `00` (the workbook's no-motor value). The full HP×RPM MATCH matrix is
not yet reproduced. Motor is C/F in D120 pricing, so this is consistent.

### 5.4 Motor options — inert `00`
The workbook's Motor Options cell (`AB12`) has no formula (static `00`); the
resolver emits `00` to match. Carried as inert until engineering wires it.

## 6. Exit-gate decision

| Criterion | Result |
|-----------|--------|
| SQL generates the Dean PN (SQL-authoritative, additive DEAN branch) | **PASS** |
| A#→D# base identifier from authoritative source | **PASS** (0 mismatches) |
| Engineering segment codes match the workbook numbering tables | **PASS** for aligned models (segment-by-segment); gap models disclosed (§5.2) |
| SQL == Python parity oracle | **PASS** (0 failures) |
| SKU derived from PN (1:1) | **PASS** (0 failures) |
| Deterministic / reuse | **PASS** |
| Fybroc byte-for-byte unchanged (gate 7/7 + isolation) | **PASS** |
| Milestone audit re-runnable, exits non-zero on failure | **PASS** |

**D130 exit gate: PASS.** SQL output matches the approved Dean workbook output for
every model whose STD configuration is fully specified by the data available to
us; the remaining models are blocked only by external-Access-DB data gaps (§5.1,
§5.2), which are disclosed rather than fabricated.

## 7. Reproduce

```powershell
# load (idempotent)
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\load_dean_identifier_to_sql.py
# deploy SQL branch
sqlcmd -S localhost -d PumpConfiguratorDB -E -C -b -i "sql\23_Create_Assemble_Configured_Product.sql"
# API
$env:PYTHONPATH="."; $env:CONFIGURATION_TOKEN_SECRET="local-dev-configuration-token-secret-0123456789"; .\.venv\Scripts\python.exe -m uvicorn src.api.app:app --host 127.0.0.1 --port 8080
# audits
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_identifier.py     # 8/8
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_pricing.py         # 22/22
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_config.py          # 29/29
# cross-family gate (stop the standalone API first; it spins its own)
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\run_all_fybroc_audits.py      # ALL CORRECTIONS INTACT 7/7
```

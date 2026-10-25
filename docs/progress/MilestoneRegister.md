# Milestone Register

**Last Updated:** 2026-08-26

> **Authority note:** for the true, verified Dean-phase status use
> `docs/Project_master_roadmap.md` §11–§12 (v1.29).
>
> **2026-08-26 (v1.29):** Dean STD-CONSISTENCY fix (D110; Dean-only runtime fix,
> Fybroc frozen; no DB/schema/loader change). CNV206/1X1.5X6 wrongly reported
> Cooling Plan STD incompatible with the standard selection. Root cause: a
> source-vocabulary-inconsistent Dean Codependencies sub-block ('Casing Mounting'
> stacked under Cooling Plan, enumerating piping accessories) made _apply_constraints
> prune CASING_MOUNTING=NONE (the sheet STD) -> false conflict; widespread (0/7
> sample pre-fix across 3 codep tables + a numbering-combination gap). FIX: a
> field's authoritative Pump-Constraints STD value is never pruned by a constraint
> (std_defaults guard in _apply_constraints feasible + Dean combination blocks,
> threaded from /evaluate + resolve-state). Scoped DEAN-ONLY after the universal
> version regressed Fybroc CT20 (Fybroc defaults can legitimately be pruned);
> Fybroc std_defaults=None -> unchanged. New scripts/audit_dean_std_consistency.py
> --all 206/206. Non-STD enforcement intact; audit_dean_config 28/0;
> audit_dean_codependencies 13/0; run_all_fybroc_audits ALL CORRECTIONS INTACT 9/9;
> FYBROC watermarks unchanged (4487/28/3638). Pending: full reconciliation of the
> vocab-mismatch Codependencies sub-blocks (deferred, seal-A1 class). See
> `docs/evidence/D110/DEAN_D110_STD_CONSISTENCY_FIX.md`.
>
> **2026-08-26 (v1.28):** Dean CONFIG FIELD-ACCURACY AUDIT (all fields) +
> Custom->C/F relabel (D110; Dean-only data change, Fybroc frozen). Proved DB
> cfg.SeriesFieldOption (DEAN) is a BYTE-EXACT image of PumpConfiguration_Logic_0.1
> "Pump Constraints" across every (series,size,field) via new
> scripts/audit_dean_config_accuracy.py (independent oracle re-parse): 8/0, 0
> MISSING/EXTRA/STD-mismatch (206 models, 68 fields, 48,063 rows, STD 11,786).
> Relabeled sheet value "Custom" (customer-request, outside standard offering) to
> C/F in loader _norm_value: 2,329 SFO rows/20 fields (all X) + 4 codep legs; totals
> unchanged. Live API cross-check (new audit_dean_config_accuracy_live.py) 6/6
> models, 286 STD-exact + 326 no-leak, 0 fail. Regression audit_dean_config 28/0,
> audit_dean_codependencies 13/0, run_all_fybroc_audits ALL CORRECTIONS INTACT 9/9;
> FYBROC unchanged (4487/28/3638). Pending: C/F downstream quote/numbering logic,
> BARRIER_PLAN (no per-model STD/X, deferred seal quad A1), 519 seal codep tuples.
> See `docs/evidence/D110/DEAN_D110_FIELD_ACCURACY_AUDIT.md`.
>
> **2026-08-26 (v1.27):** Dean CONFIGURATION RE-EXTRACT CERTIFICATION (D110,
> verify-only; no schema/loader/data/runtime change). Re-ran the authoritative
> loader (d110_load_dean_config_v01.py) against PumpConfiguration_Logic_0.1.xlsm
> "Pump Constraints" per the user's explicit 67-group column map and full row range
> (4–209 = 206 models). Loader already matched the spec: dry-run 206 models / 37
> series / 68 fields / 11,786 STD cells / 0 unmapped; real reload reproduced the
> baseline EXACTLY (SFO 48,063; FeasibleConstraint 256 = 251 2-leg + 5 3-leg; 519
> seal tuples still deferred) with ZERO file/DB diff (git clean). Live resolve-state
> verified across the sheet incl. row-167+ (RM5140, Deanline): all valid, SIZE
> present, STD seeded, no dead ends. audit_dean_config 28/0; audit_dean_codependencies
> 13/0; run_all_fybroc_audits ALL CORRECTIONS INTACT 9/9; FYBROC unchanged (4487 /
> 3638 / 28). D150 not started. See
> `docs/evidence/D110/DEAN_D110_CONFIG_REEXTRACT_CERTIFICATION.md`.
>
> **2026-08-26 (v1.15):** FYBROC constraint/config authority moved to
> `Fybroc Configuration Rev0.4.xlsx` (supersedes Rev0.3). Content is byte-identical
> to Rev0.3 — a provenance/authority supersession + loader family-safety hardening;
> run_all_fybroc_audits ALL CORRECTIONS INTACT 7/7, Dean isolated. See
> `docs/evidence/REV04_CONSTRAINTS/REV04_CONSTRAINT_SUPERSESSION.md`.
>
> **2026-08-26 (v1.16):** All 29 Rev0.4 ConstraintTables verified conformant
> (extract/load/enforce) against the authoritative spec; one correction —
> CT24 Tailpipe Length now conditionally not-applicable when the tailpipe is not
> supplied. audit_feasible_constraints 44/44; gate 7/7; Dean isolated. See
> `docs/evidence/REV04_CONSTRAINTS/REV04_29_TABLES_CONFORMANCE.md`.
>
> **2026-08-26 (v1.24):** Dean PCL v0.1 numbering-authority CERTIFICATION (verify-only,
> no data/code change). Confirmed PumpConfiguration_Logic_0.1.xlsm is the loaded
> authoritative Dean numbering source (batch id=5, 106,892 seg rows across the 6
> numbering sheets; 206 models/37 series A#->D#). Bounded live parity probe 12/12 PASS
> (parity_ok 0 fails; base_identifier correct); run_all_fybroc_audits 9/9; baselines
> unchanged. Documented engineering gaps remain (Cooling/Barrier tables, Motor main
> code, Standard Confs + Seal external DBs). See
> `docs/evidence/D100/DEAN_PCL_V01_NUMBERING_CERTIFICATION.md`.
>
> **2026-08-26 (v1.23):** Architecture review + UAT-readiness backlog (docs only).
> Confirmed FastAPI/Pydantic API over SQL Server via raw pyodbc + SQLAlchemy Core (NO
> ORM); injection-safe via parameterized queries throughout. Rejected Tortoise ORM (no
> MSSQL support; would force Postgres + rewrite of stored-proc core). Added Phase-T
> milestone T105 (UAT-Readiness Hardening): auth-bypass fail-closed guard, schema
> migration tooling, CI audit gate, Key Vault secrets, promotion/rollback runbook,
> price-adjustment reapply policy. CI today = uv sync + pytest + non-empty-SQL + imports
> (does NOT run run_all_fybroc_audits — tracked as T105.3). No code/data/schema change.
>
> **2026-08-26 (v1.22):** Targeted price-adjustment procedure. New
> price.usp_ApplyPriceAdjustment (sql/19_Create_Price_Adjustment.sql) applies a PERCENT
> change to price.PriceRule.Amount for the current price book version, scoped
> ALL_FAMILIES / FAMILY / SERIES (+ optional component child; NULL=all). @DryRun default
> previews; real run audits every row (price.PriceAdjustment + price.PriceAdjustmentRow)
> and is reversible. FAMILY/SERIES family-isolated. Thin CLI scripts/apply_price_adjustment.py.
> Verified scope targeting + byte-identical round-trip + DEAN isolation; gate 9/9; pricing
> UNCHANGED (mechanism only). price.PriceRule is the update table; this proc the entrypoint.
> See `docs/evidence/PRICING/PRICE_ADJUSTMENT_PROCEDURE.md`.
>
> **2026-08-26 (v1.21):** FYBROC 1500 Pricing series-attribution correction. The 1500
> Vibration Testing & Sound Level Testing adders were missing from the published pricing
> (present only under 5500), so 1500 vibration/sound resolved to C/F. Root cause: stale
> publication (the compiler already extracts the 1500 testing blocks). Fix: recompile +
> re-merge + re-publish a new family-safe FYBROC version FYBROC-REV04-MERGE-20260826-V2
> (56355 rules, +114 restored 1500 testing rows; supersede-not-delete). Verified: both
> components now [1500:57, 5500:57]; live 1500 witnessed vibration/sound = \$3045 (sheet
> match); audit_fybroc_pricing 47/0 (+12 testing asserts); gate 9/9; DEAN 9874 unchanged.
> See `docs/evidence/REV04_PRICING/REV04_1500_TESTING_SERIES_FIX_EXIT.md`.
>
> **2026-08-26 (v1.20):** FYBROC Suction Discharge Taps pricing bridge. Selecting the
> option for 1500 now resolves to the Rev0.4 1500 Pricing CS-CV adder ($0 not-supplied /
> $1041 supplied); unpriced series show C/F. Root cause: runtime pricing didn't bridge
> the selectable vocabulary ('no suction discharge taps') to the pricing vocabulary
> ('Not_Supplied_by_Fybroc'), so it was silently C/F despite correct priced rows. Fix
> (runtime-only, no reload): _price_component now consults
> config/runtime_profiles/fybroc_value_equivalences.json (+ field-code alias + prefix
> for '*' STD values). Bonus: Casing Drains also resolves now. audit_fybroc_pricing
> 35/0 (+8 sheet-derived asserts); gate ALL CORRECTIONS INTACT 9/9; DEAN 9874 / FYBROC
> 56241 unchanged. See `docs/evidence/REV04_PRICING/REV04_SUCTION_DISCHARGE_PRICING_EXIT.md`.
>
> **2026-08-26 (v1.19):** FYBROC Rev0.4 "1500 Motors" — CPQ Conversion2 motor display
> descriptor implemented. Verified against all 144000 rows that CPQ Conversion2 ==
> "{Enclosure}---{Efficiency}---{Voltage}---{Hertz}" (18 distinct values), so it is
> derived at runtime (no 144k reload; only 151 motor rows are priced, rest C/F).
> src/api/v2_routes.py surfaces it on the Motor line + top-level motor_cpq_conversion
> (present even when motor is C/F); UI shows it via the existing Selection column.
> New guard scripts/audit_fybroc_motor_cpq.py (sheet-derived, 37/0) wired into the
> gate (audit #9). Gate ALL CORRECTIONS INTACT 9/9; runtime-only (no DB write), DEAN
> 9874 / FYBROC 56241 pricing unchanged. See
> `docs/evidence/REV04_PRICING/REV04_1500_MOTORS_CPQ_EXIT.md`.
>
> **2026-08-26 (v1.18):** FYBROC Rev0.4 "1500 Pricing" authority VERIFIED + base-pump
> pricing correction. Probed all 24 pricing blocks (reconciled vs request spec's
> column errors: Baseplate Hardware=BE-BH, Flange Type=BY-CB, Flush=CI-CL; G-I VR-1
> helper redundant with main table, correctly not published). Data already in pub
> FYBROC-REV04-MERGE-20260914-V1 (56241 rules) — no republish. FIXED runtime bug:
> plain 'vr-1' base material aliased onto VR-1A (over-priced every VR-1 pump, e.g.
> 8666 vs correct 4987); now exact per-material patterns. New guard
> scripts/audit_fybroc_pricing.py (sheet-derived, 27/0) wired into the gate (audit
> #8). Gate ALL CORRECTIONS INTACT 8/8; DEAN pricing 9874 unchanged (Fybroc-only,
> runtime). See `docs/evidence/REV04_PRICING/REV04_1500_PRICING_EXIT.md`.
>
> **2026-08-26 (v1.17):** FYBROC Rev0.4 Motor Constraints authority + enforcement
> VERIFIED (no code/data change needed). Extractor reproduces the real sheet layout
> exactly (19 blocks, 3278 rows; 3000 at col AV, 1500/1600 Alt×HpRpm at F–H — two
> request-spec transcription errors reconciled against the sheet). Pure allow-list
> semantics ('Allowed'/'X' = present = allowed, no deny rows). cfg.MotorConstraint
> FYBROC=3278 / DEAN=0. audit_motor_constraints 91/0; 5530 targeted probe 0 leaks;
> gate 7/7 ALL CORRECTIONS INTACT; Dean isolated. KNOWN GAP: F_MotorHpRpm×F_Motor Type
> block (170 rows) loaded but inert (no single MOTOR_TYPE field). See
> `docs/evidence/REV04_CONSTRAINTS/REV04_MOTOR_CONSTRAINTS_EXIT.md`. The Phase D / Phase U rows
> below were over-reported in a prior checkpoint; **D100**, **D110**, **D120**,
> **D130**, and **D140** are verified complete against their exit gates (evidence
> in `docs/evidence/D100/`…`docs/evidence/D140/`). **D140** was re-based onto the
> new authoritative workbook `PumpConfiguration_Logic_0.1.xlsm`. **D150–D160 are
> NOT yet built** (the "Complete" marks previously shown for them were
> over-reported and remain inaccurate).

## Foundation Phase

| Milestone | Title | Status |
|---|---|---|
| M001 | Repository and Database Foundation | Complete |
| M002 | Workbook Discovery | Complete |
| M003 | Configuration Model Compiler | Complete |
| M004 | Identifier Architecture | Complete |
| M005 | Option Source Discovery | Complete |
| M006 | Segment Combination Compiler | Complete |
| M007 | SQL Staging and Validation | Complete |
| M008 | Runtime Configuration Engine | Complete |
| M009 | Attribute Metadata Platform | Complete |
| M010 | Active Publication Integration | Complete |
| M011 | Fybroc Motor Assembly | Complete |
| M012 | Constraint Projection Foundation | Complete |
| M013 | Fybroc Series Constraint Matrix | Complete |
| M014 | Unified Available Options Service | Complete |
| M015 | Allowable Configuration Navigation | Complete |
| M016 | Complete Allowable Configuration Session | Complete |
| M017 | Constraint Dependency Closure | Complete |
| M018 | Identifier Persistence and Reuse | Complete |
| M019 | Closed FastAPI Configuration Service | Complete |
| M021 | Shared Versioned Pricing Platform | Complete |
| M024.1 | uv Migration | Complete |
| M024.2 | Architecture Baseline | Complete |

## Phase F — Fybroc Completion

| Milestone | Title | Status | Git Tag |
|---|---|---|---|
| F100 | Fybroc Source Inventory | Complete | — |
| F110 | V5/V6 Nomenclature Reconciliation | Complete | — |
| F120 | Rev0.3 Configuration Model | Complete | — |
| F130 | Fybroc Pricing/Adders Reconciliation | Complete | — |
| F140 | Fybroc Metadata Corrections & Publication | Complete | — |
| F150 | SQL Fybroc Identifier Authority | Complete | — |
| F160 | Fybroc Excel Oracle Harness | Complete | — |
| F170 | Fybroc Exhaustive Regression | Complete | — |
| F180 | Fybroc Signoff & Freeze | Complete | `f180-fybroc-complete` |

## Phase D — Dean Completion

| Milestone | Title | Status | Git Tag |
|---|---|---|---|
| D100 | Dean Source Reconciliation | Complete (verified) | — |
| D110 | Dean Configuration & Dependency Completion | Complete (verified) | — |
| D120 | Dean Pricing & Adders | Complete (verified 2026-08-26) | — |
| D130 | SQL Dean Identifier Authority | Complete (verified 2026-08-26) | docs/evidence/D130/DEAN_D130_EXIT.md |
| D140 | Dean Excel Oracle | Complete (verified 2026-08-26; re-based onto PumpConfiguration_Logic_0.1.xlsm) | docs/evidence/D140/DEAN_D140_EXIT.md |
| D145 | Dean UI Selection-Hierarchy Rearrangement (presentation-only) | Complete (verified 2026-08-26; authoritative order + 10-group render, C/F for unbuilt, Fybroc untouched, PN unchanged) | docs/evidence/D145/DEAN_D145_UI_REARRANGE_EXIT.md |
| D155 | Dean Codependencies Certification | Complete (verified 2026-08-26; 256 non-seal codependencies enforced = 251 two-leg + 5 three-leg, matches PCL v0.1 Codependencies sheet; 519 seal tuples deferred per A1 crosswalk gap; fail-closed, no dead ends; FYBROC 4487 unchanged) | docs/evidence/D155/DEAN_D155_CODEPENDENCIES_EXIT.md |
| D150 | Dean Exhaustive Regression | NOT STARTED (prior "Complete" was over-reported) | — |
| D160 | Dean Signoff & Freeze | NOT STARTED (prior "Complete"/`d160-dean-complete` was over-reported) | — |

## Phase U — Unified Application

| Milestone | Title | Status | Git Tag |
|---|---|---|---|
| U100 | Canonical Product Model | Complete | — |
| U110 | Unified Configuration Dictionary | Complete | — |
| U120 | FastAPI V2 | Complete | — |
| U130 | Reusable BOM Engine | Complete | — |
| U140 | Quote Engine | Complete | — |
| U150 | Excel Runtime V2 | Complete | — |
| U160 | React Configurator | Complete | — |
| U170 | Security & Audit | Complete | `u170-unified-complete` |

## Phase T — Central Testing & UAT

| Milestone | Title | Status |
|---|---|---|
| T100 | CI/CD | Complete |
| T110 | Azure TEST Environment | Ready (infrastructure defined) |
| T120 | Telford UAT | Ready (awaiting deployment) |
| T130 | Indianapolis UAT | Ready (awaiting deployment) |
| T140 | Cross-Family UAT | Ready (awaiting deployment) |
| T150 | UAT Correction Cycle | Ready (awaiting UAT feedback) |

## Phase P — Production

| Milestone | Title | Status |
|---|---|---|
| P100 | Performance & Concurrency | Pending |
| P110 | Resilience & Recovery | Pending |
| P120 | Monitoring | Pending |
| P130 | Security Review | Pending |
| P140 | Production Infrastructure | Pending |
| P150 | Production Metadata Publication | Pending |
| P160 | Production Cutover | Pending |
| P170 | Training & Documentation | Pending |
| P180 | Stabilization | Pending |
| P190 | Project Closeout | Pending |

---

## Current Work Context

**Active work:** D155 complete — Dean Codependencies CERTIFIED. The PCL v0.1
`Codependencies` sheet (B1:BA171, 775 tuples) is enforced as Dean cross-constraint
dependencies: 256 non-seal tuples (251 two-leg + 5 three-leg) in
cfg.FeasibleConstraint, matching the authoritative workbook exactly; 519 seal
tuples deferred (A1 seal-vocab crosswalk gap, engineering-blocked, disclosed).
New re-runnable audit `scripts/audit_dean_codependencies.py` 13/0 (expectations
derived from re-parsing the workbook, not hardcoded); `scripts/audit_dean_config.py`
28/0 (fail-closed + quad-deferral + no-dead-end); Fybroc gate ALL CORRECTIONS
INTACT 9/9; FYBROC FeasibleConstraint 4487 unchanged. No data/schema/code change
(verify-only). Prior: D145 (UI rearrangement) complete.  
**Branch:** `feature/m021-shared-excel-production-hardening`  
**Next action:** D150 — Dean Exhaustive Regression — awaiting explicit go-ahead.
(D155 evidence: docs/evidence/D155/DEAN_D155_CODEPENDENCIES_EXIT.md. D145 evidence:
docs/evidence/D145/DEAN_D145_UI_REARRANGE_EXIT.md.)  

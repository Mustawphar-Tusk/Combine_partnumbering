# Milestone Register

**Last Updated:** 2026-08-26

> **Authority note:** for the true, verified Dean-phase status use
> `docs/Project_master_roadmap.md` §11–§12 (v1.18).
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

**Active work:** D120 complete — Dean Pricing Matrix published to SQL
(DEAN_STANDARD, 9874 rules), Dean pricing audit 22/22, Dean config audit 29/29,
Fybroc regression gate ALL CORRECTIONS INTACT (no regression). Pump Configuration
applicability gating added to the config model (Dean-only).  
**Branch:** `feature/m021-shared-excel-production-hardening`  
**Next action:** D150 (Exhaustive Dean Regression) — awaiting explicit go-ahead. (D140 Dean Excel Oracle complete 2026-08-26, re-based onto PumpConfiguration_Logic_0.1.xlsm; see docs/evidence/D140/DEAN_D140_EXIT.md.)  

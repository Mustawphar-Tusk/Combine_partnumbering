# D100 — Dean Conflict Register

**Date:** 2026-08-26
**Scope:** analysis/inventory only. Every conflict/ambiguity across the Dean
sources, with a proposed resolution or a NEEDS_ENGINEERING_REVIEW flag.
**Grounding:** prior M023.3 compile of `PumpConfiguration_Logic.xlsm`
(`exports/m023_dean_*`, `exports/dean_pumpconfiguration_logic.json`) plus this
session's re-extraction. The M023.3 dependency compile reports
`publication_gate: PASS`, `rule_semantics: "each Codependencies table compiled
as an undirected allowed-tuple constraint; no parent/child direction inferred"`
— consistent with the authority decision (PumpConfiguration_Logic = codependency
+ option-domain authority).

---

## A. BLOCKED constraint rules (5) — must resolve before D110 publication

The M023.3 compile produced 47 rules: **42 READY (542 tuples), 5 BLOCKED_REVIEW**.
All 5 blocked rules carry issue `DEPENDENCY_RULE_NO_READY_TUPLES` ("no tuples
safe for publication"), and every one of the 184 blocked tuples has review type
**`UNKNOWN_DEPENDENCY_OPTION`** — i.e. a Codependencies table uses a value that
is NOT in that field's Config Options domain. CONFIRMED root causes (from
`m023_dean_dependency_review.csv`):

| # | Rule | Fields | Blocked | CONFIRMED cause | Proposed action |
|---|------|--------|--------:|-----------------|-----------------|
| A1 | Table100 | Seal Option × Gland Type × Flush Plan × Barrier Plan | 165 | **Barrier Plan casing mismatch**: codependency uses `PLAN 7352`/`PLAN 52`/`PLAN 53`/… but Barrier Plan domain is `Plan 7352`/`Plan 52`/`Plan 53` (`PLAN` vs `Plan`). Also a 4-leg quad. | Normalize Barrier Plan casing (case-insensitive match, as Fybroc does) → all 165 resolve. D110 schema must also support a 4-leg tuple (Fybroc's is 3-leg). |
| A2 | Table113109 | Seal Configuration × Throttle Bushing | 1 | **Real data error**: tuple `Packing × Required`, but Throttle Bushing domain is `{Not Required, Carbon}` — "Required" is not a valid value. | NEEDS_ENGINEERING_REVIEW — is the intended value `Carbon` (or a new "Required")? |
| A3 | Table118 | Pumping Ring × Barrier Plan | 2 | Barrier Plan `Plan 52`/`Plan 53` — matches domain casing but the M023 run still flagged unknown (whitespace/normalization); resolves under case/space-insensitive match | Apply the same normalization as A1; re-validate |
| A4 | Table121 | Seal Configuration × Barrier Plan | 12 | Same `PLAN xxxx` vs `Plan xxxx` casing mismatch as A1 | Normalize casing → resolves |
| A5 | Table128 | Cooling Plan × Bearing Frame Cooling | 4 | **Value mismatch**: codependency uses `BEARING_FRAME_COOLING = NONE`, but domain is `{Not Required, Steel Tube, Aluminum Fan, Stainless Steel Fan}` — no `NONE`. | NEEDS_ENGINEERING_REVIEW — map `NONE` → `Not Required`? |

**Takeaway:** ~179 of 184 blocked tuples (A1, A3, A4) are **casing/normalization**
mismatches that resolve with the same case/space-insensitive matching already
used for Fybroc — they are NOT genuine engineering conflicts. Only **A2 (1 tuple:
Throttle Bushing "Required")** and **A5 (4 tuples: Bearing Frame Cooling "NONE")**
are true value-domain discrepancies needing an engineering decision.

Note the rule-code oddity **`Table113109`** (looks like `Table113`+`Table109`
concatenated) — a source-workbook Excel table-naming artifact to verify.

## B. Config Options domain issues

| # | Item | Detail | Action |
|---|------|--------|--------|
| B1 | Barrier Plan Extras empty | `Config Options` Table76 (col DE) has 0 data rows | Confirm the field is intentionally empty / deprecated, else supply domain |
| B2 | "Pump Configuration" option 9 is an instruction | Value = *"Add additional flush and barrier plan questions from Attribute list. Will no longer selected 2 character code."* | Remove from option domain; it is a design note, not a selectable value |
| B3 | OLD JC Style column | 26 legacy John Crane names parallel to Seal Type (col BO) | Treat as cross-reference/deprecated, not a configurable field |
| B4 | "Custom" terminal option | Appears on many fields (Pump Material, Flange, Casing Wear Ring, etc.) | Decide runtime handling: free-text escape vs blocked-for-quote |

## C. Cross-workbook model-reference conflicts (PumpConfiguration_Logic vs Data Sheet Rev 2)

From `m023_dean_reconciliation_issues.csv`:

| # | Issue | Detail | Action |
|---|-------|--------|--------|
| C1 | LOGIC_MODEL_NOT_IN_REV2_REFERENCE | `DEANLINE\|0.75X0.75` present in PumpConfiguration_Logic but NOT in the authoritative Rev2 model reference | Confirm whether 0.75x0.75 Deanline is a real model; reconcile which workbook is authoritative for the model list |
| C2 | LOGIC_MODEL_NOT_IN_REV2_REFERENCE | `DEANLINE\|1.5X1.5` present in PumpConfiguration_Logic but NOT in Rev2 | Same as C1 |
| C3 | LOGIC_MODEL_IDENTIFIER_NON_A_PREFIX | `MDL1-.75` (Pump Options!A208) does not match the A-number prefix scheme | Confirm A-number model identity convention (D130 A→D rule) |
| C4 | LOGIC_MODEL_IDENTIFIER_NON_A_PREFIX | `MDL1-1.5` (Pump Options!A209) non-A prefix | Same as C3 |

**Authority note:** per engineering direction, PumpConfiguration_Logic is
authoritative for **codependencies + option domains**. C1-C4 concern the **model
(Series×Size) list**, which per DEAN_CONSTRAINT_RECONCILIATION is owned by the
Data Sheet Rev 2 `Constraints` sheet — so these are model-list reconciliation
items, NOT codependency conflicts.

## D. Extra / candidate workbook

| # | Item | Detail | Action |
|---|------|--------|--------|
| D1 | `DeanMasterConfig_v14 - RA - JASON.xlsm` (5.6 MB) | Present in `workbooks/Dean/` but NOT in the roadmap's four-workbook Dean source set, and NOT referenced by `config/workbook_roles.json` | NEEDS_ENGINEERING_REVIEW — is v14 a newer master that supersedes any of the four, or a personal working copy? Governance: newer filename does NOT auto-supersede. Classify before D110. |

## E. Not-yet-loaded state (informational, not a conflict)

- SQL currently has **no Dean rows** (`cfg.MotorConstraint` 0, `cfg.AttributeValue`
  0 for DEAN; `cfg.SeriesFieldOption` holds only Fybroc series). Dean constraints
  are extracted + compiled to `exports/` but not published to SQL — that is
  D110's job, not a D100 conflict.
- DEAN is `cfg.PumpFamily` id=1 (FYBROC=2).

## Summary

- **5 blocked constraint rules (A1-A5)** are the must-resolve engineering items
  before Dean constraints can publish; A2-A5 look like value spelling/normalization
  or domain mismatches, A1 is the 4-leg quad needing schema + confirmation.
- **B, C, D** are review/classification items that do not block the constraint
  authority but must be settled during D110/D130.
- No conflict contradicts the authority decision: PumpConfiguration_Logic remains
  the complete codependency + option-domain source.

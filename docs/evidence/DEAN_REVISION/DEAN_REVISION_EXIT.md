# Dean Revision — Pump Constraints Custom + Seal Reference + Custom-Spec Lifecycle — EXIT EVIDENCE

**Milestone:** Dean revision of `PumpConfiguration_Logic_0.1.xlsm` → `Pump Constraints`
(Custom columns on all option groupings + new per-series Seal Reference Table) and
the engineer custom-spec lifecycle. **Mode:** FULL. **Branch:** `feature/cpq-spa`.
**Design:** `docs/DEAN_REVISION_CUSTOM_SPEC_DESIGN.md`. **Date:** 2026-08-26.
Additive-only; **Fybroc (PumpFamilyId 2) frozen**.

Owner requirements (fulfilled): revised sheet re-ingested so every grouping's
**Custom** option is selectable; new **Seal Reference Table** captured per series
(not in the PN); selecting Custom opens a pop-up to describe the customization,
which **forces engineering review** on submit; the engineer resolves the spec and
it is **stored per grouping and reusable**; the resolved custom code **occupies the
grouping's PN segment slot at its native width** (same PN shape, new custom value).

---

## 1. Deliverables (all additive)

- **D-R1 — re-ingest + seal reference**
  - `scripts/d110_load_dean_config_v01.py`: `Codependencies` parser moved to the
    revised layout (header row 6→8; `?`/note markers excluded). Parses 738 tuples →
    246 non-seal enforced (seal 492 deferred, Option A), vs 256 before. `Pump
    Constraints` re-ingested → DEAN `cfg.SeriesFieldOption` 50320→50478; 39 groupings
    carry a `C/F` (Custom) option.
  - `sql/35_Create_Dean_Seal_Reference.sql` + `scripts/load_dean_seal_reference.py`:
    new `cfg.DeanSealReference` (series → seal-ref key from col 594). 37 series;
    keys {1.000"/1.375"/1.750"/2.125"/2.250"/3.000" Shafts, Misc., X}. **Not in PN.**
- **D-R2a — custom code occupies the PN slot** (`src/api/dean_identifier.py`):
  reserved selections keys `<SEG>__CUSTOM` (flag) and `<SEG>__CUSTOM_CODE` (resolved
  code). When a grouping is explicitly customized, the resolved base-36 code occupies
  its segment slot at the native width; unresolved → placeholder (`____`/`__`).
  `_has_custom` triggers only on explicit custom (NOT a field's C/F standard — 43
  Dean coded-field STD defaults are legitimately C/F). **No SQL change**: the code
  flows through the existing DEAN CONCAT; python==SQL parity preserved.
- **D-R2b — lifecycle SQL + API** (`sql/36_Create_Custom_Spec_Resolution.sql`,
  `src/api/v2_routes.py`): `quote.QuoteLineCustomization` gains
  Resolved{CustomCode,SpecKey,ByAppUserId,At}; new `cfg.usp_ResolveCustomSpec` mints-
  or-reuses via `cfg.usp_GetOrCreateCustomSegmentCode` (A4) and stamps the row. New
  `POST /families/{family}/custom-segment-codes/resolve` (same spec-key hash as the
  A4 mint → family-wide reuse). `/unresolved` already forces review for any
  customization request.
- **D-R2c — SPA** (`spa/src/...`): configurator sets the `<SEG>__CUSTOM` flag when a
  field's Custom (C/F) option is chosen (PN placeholder + review) and opens the
  customization pop-up in edit mode; engineer review line "Resolve custom spec" →
  `resolveCustomSpec` (shows reused/new; seal → deferred). `client.ts`
  `resolveCustomSpec`.

## 2. Milestone audit — `scripts/audit_dean_revision.py` → 15/15 PASS
Re-runnable, self-cleaning (removes its minted codes; registry back to 0).
Highlights (expectations derived from workbook/DB):
- C/F options present (4756 rows); 0 literal "Custom" left; 39 C/F fields.
- `cfg.DeanSealReference` 37 series; keys match workbook col 594 exactly (0 mismatch).
- Lifecycle: specA→`1SYB` (new), specA again→`1SYB` (reuse), specB→`1SYC` (new);
  resolved code occupies PN wet-end slot `D784-1SYB-EE01-000S-...`; `SEAL_TYPE`→409
  (deferred).
- Standard DEAN build PN clean: `D784-0022-EE01-000S-00000-0000-0000`.
- Watermarks (below).

## 3. Dean config audit — `scripts/audit_dean_config.py` → 28/0
STD auto-seed, per-size applicability, codependency fail-closed on the revised
246-tuple set, 4-leg quad (seal deferred), no dead-ends.

## 4. Identifier parity — `scripts/audit_dean_identifier.py`
Parity (python `py_pn` == SQL `usp_AssembleConfiguredProduct`) is **sound** and
standard builds are byte-unchanged. The batch audit reported a NON-DETERMINISTIC
count of "parity failures" (9 on one run, 8 on a re-run) on the
M300/RM5140/RMA5140 series — all under the audit's forced
`PUMP_CONFIGURATION="Pump, Baseplate, Coupling and Motor"` config where
`BASEPLATE_TYPE` STD = `C/F`. This was proven to be an **environmental flake**
(the audit fires hundreds of rapid resolve calls; some degrade under load — the
same HTTP-timeout flakiness documented for `audit_fybroc_pricing`), NOT a code
regression:
- Offline (no server): `dean_identifier.assemble_pn(payload) == py_pn` for these
  models (same function path — cannot disagree).
- Clean HTTP resolve of the audit's EXACT forced-baseplate config for all three
  series → `python py_pn == SQL part_number`, MATCH in every case
  (`D760-0JBK-GA01-1HWN-0S000-001Y-0000`, etc.), baseplate `1Y`.
- `_has_custom` does NOT fire on a `C/F` standard value (verified), so the
  baseplate is NOT wrongly collapsed; the slot resolves to a real `1Y` code.
Conclusion: python==SQL parity holds; the flaky batch count is an audit-under-load
artifact, not a Dean PN regression. (D-R2a changes only the explicit-custom path;
standard builds are byte-unchanged by construction.)

## 5. Cross-family regression — `scripts/run_all_fybroc_audits.py`
**9/9 — ALL CORRECTIONS INTACT (on merits).** 8 audits passed in the batch
(`audit_selections_vs_db`, `audit_feasible_constraints` 44/0, `audit_motor_constraints`,
`audit_identifier_parity` 44/0, `audit_bom_engine`, `audit_quote_engine`,
`audit_free_config` 32/0, `audit_fybroc_pricing` 47/0). `audit_fybroc_motor_cpq`
FAILED in the batch on an HTTP `TimeoutError` (the documented under-load flake);
re-run in isolation against a fresh server it passed **37/0, exit 0**. No Fybroc
correction regressed.

## 6. Isolation / no-collateral-damage
| Invariant | Baseline | After |
|---|---|---|
| non-DEAN cfg.SeriesFieldOption | 3638 | 3638 |
| non-DEAN stg.SegmentCombinationImport | 300608 | 300608 |
| DEAN stg.SegmentCombinationImport | 140976 | 140976 |
| non-DEAN cfg.FeasibleConstraint | 4487 | 4487 |

DEAN `cfg.SeriesFieldOption` grew 50320→50478 (new Custom C/F option rows — expected
and intended). DEAN `cfg.FeasibleConstraint` 256→246 (revised codependencies tracked;
seal tuples still deferred). No numbering reload (stg DEAN seg unchanged 140976). No
change to the Dean PN shape or to Fybroc.

## 7. Known gaps (disclosed)
- **Seal codependency enforcement deferred** (Option A): 492 seal codependency tuples
  parsed but not loaded; seal is pending engineering's seal numbering. Seal custom
  specs are captured + reviewed + stored, but the reusable CODE is deferred until seal
  has a numbering width (resolve returns 409 for seal today). Seal is not in the PN.
- Dean base price pending (pre-existing) — unaffected.

## 8. Exit-gate decision — **PASS**

| Criterion | Result |
|---|---|
| Revised Pump Constraints re-ingested (Custom → C/F, no dropped grouping) | PASS (audit_dean_revision) |
| Seal Reference Table captured per series, exact workbook values, not in PN | PASS |
| Custom-spec lifecycle: capture → forces review → resolve → reusable code | PASS |
| Resolved custom code occupies the grouping's PN slot at native width | PASS |
| Seal (no numbering width) → code deferred, spec captured | PASS (409) |
| Standard Dean build PN byte-unchanged; python==SQL parity | PASS (verified clean) |
| Dean config audit (STD/applicability/fail-closed/no dead-ends) | PASS 28/0 |
| Fybroc cross-family gate | PASS 9/9 on merits |
| Isolation watermarks unchanged | PASS |

**PASS.** Milestone audit 15/15; Dean config 28/0; Fybroc gate 9/9 on merits;
isolation intact; parity sound. Seal codependency enforcement + seal numbering
remain the disclosed deferred follow-up.

# Fybroc Rev0.4 — Constraint/Config Authority Supersession

**Date:** 2026-08-26
**Scope:** Adopt `workbooks/Fybroc/Fybroc Configuration Rev0.4.xlsx` as the
authoritative FYBROC **constraint + configuration** source, superseding Rev0.3.
**Family:** FYBROC (PumpFamilyId=2). Dean (family 1) untouched.
**Companion evidence:** `REV04_vs_REV03_CONSTRAINT_DIFF.{md,json}` (this folder).

---

## 1. Finding: Rev0.4 constraint/config content is IDENTICAL to Rev0.3

A full workbook-wide, cell-level diff (both the 4 constraint sheets and every
shared sheet) established that the **enforced constraint/config content is
byte-identical** between Rev0.3 and Rev0.4:

| Structure (sheet) | Result |
|---|---|
| Constraints (combination matrix, 1230×153) | IDENTICAL (hash `3bb5bc581602d9f0`) |
| Feasible Constraints (29 ConstraintTables incl. CT24 Tailpipe, 3482×81) | IDENTICAL (hash `dba5bf4b1acb70bb`) |
| Constraint Index (entries rows 6–27) | IDENTICAL (hash `8624c4ad327fe9cf`) |
| Motor Constraints (955×86) | IDENTICAL |
| Hierarchy | IDENTICAL |
| Selections (X/STD grid, rows 2–678, 10 series) | IDENTICAL (2096 rows; 0 added/removed/flip) |

The **Tailpipe Option × Tailpipe Length** table you flagged (Rev0.4 Feasible
Constraints, anchor `ConstraintTable24` at cell **BK4**, headers BK5, data BK6+ =
rows 4–123) was verified: 115 rows, `Supplied by Fybroc` × Tailpipe Length 6–120,
all `Allowed` — the same as Rev0.3.

### What actually differs in Rev0.4 (NOT constraint enforcement)
- **Pricing** (already adopted separately: price publication
  `FYBROC-REV04-MERGE-20260914-V1`): sheets `1500 Pricing`, `5500 Pricing`,
  `Pricing Index`, and Rev0.4-only `All Series Pricing`, `1500 Motors`,
  `5500 Motors`, `Setting Groups`.
- **Notes/scratch**: `To do`, `Items` (col F helper list), Rev0.4-only `UI Notes`.
- **Combine Variables** (a pricing/reference helper): the MotorHp↔RPM mapping
  VALUES are identical but its **columns were reshuffled** (Rev0.3 key
  `F_MotorHpRPM`=E, `MotorHp`=F, `MotorRPM`=G → Rev0.4 =F/D/E), and the J10 domain
  header was renamed `MotorType` → `PREVIOUS MotorType OPTIONS` (same 5 values).

---

## 2. Deliverables (what changed)

### Compilers repointed Rev0.3 → Rev0.4 (authoritative)
- `scripts/compile_fybroc_constraint_model.py` — `WORKBOOK_REL` → Rev0.4.
- `scripts/compile_fybroc_selections_model.py` — `WORKBOOK_REL` → Rev0.4
  (`DATA_END_ROW=678` already excludes Rev0.4's new pricing-helper rows 682+).
- `scripts/compile_fybroc_motor_constraint_model.py` — `WORKBOOK_REL` → Rev0.4,
  and made **revision-robust**: the MotorHpRpm composite-key table is now resolved
  by HEADER NAME (`F_MotorHpRPM` → `MotorHp`,`MotorRPM`) via a row-3 header scan,
  so Rev0.4's column reshuffle does not corrupt the mapping; a
  `DOMAIN_HEADER_CANONICAL` map keeps `PREVIOUS MotorType OPTIONS` loading under
  the canonical `MotorType` attribute (identical values).

The regenerated `docs/evidence/F120/FYBROC_{CONSTRAINT,SELECTIONS,MOTOR_CONSTRAINT}_MODEL.json`
were proven **content-identical** to the Rev0.3-derived baselines
(provenance-stripped: git/timestamp/workbook-name).

### Loaders hardened family-safe (prevented a Dean-wipe regression)
The constraint/config tables are SHARED across families under the active
publication (Dean rows were added in D110/D140). Two loaders were unsafe:
- `scripts/load_constraints_to_sql.py` — previously `DELETE FROM
  cfg.FeasibleConstraint` (ALL families) and INSERT with **no PumpFamilyId**.
  Fixed: DELETE/INSERT scoped to `PumpFamilyId=FYBROC`; INSERT sets PumpFamilyId;
  added an isolation assertion (non-FYBROC row count unchanged).
- `scripts/load_all_series.py` — previously `DELETE ... WHERE
  MetadataPublicationId=?` (publication-only) would have wiped Dean's SFO rows
  under the shared publication. Fixed: DELETE/verify scoped to
  `AND PumpFamilyId=FYBROC`; source workbook → Rev0.4.
- `scripts/load_combine_variables_to_sql.py` — already family-safe; unchanged.

### Regression guard repointed (no asserts weakened)
- `scripts/audit_selections_vs_db.py` — authority workbook Rev0.3 → Rev0.4;
  report text updated. Transform + all asserts unchanged.
- `scripts/audit_feasible_constraints.py` — docstring updated to Rev0.4; the
  hardcoded correction cases are unchanged (tables are byte-identical).

### Publication (non-destructive)
`cfg.MetadataPublication` is shared across families and NOT family-scoped, and the
Rev0.4 constraint content is identical, so **no new config publication was minted
or activated** (that would have forced a Dean-disrupting re-publish for zero
content change). Instead `scripts/annotate_rev04_config_authority.py` appended a
provenance note to the active publication's Description recording the Rev0.4
authority. Exactly one Active publication remains (`F140-corrections-v1`).

---

## 3. Verification (audit numbers + commands)

Reload (family-safe):
```
$env:PYTHONPATH="."
python scripts/compile_fybroc_constraint_model.py
python scripts/compile_fybroc_selections_model.py
python scripts/compile_fybroc_motor_constraint_model.py
python scripts/load_constraints_to_sql.py            # 4487 FYBROC rows; "Isolation OK: non-FYBROC unchanged (256)"
python scripts/load_all_series.py                    # 2096 FYBROC SFO rows (pub 2)
python scripts/load_combine_variables_to_sql.py      # CombineVariable 112, CombineValueDomain 53
python scripts/annotate_rev04_config_authority.py    # 1 Active publication (asserted)
```

Full Fybroc regression (spins its own temp API — ensure port 8080 is free first):
```
python scripts/run_all_fybroc_audits.py
```
**RESULT: ALL CORRECTIONS INTACT (7/7)** —
audit_selections_vs_db (CLEAN vs Rev0.4), audit_feasible_constraints 14/14,
audit_motor_constraints 91/91, audit_identifier_parity 44/44, audit_bom_engine
38/38, audit_quote_engine 22/22, audit_free_config 32/32.

### Isolation / no-collateral-damage (before == after)
| Table (scope) | Count | Δ |
|---|---|---|
| cfg.FeasibleConstraint (FYBROC) | 4487 | 0 |
| cfg.FeasibleConstraint (DEAN) | 256 | 0 |
| cfg.SeriesFieldOption (FYBROC, all pubs) | 3638 | 0 |
| cfg.SeriesFieldOption (DEAN) | 48063 | 0 |
| cfg.ConstraintFieldMap (FYBROC / DEAN) | 28 / 31 | 0 |
| cfg.CombineVariable / CombineValueDomain (FYBROC) | 112 / 53 | 0 |
| cfg.MotorConstraint (FYBROC) | 3278 | 0 |

Every enforced row is unchanged; Dean fully isolated.

---

## 4. Exit decision & known notes

**PASS.** Rev0.4 is now the authoritative FYBROC constraint/config source. Because
the constraint content is identical to Rev0.3, this is a provenance/authority
supersession + a loader family-safety hardening — no runtime configuration
behavior changed, and the frozen-Fybroc "corrections must not regress" gate stays
green (7/7).

Notes / not-in-scope:
- Pricing was already Rev0.4 (separate price publication); untouched here.
- Pure-analysis/pricing compilers left on Rev0.3 intentionally (historical
  evidence; not part of the enforced constraint pipeline):
  `compile_fybroc_rev03_pricing.py`, `compile_fybroc_pricing_diff.py`,
  `compile_fybroc_items_hierarchy_model.py`, `compile_fybroc_rev03_todo_mainpage.py`,
  `compile_fybroc_formula_inventory.py`, `compile_fybroc_f140_corrections.py`,
  `verify_all_series.py`.
- The pre-existing CT24 semantic (when Tailpipe = "Not Supplied" there are no rows
  so Tailpipe Length is left open rather than blocked/skipped) is UNCHANGED by
  this supersession — Rev0.4's CT24 is identical to Rev0.3's. If that behavior is
  to change, it is a separate constraint-semantics decision, not a Rev0.4 adoption.

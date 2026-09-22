# D110 — Dean Configuration & Dependency Completion: Exit Summary

**Date:** 2026-08-26
**Milestone:** D110 — Dean Configuration & Dependency Completion
**Status:** COMPLETE — the authoritative `PumpConfiguration_Logic.xlsm` model
(option domains + codependency allow-tuples) is published to SQL for the DEAN
family and enforced by the live constraint engine, with the Fybroc regression
gate still green (zero regression).
**Constraint:** family-scoped to DEAN (`PumpFamilyId=1`); **no frozen Fybroc data
was altered** (verified by row-count parity and the full Fybroc gate).

---

## 1. What was published

Authoritative source: `exports/m023_dean_source_reconciliation.json` (compiled
M023.3) + `exports/dean_pumpconfiguration_logic.json`. Loaded by the idempotent,
family-scoped loader `scripts/d110_load_dean_config.py`.

| SQL table | DEAN rows | Detail |
|-----------|----------:|--------|
| `cfg.ConstraintFieldMap` | 46 | Dean constraint label → SFO field code (family 1) |
| `cfg.SeriesFieldOption` | 19,425 | 70 option domains × 37 model-series (19,240) **+ 185 synthesized `BARRIER_PLAN`** (5 values × 37 series) |
| `cfg.FeasibleConstraint` | 721 | 47 codependency allow-tuple tables (726 rows − 5 blocked); includes the 4-leg quad |

37 Dean model-series (CNV206, DEANLINE, DL200/230, PH21xx/PHP21xx, R4/R5xxx,
RA/RAV/RM/RMA/RS/RSWA/RT/RWA/RWAV series, M300).

## 2. Infrastructure reuse (family-scoping)

Rather than build parallel Dean tables, the shared Fybroc constraint tables were
made family-aware (chosen as "Option 1" with the user):

- **`PumpFamilyId` added** to `cfg.FeasibleConstraint` and `cfg.ConstraintFieldMap`
  (migration `scripts/d110_add_family_scoping.py`). Existing rows backfilled to
  FYBROC (family 2). DEAN is family 1.
- **`ConstraintFieldMap` PK** widened to composite `(ConstraintFieldName,
  PumpFamilyId)` (`scripts/d110_fix_cfm_pk.py`) so a shared label (e.g.
  *Seal Type*, *Seal Option*, *Shaft Material*) can exist per family without
  cross-contaminating enforcement.
- **`Option4Field` / `Option4Value`** added to `cfg.FeasibleConstraint`
  (`scripts/d110_add_option4.py`, nullable) to carry the one Dean **4-leg quad**
  (*Seal Option × Gland Type × Flush Plan × Barrier Plan*, Table100). Fybroc's
  shape was 3-leg; existing Fybroc rows keep NULL Option4.
- **API** (`src/api/v2_routes.py`, `_load_constraint_context`): both constraint
  reads now filter `WHERE PumpFamilyId = ?`, and the feasible-constraint query +
  parse loop read the Option4 leg. The single authoritative `_apply_constraints`
  filter handles 2-, 3-, and 4-leg rows uniformly.

## 3. Data-shape fixes applied at load

- **Barrier Plan casing** normalized loader-side (`PLAN 52` → `Plan 52` for
  `BARRIER_PLAN`/`FLUSH_PLAN`), resolving the ~179 casing/whitespace tuples that
  D100 flagged (no workbook edit).
- **`BARRIER_PLAN` option domain synthesized.** The Config Options sheet has only
  an empty *Barrier Plan Extras* table — no standalone Barrier Plan domain — yet
  the codependency quad references *Barrier Plan* as a leg. Without a domain the
  field projected zero options and its quad leg was dead. The loader now
  synthesizes the domain for any constraint-leg field code lacking an option
  domain (except the `SERIES` selector) from the distinct constraint values:
  `BARRIER_PLAN` = {Plan 52, Plan 53, Plan 62, Plan 7352, Plan 7353}. This gap
  was caught by the Dean audit (see §4) and is a real correctness fix, not a
  workaround. It also closes the D100 open item "Barrier Plan Extras empty domain".

## 4. Verification

### Dean configuration audit — `scripts/audit_dean_config.py` (45/45 PASS)

Test cases are derived from the published DB rows (not hardcoded), so the audit
tracks the data. It verifies the four D110 exit criteria:

1. **Options project** — 8 sampled series (horizontal, vertical, close-coupled,
   canned, DEANLINE), 70 applicable fields each, **0 empty** option lists.
2. **Valid combos pass (no over-blocking)** — for every prunable 2-leg table, an
   authoritative-allowed partner survives given its context.
3. **Invalid combos fail closed** — across all 6 prunable 2-leg tables (incl.
   *Seal Configuration → Barrier Plan*), **0 disallowed values leaked**.
4. **4-leg quad wired** — selecting Seal Option/Gland Type/Flush Plan projects
   all 5 authoritative Barrier Plan values through the Option4 columns.
5. **No empty-option dead ends** — full-config walks on 3 series never drive a
   field to zero options; final walked config is `valid=True`.

> Note on Dean data shape: of the 42 two-leg ALLOW tables, only 6 actually
> *prune* — the rest (and the quad, as authored) are full-domain enumerations
> that impose no restriction by design. The audit tests fail-closed on every
> table that *can* prune and projection/no-empty on the rest, rather than
> asserting an arbitrary count.

### Fybroc regression gate — `scripts/run_all_fybroc_audits.py` (7/7 — ALL CORRECTIONS INTACT)

Re-run after the Dean load + BARRIER_PLAN reload:

| Audit | Result |
|-------|--------|
| `audit_selections_vs_db` | CLEAN 2096/2096 (family-scoped) |
| `audit_feasible_constraints` | 14/14 |
| `audit_motor_constraints` | 91/91 |
| `audit_identifier_parity` | 44/44 |
| `audit_bom_engine` | 38/38 |
| `audit_quote_engine` | 22/22 |
| `audit_free_config` | 32/32 |

The family-agnostic `audit_selections_vs_db` was scoped to FYBROC (`WHERE
PumpFamilyId = <FYBROC>`) so it no longer counts the new Dean rows as spurious
"EXTRA" — the only audit change required.

**Fybroc row parity (before == after):** `FeasibleConstraint` 4487,
`ConstraintFieldMap` 28, `SeriesFieldOption` 3638 — unchanged.

## 5. Blocked tuples — the only gap (PENDING ENGINEERING)

5 value-domain tuples remain **excluded and logged** by the loader, awaiting an
engineering decision. These are the same items D100 root-caused; they do not
block the D110 exit gate (the model is complete and enforced without them).

| Table | Constraint | Blocked value | Count | Workbook cell | Expected resolution |
|-------|-----------|---------------|------:|---------------|---------------------|
| Table113109 | Seal Configuration × Throttle Bushing | Throttle Bushing = `Required` | 1 | `Codependencies!AO124` | Domain is {Not Required, Carbon}; user verifying with engineering |
| Table128 | Cooling Plan × Bearing Frame Cooling | Bearing Frame Cooling = `NONE` (Cooling Plan C/D/E/J) | 4 | `Codependencies!AU99:AU102` | Likely `Not Required` |

When engineering confirms the correct values, remove the entries from
`BLOCKED_VALUES` in `scripts/d110_load_dean_config.py` (or add a load-time alias)
and re-run the loader + both gates.

## 6. Exit gate

> Dean valid options project correctly per series; invalid combinations fail
> closed; dependency transitions work; no unexplained empty-option state.

**MET.** `audit_dean_config.py` 45/45 proves projection, pass-through,
fail-closed, quad enforcement, and no dead ends. The Fybroc gate remains ALL
CORRECTIONS INTACT (7/7), so the shared-table family-scoping introduced no
regression. The only remaining gap is the 5 pending-engineering value tuples,
which are explicitly logged.

## 7. Deliverables / artifacts

- Loader: `scripts/d110_load_dean_config.py` (idempotent, family-scoped, blocked
  logging, casing normalization, BARRIER_PLAN synthesis).
- Migrations: `scripts/d110_add_family_scoping.py`, `scripts/d110_add_option4.py`,
  `scripts/d110_fix_cfm_pk.py`.
- Dean audit: `scripts/audit_dean_config.py`.
- API: `src/api/v2_routes.py` (family-scoped + Option4 constraint reads).
- Fybroc gate fix: `scripts/audit_selections_vs_db.py` (FYBROC scope).
- Model reference (from planning): `DEAN_CONFIGURATION_MODEL.md` (same dir).

**Next permitted milestone:** D120 — Dean Pricing & Adders. **Do not start D120
without explicit go-ahead.**

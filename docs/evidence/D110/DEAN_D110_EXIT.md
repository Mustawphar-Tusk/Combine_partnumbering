# D110 — Dean Configuration & Dependency Completion: Exit Summary

> **2026-08-26 RE-BASE (D140):** the authoritative source is now
> `workbooks/Dean/PumpConfiguration_Logic_0.1.xlsm` (PCL v0.1), which
> **supersedes** the `PumpConfiguration_Logic.xlsm` referenced below for ALL
> constraints/config. The Dean config model was re-loaded from v0.1 via
> `scripts/d110_load_dean_config_v01.py` (Pump Constraints STD/X per-model matrix
> + row-aligned Codependencies allow-tuples). Current published state:
> SeriesFieldOption **48,063** (per-model), FeasibleConstraint **256** enforced
> (251 2-leg + 5 3-leg; **519 seal-vocab codependency tuples SKIPPED**, pending
> engineering A1). `audit_dean_config` **28/28**. See
> `docs/evidence/D140/DEAN_D140_EXIT.md`. The numbers below reflect the original
> D110 pass on the old workbook and are retained for history.

**Date:** 2026-08-26
**Milestone:** D110 — Dean Configuration & Dependency Completion
**Status:** COMPLETE — the authoritative `PumpConfiguration_Logic.xlsm` model
(option domains + codependency allow-tuples) is published to SQL for the DEAN
family and enforced by the live constraint engine, with the Fybroc regression
gate still green (zero regression).
**Constraint:** family-scoped to DEAN (`PumpFamilyId=1`); **no frozen Fybroc data
was altered** (verified by row-count parity and the full Fybroc gate).

---

## 0. Correction (2026-08-26): size-aware, STD/X-driven option applicability

> **This supersedes the original SeriesFieldOption load described in §1 below.**
> The first pass loaded option **values** from the `Config Options` sheet and
> marked every option `IsStandard=0`, offered to every series. Engineering
> flagged that most Dean configurations carry **STD** (standard) and **X**
> (available) markers. Those markers live on the **`Pump Options`** sheet of
> `PumpConfiguration_Logic.xlsm` (and the `Dean Data Sheet Rev 2` `Constraints`
> sheet), which the first pass did not read. The load was rebuilt.

**What changed**

- **Authoritative option source is now `PumpConfiguration_Logic.xlsm → Pump
  Options`** (the Dean analogue of Fybroc's Selections sheet): one row per
  **model** = (A-Number + Series + Size), each option column marked STD /
  X / blank. 206 models, 69 fields, 527 option columns.
- **Applicability is per-model (series + size), not per-series.** STD/X varies by
  size in **27 of 37 series** (e.g. PH2140 has 7 distinct size signatures across
  17 sizes). A series-only key cannot represent this.
- **Schema:** added a nullable `SizeCode` to `cfg.SeriesFieldOption`
  (`scripts/d110_add_sizecode.py`). Fybroc rows keep `SizeCode = NULL` (a
  series-level row that applies to every size — Fybroc's existing semantics). The
  active-uniqueness index `UX_SeriesFieldOption_ActiveRelation` was widened to
  include `SizeCode` so per-size Dean rows don't collide (Fybroc's NULL keeps its
  existing 5-tuple uniqueness). A supporting index
  `IX_SeriesFieldOption_SizeScope` was added.
- **Loader** (`scripts/d110_load_dean_config.py`): per (model, field), an option
  cell marked STD → `IsStandard=1`, `SelectionMarker='STD'`; X → `IsStandard=0`,
  `SelectionMarker='X'`; blank → not loaded (not offered for that model).
  `SizeCode` = the model size.
- **API** (`src/api/v2_routes.py`): the option-projection reads (evaluate,
  resolve-state, validate) now scope by `(SizeCode IS NULL OR SizeCode = @size)`
  where `@size` is the selected `ALT_SIZE`/`SIZE`. Before a size is chosen, the
  series union is shown (values de-duplicated); once a size is picked, options
  narrow to that model. Fybroc rows are `SizeCode NULL` so they always project —
  **Fybroc behavior is byte-for-byte unchanged** (proven by the gate).
- **STD auto-seed now works for Dean** (it previously could not — there were no
  STD defaults). Selecting a model seeds each field's standard value, matching
  the Fybroc free-edit UX.

**Two authoritative data fixes this surfaced**

1. **SEAL_TYPE vocabulary.** `Config Options` used long descriptive seal names
   ("SIU - Non-Pusher Elastomer Bellows Seal"), but the **codependency tables and
   `Pump Options` both use the short `Type N` form** ("Type 1", "Type 6A", …). The
   first load's long names did not match the constraint legs, so the 145-row
   SEAL_TYPE codependency could not prune. Sourcing values from `Pump Options`
   aligns them: **25/25 loaded SEAL_TYPE options now match the constraint
   vocabulary.**
2. **BARRIER_PLAN domain.** `Pump Options` carries the real 10-value Barrier Plan
   domain (NONE, Plan 52/53/62/65/74/7352/7353, SK1861, Custom), richer than the
   5 values previously synthesized from the quad. BARRIER_PLAN has no per-model
   STD/X markers (availability is governed by the 4-leg quad), so it is loaded
   per-series with `SizeCode NULL`.

**Rebuilt load result**

| SQL table | DEAN rows | Detail |
|-----------|----------:|--------|
| `cfg.ConstraintFieldMap` | 46 | unchanged |
| `cfg.SeriesFieldOption` | 48,910 | 48,540 per-model (STD/X) across 206 models / 37 series + 370 ungated BARRIER_PLAN |
| — of which STD defaults | 11,767 | matches the workbook STD count exactly |
| `cfg.FeasibleConstraint` | 721 | unchanged (726 − 5 blocked) |

**Verification**

- **Dean audit** `scripts/audit_dean_config.py` — **29/29** (expectations derived
  from the DB): STD auto-seed per model; per-size applicability (API options ⊆ DB
  offered, 0 non-offered leaked) + size differentiation across sizes of varying
  series; codependency fail-closed (0 disallowed leaked, 6 prunable tables);
  4-leg quad wired via Option4; no empty-option dead ends.
- **Fybroc regression gate** — **ALL CORRECTIONS INTACT (7/7)**; Fybroc row counts
  unchanged (`FeasibleConstraint` 4487, `ConstraintFieldMap` 28,
  `SeriesFieldOption` 3638, **0 Fybroc rows with a non-NULL SizeCode**).

**New data-quality observation (non-blocking, pending engineering):** 10
codependency rows reference a SEAL_TYPE value that has no matching option because
the M023 codependency source mixes the long and short seal vocabularies —
`SIB - Pusher O-Ring Seal` (×1), `… (thin cross section)` (×1), `… - High
Pressure` (×1), `SIB - Pusher Wedge Seal` (×1), and `Type 2` (×6). These legs are
**inert** (they can never match a selectable option), so they are harmless, but
the seal vocabulary should be reconciled in the source with the other pending
items.

---

## 1. What was published (original first-pass description — see §0 for the
##    corrected, authoritative load)

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

# Milestone Exit Audit — mandatory before every milestone exit

**Status:** always-on process rule. Applies to every milestone (F/D/U/T/P phases).
**Authority:** operationalizes `docs/PROJECT_MASTER_ROADMAP.md` §"Each milestone
ends with…" and the "CORRECTIONS ARE PERMANENT AND MUST NOT REGRESS" rule.

## Rule

A milestone is **not complete** — and the next milestone must **not start** —
until a full exit audit has passed and been recorded. No exceptions without an
explicit user override. When the user asks to "move on" / "start the next
milestone" and this audit has not passed, run it first (or state clearly that it
has not been run and why).

## The exit audit (run every item, in order)

1. **Deliverables inventory.** List what this milestone changed: schema
   migrations, loaders, API/code edits, config/data published, docs. Re-read the
   milestone's exit-gate criteria from the roadmap and restate them as concrete,
   checkable success conditions (exact counts, values, files, behaviors).

2. **Milestone-specific audit.** Run (or write, if it does not exist) a
   re-runnable audit script that verifies THIS milestone's deliverables against
   those exit-gate criteria — not just that code runs, but that outputs are
   correct. Derive expectations from the authoritative source or the DB, not
   hardcoded guesses. Examples of the bar: `scripts/audit_dean_config.py`
   (Dean config: STD seed, per-size applicability, fail-closed, no dead ends).
   The audit must exit non-zero on any failure.

3. **Cross-family / prior-correction regression.** Run
   `scripts/run_all_fybroc_audits.py` and require **exit 0 — "ALL CORRECTIONS
   INTACT"**. Any prior correction that regresses blocks exit and must be
   reconciled (never override a correction to make new work pass).

4. **Isolation / no-collateral-damage check.** Prove the frozen/other family was
   not altered: compare row counts (and key invariants) before/after for any
   shared table, and confirm shared-schema changes are backward-compatible
   (e.g. nullable columns, additive indexes). State the before/after numbers.

5. **Build/verify.** Confirm the code compiles/imports and any relevant tests
   pass. Clean up temporary scripts/files created during the work.

6. **Evidence doc.** Write/update `docs/evidence/<MILESTONE>/…_EXIT.md`: what was
   published, how it was verified (with the audit numbers), what could NOT be
   verified, and every known gap (pending-engineering items, inert data, etc.).
   Record the exact commands used so the audit is reproducible.

7. **Roadmap + register update.** Mark the milestone complete against its exit
   gate in `docs/PROJECT_MASTER_ROADMAP.md` (bump version + CHANGE note) and
   `docs/progress/MilestoneRegister.md`. Do not silently redefine the objective.

8. **Git checkpoint.** Commit with a descriptive message covering the full scope;
   push to `claude` AND `origin`, both `main` and the feature branch (project
   convention).

9. **Explicit exit-gate decision.** State PASS/FAIL against each criterion. On
   PASS, report the result and the next permitted milestone, and **wait for the
   user's explicit go-ahead before starting it**. On FAIL, remain in the
   milestone and fix the root cause.

## Honesty rules

- A command exiting 0 is NOT proof of correctness — verify the actual output
  against the criterion.
- Report every gap plainly. Pending-engineering items and known-inert data are
  disclosed in the evidence doc, not glossed over.
- If an audit cannot verify something (environment/data limits), say so
  explicitly rather than implying it passed.

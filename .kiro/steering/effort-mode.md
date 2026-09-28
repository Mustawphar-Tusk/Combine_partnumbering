# Effort mode — match verification cost to change size

**Status:** always-on process rule. Governs how much verification/audit/ceremony
a change gets, to keep credit consumption proportional to the work.

## The two modes

### LEAN mode (default for one-off / small changes)
Use for a small, well-scoped change: a single-field/single-function edit, a bug
fix, a config tweak, a UI/enforcement one-liner, a doc edit, or anything touching
a handful of lines with a clear blast radius.

In LEAN mode:
- Make the edit.
- Run ONLY the directly relevant check (e.g. re-run the one audit that covers the
  changed behavior, or a single targeted query/probe). Do NOT run the full
  `run_all_fybroc_audits.py` gate speculatively.
- Prefer one targeted DB query / API probe over writing throwaway `_tmp_*` scripts.
- Do NOT auto-produce evidence docs, roadmap version bumps, or MilestoneRegister
  updates.
- Keep tool calls and re-reads minimal; don't re-verify things already confirmed.
- COMMIT the change (see "Always commit" below), but skip the full milestone-exit
  ceremony.

### FULL mode (big changes / milestones)
Use for: a milestone (F/D/U/T/P phase), a new authoritative source adoption, a
schema/loader change, a multi-file feature, anything with cross-family blast
radius, or anything that reloads/republishes data.

In FULL mode, apply `.kiro/steering/milestone-exit-audit.md` in full:
milestone-specific audit + `run_all_fybroc_audits.py` ("ALL CORRECTIONS INTACT")
+ isolation check + evidence doc + roadmap/register update + commit/push, then the
explicit exit-gate PASS/FAIL decision.

## Choosing the mode
- Default to LEAN. Escalate to FULL only when the change fits a FULL trigger above.
- When genuinely unsure which mode a change needs, ASK the user before running the
  expensive full regression gate or the full exit ceremony.
- If a LEAN change unexpectedly touches constraint enforcement, shared/frozen data,
  or the Fybroc↔Dean boundary, run the one relevant guard; escalate to FULL (and
  say so) only if that guard shows cross-family or regression risk.

## Always commit
Every correction MUST be committed after it is made and verified — this matters so
the UI/runtime reflects the change and nothing is left uncommitted. This applies in
BOTH modes.
- LEAN: a focused commit of just the changed files with a clear message. Pushing
  to remotes (claude + origin, main + feature) is done, but the heavy multi-branch
  ceremony/roadmap bump is FULL-mode only unless the user asks.
- FULL: commit + push per the milestone-exit rule (claude AND origin, main AND
  feature).
- Never leave a verified correction uncommitted.

## Cost discipline (both modes)
- Don't re-run long/expensive commands to re-confirm a result already obtained.
- Ensure port 8080 is free before running the Fybroc gate so it isn't run twice.
- Clean up `_tmp_*` scripts, but prefer not creating them in the first place for
  small checks.

# D110 — Dean PN: drop Additional Options + Testing & Documentation groups

**Date:** 2026-08-26
**Milestone:** D110 — Dean Configuration (part-number format change)
**Type:** ENGINEERING DECISION. Dean-only PN format change (Python resolver + SQL
assembler) + one-time cleanup of stale pre-change products. Fybroc PN format
untouched.

---

## 1. Decision

Per engineering (2026-08-26): **Additional Options** and **Testing &
Documentation** are NOT part-number drivers for Dean. They are removed from the
Dean part number. The two trailing dash-groups are dropped, so the Dean PN now
ends at the motor group.

Example — RA3146:

```
before:  D770-004L-GA01-000S-00000-0000-000000-00-000000   (9 groups)
after:   D770-004L-GA01-000S-00000-0000-000000             (7 groups)
```

Group mapping (unchanged for the surviving groups):
`base - wet_end - trim+impeller_options - power_frame - flush+barrier+cooling -
frame+baseplate - motor+motor_options`. The dropped groups were
`- additional_options` and `- testing+documentation` (both inert placeholders).

## 2. Implementation (Dean-only; Python + SQL kept in parity)

- **Python resolver** `src/api/dean_identifier.py`: the `py_pn` f-string and
  `assemble_pn()` no longer append `-{additional_options}-{testing}{documentation}`.
  The three segments are still resolved into the payload / `segment_debug` (for
  reference and back-compat), but they are not part of the PN.
- **SQL assembler** `sql/23_Create_Assemble_Configured_Product.sql` (DEAN branch):
  the `@PartNumber` CONCAT no longer appends `'-', @d_addl, '-', @d_test, @d_doc`.
  `@d_addl` / `@d_test` / `@d_doc` are still read from `@SegmentsJson`
  (back-compat) but omitted from the assembled PN. Re-applied with
  `CREATE OR ALTER`. The **Fybroc branch is untouched**.

Both sides drop exactly the same two groups, so python==SQL parity holds. This is
the only place the Dean PN is assembled (verified: no other Python or SQL PN
assembly references `additional_options` / `testing` / `documentation`).

## 3. One-time stale-data cleanup

Reuse in `cfg.usp_AssembleConfiguredProduct` is signature-keyed, so Dean
configurations persisted BEFORE this change would keep returning their stored
9-group PN. Deleted all **30** Dean `cfg.ConfiguredProduct` rows (0 quote-line /
BOM references); Fybroc `cfg.ConfiguredProduct` (1196) untouched. The corrected
assembler re-persists the new 7-group PN on next resolve.

## 4. Verification

Live (API) — every sampled series resolves to the new 7-group PN,
`parity_ok=True`, no `?`:

| Series | PN (new) |
|--------|----------|
| RA3146 | `D770-004L-GA01-000S-00000-0000-000000` |
| RA2096 | `D779-000R-CA01-0001-00000-0000-000000` |
| CNV206 | `D460-1SW1-CA01-1HWJ-01000-0000-000000` |
| R5140  | `D659-0VU9-GA0D-008S-00000-0000-000000` |
| RM5140 | `D713-0A3K-GA01-1HWN-00000-0000-000000` |

**Regression (all green):** `audit_dean_wet_end_resolve` 32/0,
`audit_dean_baseplate_combos` 23/0, `audit_dean_baseplate_coupling` 301/0,
`audit_dean_flush_plan` 15/0, `audit_dean_std_consistency` 7/7,
`audit_dean_config` 28/0, `audit_dean_codependencies` 13/0,
`run_all_fybroc_audits` **ALL CORRECTIONS INTACT 9/9** — including
`audit_identifier_parity`, `audit_bom_engine`, and `audit_quote_engine` (critical:
the shared SQL assembler proc changed, but only its DEAN branch, so Fybroc PN
assembly / parity / BOM / quote are unaffected).

**Isolation:** Fybroc `cfg.ConfiguredProduct` 1196 unchanged; FYBROC watermarks
unchanged (FeasibleConstraint 4487, ConstraintFieldMap 28, SeriesFieldOption 3638,
stg 300608).

## 5. Notes

- Additional Options and Testing & Documentation remain selectable configuration
  areas / resolved segments; they simply no longer appear in the part number.
- Fybroc part numbers are unaffected (the change is gated to the SQL DEAN branch
  and the Dean Python resolver).

## 6. Exit-gate decision

> Additional Options and Testing & Documentation no longer drive the Dean part
> number; the Dean PN ends at the motor group; python==SQL parity holds; Fybroc
> untouched.

**PASS.** RA3146 resolves to `D770-004L-GA01-000S-00000-0000-000000` (7 groups,
parity True). All Dean audits pass and the Fybroc gate is ALL CORRECTIONS INTACT
(incl. identifier parity, BOM, quote). Fybroc PN format and watermarks unchanged.

## 7. Reproduction commands

```powershell
# apply the SQL assembler change
sqlcmd -S localhost -d PumpConfiguratorDB -E -C -b -i "sql\23_Create_Assemble_Configured_Product.sql"

# API on 127.0.0.1:8080, then resolve a Dean config (e.g. RA3146) and confirm 7 groups
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_dean_wet_end_resolve.py
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\run_all_fybroc_audits.py
```

**Next permitted milestone:** D150 — Exhaustive Dean Regression (still parked per
the user; further configuration work precedes it). Do NOT start D150 without
explicit go-ahead.

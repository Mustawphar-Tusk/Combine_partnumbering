# M023.2 — Dean Applicability Compiler

## Purpose

Compile Dean `Pump Options` into normalized model/field/option applicability candidates without reopening the 84 MB Dean Rev2 workbook.

Inputs:

- `exports/m023_dean_source_reconciliation.json` from successful M023.1.1
- `workbooks/Dean/PumpConfiguration_Logic.xlsm` / `Pump Options`

The compiler opens only the small `PumpConfiguration_Logic.xlsm` workbook once.

## Safety boundary

The compiler accepts only reconciled model classifications:

- `SHARED_MATCH`
- `SHARED_ALIAS_MATCH`
- `SHARED_REV2_OVERRIDE`
- `LOGIC_ONLY_SUPPLEMENTAL_READY`

`LOGIC_ONLY_REVIEW` models such as Deanline `MDL1-*` are blocked and never become applicability candidates.

## Correct matrix alignment

The first physical column of each Pump Options field group is itself the first option column.

Example:

- group starts at `N`
- Config Options domain contains 9 Pump Material values
- option columns are `N:V`
- any trailing spacer column before the next group is ignored

This fixes the common error of starting at `N+1` and dropping the first option/default for every field.

The compiler aligns matrix columns to the ordered rows from the corresponding `Config Options` structured table, not to hardcoded Excel letters.

## Marker semantics

Based on the workbook patterns already observed:

- `STD` = standard and allowed
- `X` = available and allowed
- blank = not available
- `O` = blocked for review until its exact workbook meaning is confirmed
- every unknown marker = blocked for review

This is deliberately conservative. Unknown values can never become runtime-valid options.

## Outputs

- `exports/m023_dean_applicability_summary.json`
- `exports/m023_dean_applicability_candidates.csv`
- `exports/m023_dean_applicability_ready.csv`
- `exports/m023_dean_applicability_review.csv`
- `exports/m023_dean_applicability_issues.csv`
- `exports/m023_dean_applicability_groups.json`
- `exports/m023_dean_applicability_marker_summary.csv`

No SQL publication occurs in M023.2.

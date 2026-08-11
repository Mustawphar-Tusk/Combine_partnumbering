# M023.3 — Dean Dependency Compiler

## Purpose

Compile the 47 Dean `Codependencies` tables into generic, directionless allowed-tuple constraints.

This milestone uses the cached M023.1 reconciliation JSON. It performs **zero Excel workbook reads**.

## Why allowed tuples

Dean Codependencies are not consistently simple parent -> child relationships.

Examples include:

- Series + Casing Material + Flange Configuration
- Seal Option + Gland Type + Flush Plan + Barrier Plan

Rather than inventing direction, each source table becomes a set of valid tuples. Runtime projection can then answer:

> Given the current valid selections, which values of field X still participate in at least one allowed tuple?

This is compatible with the project requirement that invalid choices are never presented.

## Safety

- no dependency direction is inferred;
- blank dependency cells are not interpreted as wildcards;
- unknown field mappings block the rule;
- unknown option values block only the affected tuple;
- duplicate tuples are deduplicated;
- identity fields such as `SERIES` may participate without being Config Options domains.

## Outputs

- `exports/m023_dean_dependency_summary.json`
- `exports/m023_dean_dependency_rules.csv`
- `exports/m023_dean_dependency_tuples.csv`
- `exports/m023_dean_dependency_review.csv`
- `exports/m023_dean_dependency_issues.csv`

No SQL publication occurs in M023.3.

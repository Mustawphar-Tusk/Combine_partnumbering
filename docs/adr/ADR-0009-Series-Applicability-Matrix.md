# ADR-0009: Compile Series Applicability Matrix

- Status: Accepted
- Date: 2026-08-04

## Decision

Compile the Fybroc `MAIN` worksheet into a normalized relation:

```text
Series + Field + Option Value
```

## Rejected Interpretation

Rows in `FULL LIST` are not treated as complete valid configurations. The sheet is organized as independent allowed-value columns and contains continuation rows.

## Consequences

- Series-level option projection is authoritative.
- Finer constraints among multiple non-series selections still require additional metadata.
- Runtime remains metadata-driven and does not reproduce Excel formulas.

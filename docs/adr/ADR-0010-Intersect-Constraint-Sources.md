# ADR-0010: Intersect Constraint Sources

- Status: Accepted
- Date: 2026-08-04

## Decision

Available values are computed as the intersection of every applicable authoritative source:

```text
Active Attributes
∩ Series Applicability
∩ Valid Segment Combinations
```

## Consequences

- A value excluded by any applicable source is not presented.
- Source counts and applied filters are returned for diagnostics.
- Workbook display variations are normalized for comparison only.

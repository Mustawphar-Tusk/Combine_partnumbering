# M013 – Fybroc Series Constraint Matrix

## Correct Source Interpretation

`MAIN` is the authoritative applicability matrix:

- Column B: source field code
- Column C: option value
- Columns E:O: series applicability markers

`FULL LIST` is a collection of per-field allowed-value columns. Its rows are not complete configuration records and must not be interpreted as complete model combinations.

## Runtime Capability

The platform can now answer:

```text
Given Series 1530:
- Which sizes are valid?
- Which pump materials are valid?
- Which seal types are valid?
- Which motor options are valid?
```

This is the first cross-segment projection layer.

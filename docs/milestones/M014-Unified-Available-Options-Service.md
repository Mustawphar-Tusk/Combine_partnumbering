# M014 – Unified Available Options Service

## Objective

Provide one runtime service that returns currently valid values for a requested field.

## Sources Intersected

1. Active attribute catalog
2. Series applicability matrix
3. Partial valid combination projection

## Value Normalization

Workbook source systems use different display conventions:

- underscores versus spaces
- optional trailing asterisks
- repeated whitespace

Normalization is used only for comparison. The returned display value comes from the primary runtime source, normally the valid combination metadata.

## Result

Clients no longer need to understand engineering rules. They submit:

```text
Family
Selected Series
Current Segment Selections
Target Field
```

and receive only valid values.

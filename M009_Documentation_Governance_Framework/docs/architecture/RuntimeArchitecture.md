# Runtime Architecture

Every identifier segment uses a resolution strategy.

## ATTRIBUTE
One display value maps to one identifier code.

## COMBINATION
An ordered selection set maps to one source ID and one padded base-36 segment.

## Identifier Assembly

```text
Part Number = Base Identifier + Ordered Segment String
SKU         = Base Identifier + Version + Compact Segment String
```

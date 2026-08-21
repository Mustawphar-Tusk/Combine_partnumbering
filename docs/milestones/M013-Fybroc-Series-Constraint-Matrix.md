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

F100.5.1 — Series Sheet Classification Correction
Source

(I confirm this line before this is treated as citable): Confirmed [ by engineering / from existing project knowledge — delete one ], [8/20/2026].

What F100.5 got wrong

The automated business-object classification pass tagged the following seven sheets in Fybroc Attributes and Constraints.xlsx as NEEDS_ENGINEERING_REVIEW, with no established mapping or keyword match:

1500, 1530, 1600, 1630, 2530, 3000, 5500

Correction

These are not unused or leftover sheets. Each holds the detailed configuration breakdown for that one specific Fybroc series. MAIN holds the consolidated, overall-series view and is built on top of them — confirmed by MAIN's own formulas, e.g. cell Q1:

=CONCAT("'", P1, "'!$C$3:$AK$100")

This constructs a reference into whichever of the seven series sheets is named in P1. That cross-reference is intentional and internal to this workbook, not a broken or orphaned link.

Reclassification

All seven sheets should carry the same tags as MAIN:

constraints
configuration_fields

Confidence: ESTABLISHED, citing this document (mirrors how MAIN and FULL LIST already cite docs/milestones/M013-Fybroc-Series-Constraint-Matrix.md).

Not yet resolved by this correction

This note covers only the seven series sheets. The following sheets in Price Estimator-Fybroc.xlsm remain open — a general answer was given for that workbook ("focuses on different kinds of material and adders used in building different kinds of pump, all of which play a role in the overall price"), which confirms the workbook's overall purpose but does not resolve these specific sheets individually:

Aquarium, Vert. Spares, ACC, CC-Old, CC-New, M-Req, Top Level, NewRules 5-2-23, Batch_Descriptions

# M023.1 — Dean Source Reconciliation

## Purpose

Create a version-friendly reconciliation layer for Dean configuration metadata before any Dean runtime publication.

Dean is intentionally sourced from two authoritative workbooks with different responsibilities:

- `Dean Data Sheet Rev 2.xlsm`
  - ordered configuration workflow
  - authoritative model/A-number reference used to derive the D-number base identifier
  - legacy numbering tables and quote workbook
- `PumpConfiguration_Logic.xlsm`
  - supplemental option domains
  - model/series/size applicability
  - codependencies
  - pricing/adders lineage

The reconciliation compiler does **not** publish runtime metadata and does **not** infer pricing semantics.

## Identifier contract preserved

For authoritative Dean A-number model references:

- `A779` -> base identifier `D779`
- Part Number later begins `D779-...`
- SKU later begins `D779-V1-...`

`PumpConfiguration_Logic.xlsm` may provide additional model rows, but Rev2 model-reference data remains authoritative until a discrepancy is explicitly reconciled.

## Dynamic update principle

Workbook column letters are not runtime contracts.

The compiler discovers Pump/Price matrix groups by their structured header formulas, such as:

`Table88[[#Headers],[Pump Material]]`

This makes a workbook revision re-compilable even if configuration groups move to different columns.

## Outputs

Running:

`python .\scripts\compile_dean_source_reconciliation.py`

creates:

- `exports/m023_dean_source_reconciliation.json`
- `exports/m023_dean_field_reconciliation.csv`
- `exports/m023_dean_model_reconciliation.csv`
- `exports/m023_dean_dependency_candidates.csv`
- `exports/m023_dean_reconciliation_issues.csv`

## Classification

Fields are classified as:

- `SHARED`
- `REV2_ONLY`
- `LOGIC_ONLY_SUPPLEMENTAL`
- `LOGIC_DEPENDENCY_ONLY`
- `LOGIC_PRICING_ONLY`

Model keys are classified as:

- `SHARED_MATCH`
- `REV2_ONLY`
- `LOGIC_ONLY_REVIEW`
- `MODEL_IDENTIFIER_MISMATCH`

Only `SHARED_MATCH` model references are automatically publication-ready in M023.1.

## Safety

M023.1 deliberately preserves raw matrix values (`STD`, `X`, `C.F.`, `O`, numbers, etc.) without assigning business meaning. Marker semantics belong to the later applicability/pricing compilers after workbook behavior is formally validated.

No Fybroc runtime files are changed by this milestone.

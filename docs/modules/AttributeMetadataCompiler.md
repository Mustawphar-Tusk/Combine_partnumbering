# Attribute Metadata Compiler

## Purpose

Compile one-to-one Fybroc identifier attributes from the `Attributes` worksheet.

## Source Columns

| Field | Display | Code |
|---|---|---|
| SERIES | F | G |
| SIZE | I | J |
| PUMP_MATERIAL | L | M |
| IMPELLER_TRIM | O | P |
| MOTOR_MODIFICATIONS | R | S |
| TESTING | U | V |

## Outputs

- `exports/fybroc_attribute_candidates.json`
- `exports/fybroc_attribute_candidates.csv`
- `exports/fybroc_attribute_issues.csv`

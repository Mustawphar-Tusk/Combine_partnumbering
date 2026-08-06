# M009 – Attribute Metadata Platform

## Objective

Remove caller-supplied direct identifier codes and resolve simple attributes from SQL metadata.

## Scope

- Metadata publication model
- Attribute staging and publication
- Fybroc direct-attribute compiler
- Attribute resolver
- Resolver registry
- Platform status command
- Documentation and tests

## Initial Fybroc Attributes

- SERIES
- SIZE
- PUMP_MATERIAL
- IMPELLER_TRIM
- MOTOR_MODIFICATIONS
- TESTING

## Definition of Done

- Attribute candidates compile from authoritative workbook columns.
- Candidates load into SQL staging.
- Validated candidates publish atomically.
- Runtime resolves display values to codes.
- Resolver registry supports ATTRIBUTE and COMBINATION.
- Tests, milestone log, ADRs, and release notes are updated.

# ADR-0015: Require Constraint Dependency Closure

- Status: Accepted
- Date: 2026-08-04

## Decision

Identifier generation requires a complete signed state whose every
field is classified by an authoritative constraint policy.

## Consequences

- Impeller Trim is narrowed by Series and Size.
- Motor Modifications are narrowed by the completed Motor Assembly.
- Three modification codes are concatenated into the identifier.
- Silent scenario fallback is prohibited.
- New fields cannot enter navigation without a coverage classification.

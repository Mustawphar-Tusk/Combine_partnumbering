# ADR-0014: Reconcile Source Vocabulary Through Metadata

- Status: Accepted
- Date: 2026-08-04

## Decision

Represent equivalent labels from authoritative workbooks in a
family-specific runtime metadata profile.

## Rejected Approaches

- Do not weaken the intersection.
- Do not remove series applicability.
- Do not hardcode Fybroc synonyms in API routes.
- Do not expose unmatched values.

## Consequence

A value is presented only when its canonical equivalence exists in
every applicable source, or when the current combination explicitly
returns a metadata-approved not-applicable value.

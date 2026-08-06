# ADR-0013: Generate Identifiers Only from Completed Signed State

- Status: Accepted
- Date: 2026-08-04

## Decision

Part Number and SKU generation are reachable only after the allowable
navigator has issued a complete signed configuration state.

## Rejected Design

Do not expose an identifier-generation endpoint that accepts arbitrary
field/value selections.

## Consequences

- Every generated identifier is derived from server-issued choices.
- Attribute and combination metadata revisions are traceable.
- The final configuration signature is deterministic.
- Defensive token checks protect the boundary without becoming a
  user-facing invalid-selection workflow.

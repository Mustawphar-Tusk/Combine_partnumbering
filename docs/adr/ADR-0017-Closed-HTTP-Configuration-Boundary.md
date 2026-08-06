# ADR-0017: Use a Closed HTTP Configuration Boundary

- Status: Accepted
- Date: 2026-08-04

## Decision

Expose configuration through family-scoped Start, Advance, and
Finalize endpoints.

Advance accepts only:

```text
stateToken + optionToken
```

Finalize accepts only:

```text
completed stateToken
```

## Rejected Designs

- Do not expose a generic validate-field endpoint.
- Do not expose a generate-from-selections endpoint.
- Do not accept Part Number or SKU from clients.
- Do not accept arbitrary engineering values.
- Do not route families by decoding unsigned client data.

## Consequences

- Excel and web clients use the same configuration contract.
- The family code is explicit in the URL.
- Request schema violations are rejected before domain execution.
- Persistence remains reachable only through a complete signed state.

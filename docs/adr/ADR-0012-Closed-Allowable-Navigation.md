# ADR-0012: Use Closed Allowable-Configuration Navigation

- Status: Accepted
- Date: 2026-08-04

## Decision

Clients may select only opaque option tokens issued for the current
signed configuration state.

## Rejected Design

Do not accept arbitrary field/value pairs and then explain why they are
invalid.

## Consequences

- Invalid engineering values are not presented.
- Free-text configuration submissions are not part of the API.
- Every selection narrows the allowable configuration space.
- Runtime checks remain defensive safeguards only.

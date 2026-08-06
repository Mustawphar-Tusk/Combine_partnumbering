# ADR-0008: Metadata Publication Model

- Status: Accepted
- Date: 2026-07-16

## Decision

Engineering metadata is released through a publication object rather than publishing each table independently.

## Consequences

- A complete metadata release can be Draft, Testing, Active, Retired, or Failed.
- Runtime records can reference the exact publication used.
- Rollback and audit become practical.
- Multiple engineering revisions can coexist safely.

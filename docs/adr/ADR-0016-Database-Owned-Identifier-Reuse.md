# ADR-0016: Database-Owned Identifier Reuse

- Status: Accepted
- Date: 2026-08-04

## Decision

The SQL database owns the atomic insert-or-reuse decision for configured
products.

## Reason

A Python lookup followed by an insert would permit two concurrent requests to
create duplicate product records. A transaction-owned SQL application lock,
locking reads, and unique indexes provide one authoritative decision point.

## Consequences

- repeated requests reuse one registry row;
- concurrent requests cannot create duplicate signatures;
- Part Number and SKU collisions are rejected;
- every request is auditable;
- the API and Excel clients remain consumers rather than identity owners.

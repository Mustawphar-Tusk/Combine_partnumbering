# M018 – Identifier Persistence and Reuse

## Objective

Persist a completed allowable configuration once and reuse the same Part
Number and SKU for every later request with the same configuration
signature.

## Boundary

Persistence accepts only the result of:

```text
complete signed allowable state
→ identifier generation
→ persistence payload
```

It does not accept arbitrary configuration fields or engineering values.

## Database Ownership

`cfg.usp_PersistConfiguredProduct` owns the final create-or-reuse decision.
The procedure:

1. acquires a transaction-owned application lock on family + signature;
2. looks up the existing configured product under `UPDLOCK, HOLDLOCK`;
3. reuses the existing row when signature, selections, Part Number, and SKU
   agree;
4. creates the registry, 41 selections, and 10 resolved segments when no row
   exists;
5. rejects signature collisions and identifier collisions;
6. records every request in the audit table.

## Durable Metadata

The registry stores:

- configuration signature;
- Part Number and SKU;
- ordered selections;
- ordered resolved identifier segments;
- source metadata IDs;
- canonical configuration JSON;
- publication, series, combination, and dependency batch IDs;
- request count and audit history.

## Reuse Contract

```text
same family + same configuration signature
→ same registry ID
→ same Part Number
→ same SKU
→ no duplicate selection or segment rows
```

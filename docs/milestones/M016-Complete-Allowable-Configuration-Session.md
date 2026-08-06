# M016 – Complete Allowable Configuration Session

## Objective

Complete the entire configuration using only server-issued allowable
option tokens, then generate identifiers from the completed signed
state.

## Closed Loop

```text
Allowable Series token
→ allowable Size token
→ allowable configuration tokens
→ complete signed state
→ metadata segment resolution
→ Part Number
→ SKU
→ configuration signature
```

## Public Boundary

Identifier generation does not accept arbitrary engineering values.
The session finalizer accepts only a signed complete state created by
the allowable navigator.

## Metadata Resolution

Attribute segments resolve from the active metadata publication.
Combination segments resolve from the combination batch embedded in
the runtime revision.

## Token Regression Corrected

Token JSON is canonically sorted before signing. Consequently,
selection order cannot be validated through dictionary insertion
order. State integrity is now checked against membership in the
required field-order prefix.

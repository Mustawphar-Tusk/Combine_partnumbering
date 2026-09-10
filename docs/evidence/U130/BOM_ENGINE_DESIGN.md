# U130 — Reusable BOM Engine — design (Option 1: grounded BOM from real data)

**Identity chain:** configuration → BOM → PN → SKU, where **same BOM = same PN =
same SKU**. The BOM is a deterministic function of the resolved configuration.

**Scope (Option 1, agreed with product owner):** generate BOM lines from data we
authoritatively have today — the priced components (`BASE_PUMP`, `SEAL` from
`price.PriceRule`, with source lineage) plus **structural** component lines derived
from the resolved Part-Number segments. The full physical parts breakdown
(Coupling / Baseplate / Motor internals / adders) requires new workbook extraction
and is a later milestone; adding those lines later enriches the BOM without
changing the engine or breaking the identity invariant.

## BOM line model

Every line: `ComponentCode`, `ComponentDescription`, `Quantity`, `UnitOfMeasure`
(default `EA`), optional `UnitCost`, `SourceReference`.

### Structural lines (identity-bearing, from resolved segments)

| ComponentCode  | Attributes (from segments)                     | Present |
|----------------|------------------------------------------------|---------|
| PUMP_ASSEMBLY  | series_code + size_code + material_code + trim_code | always |
| PUMP_OPTIONS   | pump_options code                              | always |
| SEAL_ASSEMBLY  | seal_mfg + seal_assy code                      | horizontal only (vertical omits the seal segment) |
| OPTIONS        | options code                                   | always |
| MOTOR_ASSEMBLY | frame_size + motor_assy code                   | always |
| MOTOR_MODS     | motor_mods code                                | always |
| TESTING        | testing code                                   | always |

### Priced lines (real cost + lineage from price.PriceRule)

- `BASE_PUMP` — cost keyed by series/size/material; lineage `SourceReference` =
  the matched price rule's source value. Attaches cost to the pump assembly.
- `SEAL` — cost keyed by series + seal type; present only when a mechanical seal
  is configured.

Priced amounts populate `UnitCost`; they do **not** participate in identity.

## Canonical BOM signature

```
line_key   = f"{ComponentCode}|{attributes}|{Quantity}|{UnitOfMeasure}"   (lowercased, trimmed)
bom_body   = "\n".join(sorted(line_key for each STRUCTURAL line))          # price EXCLUDED
BOMSignature = SHA-256(bom_body)  hex upper
```

Rationale: the signature is the **physical-build identity**. It is computed over
structural line identity only — **excluding UnitCost / ExtendedCost, line numbers,
timestamps, and any volatile field** — so a price change never changes a product's
identity, and the same configuration always yields the same BOM signature.

## Reuse / persistence

- `cfg.BOMHeader` gains a `BOMSignature char(64)` column, unique per configured
  product family, plus `Status='Active'`.
- `cfg.usp_GenerateBOM` takes the resolved segments (+ priced components) JSON,
  builds the structural + priced lines, computes `BOMSignature`, and is
  **idempotent**: if a BOM with the same signature already exists it is reused; a
  new one inserts `BOMHeader` (Active) + `BOMLine` rows.
- Because same configuration → same PN (already enforced) and → same BOM signature,
  **BOM ↔ PN is 1:1**. This is asserted by the BOM audit.

## Invariants (guarded by scripts/audit_bom_engine.py)

1. Every resolved product has a non-empty BOM (≥ the structural lines).
2. Deterministic: two resolves of the same configuration produce the **identical**
   BOM signature.
3. Reuse: the second resolve reuses the existing BOM (no duplicate BOM per product).
4. BOM ↔ PN is 1:1 across a representative matrix (no PN with two BOM signatures,
   no BOM signature under two PNs).

## Parity oracle

Python recomputes the same canonical BOM signature from the lines it builds and
asserts it equals SQL's, mirroring the F150 PN/SKU parity approach.

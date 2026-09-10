# U130 — Reusable BOM Engine — EXIT

**Milestone:** U130 (Reusable BOM Engine)
**Roadmap exit gate:** *"Repeated identical configured products reuse the
appropriate BOM."*
**Approach:** Option 1 — grounded BOM from real data (agreed with product owner).

## What was delivered

The BOM is now generated deterministically from a resolved configuration and is
the **physical-build identity** feeding the chain **configuration → BOM → PN →
SKU** (`same BOM = same PN = same SKU`).

### BOM lines (per resolved configuration)

Structural, identity-bearing lines from the resolved Part-Number segments:
`PUMP_ASSEMBLY`, `PUMP_OPTIONS`, `SEAL_ASSEMBLY` (horizontal only),
`OPTIONS`, `MOTOR_ASSEMBLY`, `MOTOR_MODS`, `TESTING` — 7 lines horizontal, 6
vertical (no seal segment). The priced components we look up (`BASE_PUMP`, `SEAL`
from `price.PriceRule`, with real `UnitCost` + source lineage) are merged onto the
matching structural lines (`PUMP_ASSEMBLY` / `SEAL_ASSEMBLY`).

### Canonical BOM signature (identity)

`SHA-256` over the sorted, lowercased structural line keys
`component_code|attributes|qty|uom`, **price excluded** (no `UnitCost`, no line
numbers, no timestamps). Hashed over `varchar` bytes in SQL to match the Python
UTF-8 parity oracle (same convention as the PN-derived SKU).

### Persistence + reuse

- `cfg.BOMHeader` gains `BOMSignature char(64)` and a filtered unique index
  `UX_BOMHeader_Product_Active` (one Active BOM per configured product).
- `cfg.usp_GenerateBOM` builds the lines, computes the signature, and is
  **idempotent**: same signature for a product → reuse (no duplicate); a changed
  BOM supersedes the prior Active header and inserts a new versioned one.
- Wired into `resolve_configured_product` (`src/api/v2_routes.py`): after the
  configured product is persisted, the endpoint generates the BOM and returns a
  `bom` block (`bom_header_id`, `bom_signature`, `existing_bom`, `line_count`,
  `bom_parity_ok`, `lines`). Python recomputes the BOM signature as a parity
  oracle.

## Changes

- `sql/23_Create_BOM_Engine.sql` — `BOMSignature` column + filtered unique index;
  new `cfg.usp_GenerateBOM` (deterministic line generation, canonical signature,
  idempotent reuse). File set to `QUOTED_IDENTIFIER/ANSI_NULLS ON` (filtered
  index requirement). Already in `sql/00_Deploy_All.sql`.
- `src/api/v2_routes.py` — BOM generation call + `bom` response block + Python
  BOM-signature parity oracle.
- `scripts/audit_bom_engine.py` — new correction guard.
- `scripts/run_all_fybroc_audits.py` — BOM audit added to the gate.

## Verification

- BOM audit `audit_bom_engine.py`: **38/38** — every series generates a
  non-empty BOM; `bom_parity_ok` (Python == SQL signature); deterministic (2nd
  resolve = same signature); reused (2nd resolve `existing_bom=True`); and the
  store-wide invariants **no PN → >1 BOM signature** and **no BOM signature → >1
  PN** (0 violations) — i.e. **same BOM = same PN**.
- Correction gate `run_all_fybroc_audits.py`: **ALL CORRECTIONS INTACT**
  (selections 2096, feasible 14/14, motor 91/91, identifier 44/44, BOM 38/38).
- F160 Excel oracle vs API/SQL identity: **6/6** (identity unaffected).

## Scope note / next

This milestone delivers the BOM *engine* (generation, canonical signature,
reuse, identity wiring) using authoritatively-known data. The **full physical
parts breakdown** (Coupling, Baseplate, Motor internals, and the 14 adder
sections that exist un-extracted in the Price Estimator workbook) is a separate,
later data-extraction milestone. Because the BOM is derived deterministically
from the configuration and the signature is computed over structural line
identity, adding those component lines later **enriches** the BOM without changing
the engine or breaking the `same BOM = same PN = same SKU` invariant.

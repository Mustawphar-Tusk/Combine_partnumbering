# Identity model — SKU derived from Part Number (SKU ↔ PN is 1:1)

**Status:** implemented (split step, before the full BOM engine).
**Rule (product owner):** *"No two SKUs can point to the same PN. The SKU is a
customer-facing number that traces back to a PN; the same SKU recurs only for the
same PN."*  →  **SKU ↔ PN is strictly 1:1.**

## Before

The SKU was derived from the **configuration signature** (SHA-256 of the canonical
configuration JSON). Because the signature is finer-grained than the Part Number
(the PN does not encode every selection), two configurations that resolve to the
**same PN** but hash to **different signatures** produced **different SKUs** —
violating the rule (two SKUs on one PN).

## After

The SKU is now **derived from the Part Number**:

```
token = first 8 hex chars of SHA-256(PartNumber)
SKU   = <FamilyPrefix><Series>-<token><VersionLetter>     e.g. F1500-EA8F8AFDA
```

- **Same PN → same SKU** (the token is a pure function of the PN).
- **Different PN → different SKU.**
- **No two SKUs can share a PN**, by construction.

Reuse is keyed on the **Part Number**: if the PN already exists,
`cfg.usp_AssembleConfiguredProduct` returns the stored row (existing=True) with its
canonical PN + SKU, and never attempts a second insert for that PN. The
configuration signature is retained only as a detail/audit column (still
order-stable via `sort_keys` from F160).

## Changes

- `sql/22_Create_Identifier_Generation.sql` — `cfg.usp_GenerateSKU` now takes
  `@PartNumber` and derives the token from `HASHBYTES('SHA2_256', @PartNumber)`;
  reuses the existing SKU if the PN is already stored. (`@ConfigurationSignature`
  kept as an optional, unused back-compat parameter.) `usp_ResolveConfiguredProduct`
  updated to pass `@PartNumber`.
- `sql/23_Create_Assemble_Configured_Product.sql` — SKU call switched to
  `@PartNumber`; reuse now keys on the **Part Number** (returns the existing row
  and its stored SKU/signature) instead of colliding on `UNIQUE(PartNumber)`.
- `src/api/v2_routes.py` — parity oracle now also checks `sku_pn_ok` (the SKU
  carries the PN-derived token) and returns it in the response. Also fixed a
  **pre-existing** parity-oracle gap: the identifier lookup now tries the
  `*`-suffixed (standard-default) form of a value — the identifier table stores
  standard options with a trailing `*` (e.g. standard material `VR-1` is stored as
  `VR-1*`), so a plain `vr-1` selection previously resolved to `?`. This only
  affected the Python parity oracle; SQL identity was always correct.
- `scripts/migrate_sku_from_partnumber.py` — one-time, guarded, idempotent
  re-derivation of existing regenerable rows' SKUs from their PNs; verifies the
  PN↔SKU 1:1 invariant.
- `scripts/audit_identifier_parity.py` — now asserts, per series, that the SKU is
  PN-derived, plus two store-wide invariants: **no PN maps to >1 SKU** and **no
  SKU maps to >1 PN**.

## Verification

- Identifier parity audit: **44/44** (adds SKU-from-PN per series + both 1:1
  invariants, 0 violations).
- Correction gate `run_all_fybroc_audits.py`: **ALL CORRECTIONS INTACT**
  (selections 2096, feasible 14/14, motor 91/91, identifier 44/44).
- F160 Excel oracle vs API/SQL identity: **6/6** (identity unaffected).
- End-to-end: same config (any key order) → same PN + same SKU (existing=True);
  different config → different PN + different SKU.

## Next milestone — BOM → PN → SKU

This step makes SKU ↔ PN 1:1 using what exists. The next milestone builds the
**Reusable BOM Engine** so the **BOM** determines the PN: *same BOM = same PN =
same SKU*. Today the BOM tables (`cfg.BOMHeader` / `cfg.BOMLine`) are scaffolding —
no BOM-line generation, no BOM signature, and the resolve path does not touch the
BOM. That work (generate BOM lines from a configuration, hash a canonical BOM
signature, and repoint reuse to the BOM signature) is the immediate next task.

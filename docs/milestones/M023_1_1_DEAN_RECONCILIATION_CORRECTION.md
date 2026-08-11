# M023.1.1 — Dean Reconciliation Correction

## Evidence-backed corrections

This patch resolves the reconciliation issues identified by M023.1 without weakening source validation.

### Rev2 sequence 53

Sequence 53 is intentionally absent in `Dean Data Sheet Rev 2.xlsm`.
The source proceeds from:

- 52 Cooling Plan
- 54 Cooling Plan Piping
- 55 Cooling Plan Extras

The reconciliation profile now declares sequence 53 as an expected source gap. Unexpected future sequence gaps remain errors.

### PHP model identifier aliases

Rev2 Reference Data is authoritative. PumpConfiguration_Logic spellings are normalized only for reconciliation:

- A614-PHP -> A614P
- A351-PHP -> A351P
- A352-PHP -> A352P
- A353-PHP -> A353P
- A356-PHP -> A356P

The authoritative D-number remains derived from the Rev2 A-number, e.g. `A351P -> D351P`.

### PH2170 / PH3170 source drift

For A415 and A416, both Rev2 Reference Data and External References agree on PH2170, while PumpConfiguration_Logic labels those two rows PH3170. The Logic rows are reconciled to PH2170 by metadata rules. This does not change the valid PH3170 A417 row or PH2170 A418 row.

### RA3246 stale Logic mappings

Both Rev2 Reference Data and External References agree on:

- RA3246 / 6x8x15.5 -> A799
- RA3246 / 8x10x15.5 -> A800

PumpConfiguration_Logic contains A798 and A799 respectively. M023.1.1 preserves the verified Rev2 mappings through explicit profile-driven overrides.

### RA3146 11.5 supplemental models

PumpConfiguration_Logic adds valid A-number-shaped model candidates that do not exist in Rev2 Reference Data:

- A770 1x2x11.5
- A771 1.5x3x11.5
- A772 2x3x11.5
- A773 3x4x11.5
- A774 4x6x11.5

Under the configured gap-fill policy, A-number Logic-only models are classified `LOGIC_ONLY_SUPPLEMENTAL_READY` with Logic lineage preserved.

### Deanline

`MDL1-.75` and `MDL1-1.5` do not satisfy the standard Dean A-number -> D-number contract. They remain `LOGIC_ONLY_REVIEW` and are not publication-ready.

## Safe field aliases

Only clear naming variants are normalized:

- Auxillary Nameplate -> Auxiliary Nameplate
- Casing Wear Ring -> Casing Wear Rings
- Frame Size -> Frame
- Impeller Wear Ring Material -> Imp. Wear Ring Mat.
- Paint Options -> Paint

Conditional seal/elastomer/hardware fields are intentionally not collapsed here; they belong to M023.2 applicability logic.

## New generic reconciliation capabilities

The compiler now supports metadata-driven:

- expected sequence gaps
- field aliases
- model identifier aliases
- series/size key aliases
- verified Rev2 overrides
- supplemental Logic-only A-number models
- continued blocking of non-A-number Logic-only models

No Dean-specific `if` logic is added to the runtime, and no Fybroc runtime files are changed.

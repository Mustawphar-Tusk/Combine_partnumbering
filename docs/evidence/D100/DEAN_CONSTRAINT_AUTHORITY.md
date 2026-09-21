# D100 — Dean Constraint Authority: PumpConfiguration_Logic.xlsm

**Date:** 2026-08-26
**Source:** `workbooks/Dean/PumpConfiguration_Logic.xlsm` (0.5 MB)
**Decision:** `PumpConfiguration_Logic.xlsm` is designated the **AUTHORITATIVE
Dean constraint table** (engineering direction). It is the Dean analogue of the
Fybroc `Feasible Constraints` model.
**Scope:** Analysis/inventory only. No runtime, SQL, or Fybroc changes.

---

## 1. Workbook structure

Four visible sheets, no defined names, no VBA constraint logic (data-driven):

| Sheet | Dims | Role |
|-------|------|------|
| **Config Options** | 103 × 148 | Field → option-domain dictionary (74 configurable fields) — the master list of Dean fields and their valid values |
| **Codependencies** | 171 × 50 | **Authoritative constraint table** — 47 allowed-combination sub-tables (726 rows) |
| Pump Options | 233 × 599 | Per-(A Number, Series, Size) applicability matrix (X / STD) — configuration bundles + materials. (Applicability, not constraint.) |
| Price Options | 225 × 686 | Same shape as Pump Options with base prices — pricing, covered in DEAN_PRICING_SOURCE_INVENTORY |

The two sheets that define the **constraint authority** are **Config Options**
(what fields/options exist) and **Codependencies** (which combinations are
allowed).

## 2. Config Options — field dictionary (74 fields)

Layout: header row 3; each field occupies a label column with its valid options
listed down the rows (a blank spacer column separates fields). Full field list
with option counts:

| # | Field | Options | # | Field | Options |
|---|-------|--------:|---|-------|--------:|
| 1 | Pump Configuration | 8 (+note) | 38 | Inboard Rotating Face Material | 4 |
| 2 | Pump Material | 9 | 39 | Inboard Stationary Face Material | 5 |
| 3 | Casing Material | 9 | 40 | Inboard Elastomer | 10 |
| 4 | Casing Drain | 8 | 41 | Inboard Hardware Material | 6 |
| 5 | Casing Taps | 4 | 42 | Outboard Rotating Face Material | 4 |
| 6 | Casing Gasket | 4 | 43 | Outboard Stationary Face Material | 5 |
| 7 | Flange Configuration | 7 | 44 | Outboard Elastomers | 9 |
| 8 | Spot Facing | 2 | 45 | Outboard Hardware Material | 6 |
| 9 | Casing Wear Ring | 6 | 46 | Hydropads | 2 |
| 10 | Tack weld wear rings | 2 | 47 | Pumping Ring | 2 |
| 11 | Casing Mounting | 5 | 48 | Throttle Bushing | 2 |
| 12 | Seal Chamber Config | 9 | 49 | Min-Flo Bushing | 3 |
| 13 | Shipping Gasket | 2 | 50 | Lantern Ring | 4 |
| 14 | Casing Heat Jacket | 2 | 51 | Flush Plan | 21 |
| 15 | Impeller Trim | 96 | 52 | Flush Plan Code | 100 |
| 16 | Impeller Balance | 2 | 53 | Barrier Plan | 10 |
| 17 | Impeller Material | 8 | 54 | Barrier Plan Code | 19 |
| 18 | Impeller Wear Ring Material | 6 | 55 | Barrier Plan Extras | 0 (empty) |
| 19 | Shaft Configuration | 6 | 56 | Cooling Plan | 14 |
| 20 | Shaft Material | 7 | 57 | Cooling Plan Piping | 3 |
| 21 | Bearing Lubrication | 4 | 58 | Cooling Plan Extras | 4 |
| 22 | Bearing Seal | 4 | 59 | Frame Size | 84 |
| 23 | Oiler Options | 6 | 60 | Drip Cover | 2 |
| 24 | Sight Glass | 2 | 61 | Conduit Box | 2 |
| 25 | Bearing Frame Cooling | 4 | 62 | Baseplate Type | 5 |
| 26 | Magnetic Drain | 2 | 63 | Drip Pan | 3 |
| 27 | Expansion Chamber | 2 | 64 | Alignment Lugs | 2 |
| 28 | Coupling Type | 4 | 65 | Lifting Lugs | 2 |
| 29 | Coupling Guard | 4 | 66 | Levelling Screws | 2 |
| 30 | Seal Option | 3 | 67 | Grounding Lug | 2 |
| 31 | Seal Manufacturer | 4 | 68 | Grout Hole | 2 |
| 32 | Seal Configuration | 7 | 69 | Isolation Pads | 2 |
| 33 | Seal Type | 26 | 70 | Stilts | 2 |
| 34 | OLD JC Style | 26 | 71 | Paint Options | 5 |
| 35 | Gland Type | 5 | 72 | Coating | 2 |
| 36 | Gland Gasket | 5 | 73 | Auxillary Nameplate | 2 |
| 37 | Shaft Sleeve Material | 8 | 74 | Crating | 5 |

Notes / flags (see DEAN_CONFLICT_REGISTER):
- **Pump Configuration** option 9 is an instruction, not a value: *"Add
  additional flush and barrier plan questions from Attribute list. Will no
  longer selected 2 character code."* → engineering-review item.
- **OLD JC Style** (col BO) is a legacy John Crane naming column parallel to
  Seal Type → likely deprecated / cross-reference only.
- **Barrier Plan Extras** has 0 options (empty column).
- **Custom** appears as a terminal option on many fields (free-text escape).

## 3. Codependencies — authoritative constraint model (47 sub-tables, 726 rows)

Layout: constraint sub-tables are stacked both horizontally (spacer-delimited
column groups) and vertically (a new sub-table begins where a row's cells are
themselves field-name headers). Every sub-table is an **ALLOW-LIST**: it lists
the value-combinations that ARE permitted for its field tuple. Arity ranges from
2-field pairs to a 4-field quad.

| # | Constraint (fields) | Arity | Allowed rows |
|---|---------------------|:-----:|-------------:|
| 1 | Casing Material × Casing Drain | 2 | 7 |
| 2 | Casing Material × Casing Taps | 2 | 3 |
| 3 | Casing Material × Casing Gasket | 2 | 4 |
| 4 | Casing Material × Spot Facing | 2 | 1 |
| 5 | Casing Material × Casing Wear Ring | 2 | 5 |
| 6 | Casing Material × Tack Weld Wear Rings | 2 | 1 |
| 7 | Casing Material × Casing Mounting | 2 | 4 |
| 8 | Casing Material × Casing Heat Jacket | 2 | 1 |
| 9 | Casing Taps × Flush Plan | 2 | 13 |
| 10 | Series × Casing Material × Flange Configuration | 3 | 1 |
| 11 | Impeller Material × Impeller Trim | 2 | 96 |
| 12 | Impeller Material × Impeller Balance | 2 | 2 |
| 13 | Impeller Material × Impeller Wear Ring Material | 2 | 5 |
| 14 | Shaft Configuration × Seal Type | 2 | 6 |
| 15 | Shaft Configuration × Shaft Sleeve Material | 2 | 7 |
| 16 | Series × Shaft Configuration × Shaft Material | 3 | 4 |
| 17 | Bearing Lubrication × Bearing Seal | 2 | 1 |
| 18 | Bearing Lubrication × Oiler Options | 2 | 15 |
| 19 | Seal Configuration × Seal Type | 2 | 145 |
| 20 | Series × Gland Type × Seal Option | 3 | 1 |
| 21 | Gland Type × Seal Configuration | 2 | 6 |
| 22 | Gland Type × Throttle Bushing | 2 | 5 |
| 23 | **Seal Option × Gland Type × Flush Plan × Barrier Plan** | **4** | 165 |
| 24 | Seal Configuration × Shaft Sleeve Material | 2 | 5 |
| 25 | Seal Configuration × Inboard Rotating Face Material | 2 | 3 |
| 26 | Seal Configuration × Inboard Stationary Face Material | 2 | 4 |
| 27 | Seal Configuration × Inboard Elastomer | 2 | 9 |
| 28 | Seal Configuration × Inboard Hardware Material | 2 | 5 |
| 29 | Seal Configuration × Outboard Rotating Face Material | 2 | 9 |
| 30 | Seal Configuration × Outboard Stationary Face Material | 2 | 12 |
| 31 | Seal Configuration × Outboard Elastomers | 2 | 24 |
| 32 | Seal Configuration × Outboard Hardware Material | 2 | 15 |
| 33 | Seal Configuration × Hydropads | 2 | 1 |
| 34 | Seal Configuration × Throttle Bushing | 2 | 1 |
| 35 | Seal Configuration × Lantern Ring | 2 | 18 |
| 36 | Seal Configuration × Barrier Plan | 2 | 12 |
| 37 | Pumping Ring × Seal Configuration | 2 | 5 |
| 38 | Pumping Ring × Flush Plan | 2 | 1 |
| 39 | Pumping Ring × Barrier Plan | 2 | 2 |
| 40 | Cooling Plan × Seal Chamber Config | 2 | 54 |
| 41 | Cooling Plan × Gland Type | 2 | 9 |
| 42 | Cooling Plan × Casing Mounting | 2 | 20 |
| 43 | Cooling Plan × Bearing Frame Cooling | 2 | 4 |
| 44 | Cooling Plan × Cooling Plan Piping | 2 | 3 |
| 45 | Cooling Plan × Cooling Plan Extras | 2 | 3 |
| 46 | Baseplate Type × Casing Mounting | 2 | 5 |
| 47 | Baseplate Type × Drip Pan | 2 | 4 |

**Total: 47 sub-tables, 726 allowed-combination rows.**

### Constraint semantics (as read from the data)

- **Allow-list.** Each sub-table enumerates the permitted combinations for its
  field tuple. A combination absent from the table is not allowed for those
  fields — subject to the same "governed domain" refinement we applied for
  Fybroc (a table only governs the values it actually mentions; it does not
  silently exclude values it never names). This will matter when this model is
  compiled to SQL in D110.
- **Series-scoped rules exist** (tables 10, 16, 20 carry a `Series` leg, e.g.
  `Deanline`, `DL200`, `DL230`) — the Dean analogue of Fybroc's SeriesApplicability.
- **Directionality.** Several tables are one-directional "X only comes with Y"
  rules (e.g. Shaft Configuration × Shaft Sleeve Material). The Fybroc
  "governed-domain" allow-list fix already handles this shape and should be
  reused for Dean.

## 4. Relationship to the other Dean workbooks

- `PumpConfiguration_Logic.xlsm` = **constraint + option-domain authority** (this doc).
- `Dean Data Sheet Rev 2.xlsm` = Smart Number / part-number construction,
  numbering combination tables, motor/seal/baseplate numbering (identifier
  authority — D110/D130).
- `Copy of Motor Numbering.xlsm` = motor numbering + motor pricing.
- `Dean Pricing Matrix.xlsx` + Price Options sheet = pricing (D120).
- `DeanMasterConfig_v14 - RA - JASON.xlsm` = candidate config source, must be
  reconciled against this constraint authority (see DEAN_CONFLICT_REGISTER).

## 5. Exit-gate contribution

This establishes the Dean **constraint authority** is fully classified and
structurally explained: 74 fields with option domains + 47 allow-list constraint
sub-tables (726 rows), semantics identified, series-scoping identified, and the
compile path to SQL (D110) mapped to the reusable Fybroc feasible-constraint
enforcement (governed-domain allow-list). Open items are captured in
DEAN_CONFLICT_REGISTER.

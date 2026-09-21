# D100 — Dean Source Lineage & Authority

**Date:** 2026-08-26
**Scope:** analysis/inventory only. Classify every Dean workbook by role,
authority, and precedence. Governance: a newer filename does NOT automatically
supersede an older workbook; each is classified explicitly.
**Cross-refs:** DEAN_CONSTRAINT_AUTHORITY.md, DEAN_CONSTRAINT_RECONCILIATION.md,
DEAN_CONFLICT_REGISTER.md, config/workbook_roles.json.

---

## 1. Workbook set (workbooks/Dean/)

| Workbook | Size | Classification | Authoritative for |
|----------|------|----------------|-------------------|
| **PumpConfiguration_Logic.xlsm** | 0.5 MB | **AUTHORITATIVE — constraint + option-domain source** | Configurable **fields + option domains** (Config Options, 74 fields) and **field codependencies** (Codependencies, 47 allow-list tables / 726 combos) |
| **Dean Data Sheet Rev 2.xlsm** | 80 MB | **AUTHORITATIVE — identity + workflow + model list** | Part-number / Smart Number construction, numbering combination tables (wet-end, power-end, baseplate, motor, testing), configuration **field ordering/sections** (93 sequences, 10 sections), **Series×Size applicability** (`Constraints` sheet), **motor frame/frequency sizing** (`Motor Constraints`) |
| **Copy of Motor Numbering.xlsm** | 3.8 MB | **AUTHORITATIVE — motor** | Motor numbering combinations (6,646) + motor pricing (59,675) |
| **Dean Pricing Matrix.xlsx** | 0.3 MB | **AUTHORITATIVE — pricing** | Std Options, Couplings, Base Plates, Shaft Configuration pricing (see DEAN_PRICING_SOURCE_INVENTORY) |
| **DeanMasterConfig_v14 - RA - JASON.xlsm** | 5.6 MB | **NOT a configuration/constraint source — ERP product-master staging** | (see §3) — NOT authoritative for configuration; candidate ERP/export artifact |

## 2. Precedence rules

1. **Field codependencies + option domains** → `PumpConfiguration_Logic.xlsm`
   wins over any overlapping content in the Data Sheet (`Logic`, `Config Info`
   sheets are SUBSET/superseded). Confirmed by engineering direction and by
   `config/workbook_roles.json` (`PumpConfiguration_Logic` roles =
   `["constraints", "matching_selections", "configuration_logic"]`).
2. **Series×Size applicability + motor sizing** → `Dean Data Sheet Rev 2.xlsm`
   (these are NOT present in PumpConfiguration_Logic).
3. **Motor numbering/pricing** → `Copy of Motor Numbering.xlsm`.
4. **Pricing/adders** → `Dean Pricing Matrix.xlsx` (+ Data Sheet Pricing / Seal
   Pricing / Price Options — reconciled in DEAN_PRICING_SOURCE_INVENTORY).
5. **Part-number identity** → `Dean Data Sheet Rev 2.xlsm` Smart Number + VBA
   (`Module2` numbering, `Module4.GeneratePartNumber` → SQL) — D110/D130.

## 3. DeanMasterConfig_v14 - RA - JASON.xlsm — classification

**Classified: ERP product-master / attribute-staging workbook — NOT a Dean
configuration or constraint authority.**

Evidence (structural inventory, 101 sheets):
- `EcoResProductV2Staging` (69,946 × 5; headers `PRODUCTNUMBER`, `PRODUCTNAME`) —
  **"EcoRes" is Microsoft Dynamics 365 F&O / AX product-information terminology.**
  This is a released-product master export/staging sheet, not configuration logic.
- `AtributeList` (134 × 386), `ValidMotorCombos` (1,419 × 8), and ~95 numbered/
  coded sheets (`1`, `1C`, `2`, `23B`, `42D`, `88`, `318` at 13,622 × 33, …) —
  code-keyed data blocks consistent with an attribute/variant staging workbook.
- The `- RA - JASON` filename suffix indicates a **personal working copy**
  (initials), reinforcing that it is not a governed authoritative source.

**Governance decision (RESOLVED, engineering-confirmed):** does NOT supersede any
of the four governed workbooks. It is an **ERP-integration artifact** (D365
EcoRes product master) used later to **map configured products to the ERP**, not
to build the pump configuration. **Deferred** to ERP/product-master integration
(U100 / Phase P); out of scope for D100–D160. Newer version number (v14) does NOT
grant it authority (governance rule: filename recency ≠ authority). See
DEAN_CONFLICT_REGISTER §D1.

## 4. Prior compilation lineage (M023)

Prior M023 work already extracted and compiled the authoritative constraint
source (does not change authority; documents provenance):
- `exports/dean_pumpconfiguration_logic.json` — extraction of Config Options
  (70 option tables) + Codependencies (47 tables) from PumpConfiguration_Logic.
- `exports/m023_dean_dependency_*` — Codependencies compiled to **47
  ALLOWED_TUPLES rules** (M023.3): 42 READY (542 tuples) + 5 BLOCKED_REVIEW,
  `publication_gate: PASS`, `rule_semantics: undirected allowed-tuple, no
  direction inferred`.
- `config/dependency_profiles/dean.json` — declares `rule_type: ALLOWED_TUPLES`,
  identity `[SERIES, SIZE]`, safety flags (no direction inference, unknown
  field/option blocks the tuple).
- SQL state: **no Dean rows published yet** (DEAN = `cfg.PumpFamily` id 1;
  `cfg.MotorConstraint`/`cfg.AttributeValue` = 0 for Dean; `cfg.SeriesFieldOption`
  holds only Fybroc). Publication to SQL is D110, not D100.

## 5. Supersession summary

| Older / overlapping | Superseded by | For |
|---------------------|---------------|-----|
| Data Sheet `Logic` sheet (30 fields) | PumpConfiguration_Logic Config Options (74) | option domains |
| Data Sheet `Config Info` sheet | PumpConfiguration_Logic Config Options | option domains |
| Data Sheet `Codependencies`-like content | PumpConfiguration_Logic Codependencies | field codependencies |
| (none) | Data Sheet `Constraints` | Series×Size applicability (unique) |
| (none) | Data Sheet `Motor Constraints` + Copy of Motor Numbering | motor sizing (unique) |

No workbook remains structurally unexplained. Authority is unambiguous per concern.

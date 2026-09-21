# D100 — Dean Constraint Reconciliation & Authority Mapping

**Date:** 2026-08-26
**Decision (engineering direction):** `PumpConfiguration_Logic.xlsm` is the
**authoritative Dean constraint source** because it holds the complete field
codependency logic. All constraint-like content in `Dean Data Sheet Rev 2.xlsm`
is mapped here and **defers to** `PumpConfiguration_Logic.xlsm`, EXCEPT for two
areas the logic workbook does not cover (Series×Size applicability and motor
frame sizing), which remain sourced from the Data Sheet.
**Scope:** analysis/inventory only — no runtime, SQL, or Fybroc changes.

---

## 1. Where the constraint logic actually lives

### VBA audit (both workbooks)
Extracted VBA is in `docs/evidence/D100/vba/`.

- **PumpConfiguration_Logic.xlsm** — VBA: a single 25-line `Module1.createTable`
  scratch helper (incomplete; loops the Pump Options sheet). **No constraint
  logic in code.** Its authority is entirely **data-driven** in the worksheets
  (Config Options + Codependencies). ⇒ nothing further to extract from code.
- **Dean Data Sheet Rev 2.xlsm** — VBA: 8 modules, ~2,525 lines, but all of it
  is **numbering / identity / database / UI**, not field-constraint enforcement:
  - `Module4.GeneratePartNumber` → calls SQL `sp_GeneratePartNumber` (identity).
  - `Module2` (1,069 lines) → builds numbering combination tables
    (`numberWetEnd`, `numberPowerEnd`, `numberBaseplates`, `numberMotors`,
    `numberTesting`, `numberDocumentation`, `numberCoolingPlans`, …) — part-number
    construction (D110/D130 territory).
  - `Sheet1`/`Sheet2` `Worksheet_Change`, `SetDefaultOptions_Click`,
    `SearchDatabase`, `SaveToDatabase` → UI + DB round-trips.
  - `Module1.getSealOptions` / `InitializeVariables` → seal option lookup + init.
  ⇒ The Data Sheet does **not** own authoritative field codependencies.

**Conclusion:** the authoritative Dean constraint mapping = the **data** in
`PumpConfiguration_Logic.xlsm` (see DEAN_CONSTRAINT_AUTHORITY.md): 74 fields with
option domains + 47 allow-list codependency tables (726 rows).

## 2. Constraint / config content in Dean Data Sheet Rev 2 (mapped)

| Data Sheet sheet | Dims | Content | Reconciliation vs PumpConfiguration_Logic |
|------------------|------|---------|-------------------------------------------|
| **Constraints** | 2892 × 222 | **Series × SIZE** applicability matrix (X marks valid size per series; columns are sizes `0.75x0.75 … 3x4x10`, rows are series `Deanline`, `RA2096`, …) | **NOT in PumpConfiguration_Logic.** Series×Size applicability is UNIQUE to the Data Sheet → **Data Sheet is authoritative for Series×Size applicability.** |
| **Motor Constraints** | 95 × 24 | Frame Size table (Power/Speed × RPM → NEMA frame) + Frequency table | **NOT in PumpConfiguration_Logic.** Motor frame/frequency sizing → **Data Sheet (and Copy of Motor Numbering.xlsm) authoritative for motor sizing.** |
| **Logic** | 60 × 70 | Column-per-field option lists (30 fields: Series, Size, Pump Material, Shaft Config/Material, Casing*, Seal*, Impeller*, Baseplate, Hydropads, …) | **SUBSET** of Config Options (30 vs 74 fields). Overlaps; **superseded by** PumpConfiguration_Logic Config Options. |
| **Config Info** | 104 × 183 | Paired field/spacer option-domain dictionary (Pump Series, Size, Pump Material, Shaft Config/Material, Casing*, Shaft Sleeve, Casing Wear Ring/Mounting, Hardware, …) | **OVERLAPS** Config Options; **superseded by** PumpConfiguration_Logic Config Options (which is broader + is the designated authority). Retain only for cross-checking option spellings. |
| **User Selections** | 100 × 99 | UI input cells / selection scratch | Not a constraint source. |

## 3. Authority mapping (the rule going forward)

| Concern | Authoritative source |
|---------|----------------------|
| Configurable **fields** + **option domains** | **PumpConfiguration_Logic.xlsm → Config Options** (74 fields) |
| **Field codependencies / feasibility** (which value-combinations are allowed) | **PumpConfiguration_Logic.xlsm → Codependencies** (47 allow-list tables, 726 rows) |
| **Series × Size** applicability | **Dean Data Sheet Rev 2 → Constraints** sheet (not in the logic workbook) |
| **Motor frame / frequency** sizing | **Dean Data Sheet Rev 2 → Motor Constraints** + **Copy of Motor Numbering.xlsm** |
| Part-number / SKU construction | Dean Data Sheet Rev 2 (Smart Number + Module2/Module4 VBA → SQL) — D110/D130 |
| Pricing / adders | Dean Pricing Matrix.xlsx + Price Options — D120 |

**Precedence rule:** for any field/option or codependency, `PumpConfiguration_Logic`
wins over the Data Sheet `Logic` / `Config Info` sheets. The Data Sheet remains
authoritative ONLY for Series×Size applicability and motor sizing, which the
logic workbook does not contain. Where the two disagree on an option spelling,
`PumpConfiguration_Logic` is canonical and the difference is logged in
DEAN_CONFLICT_REGISTER.

## 4. Compile path (D110 preview — not executed here)

The authoritative model maps cleanly onto the Fybroc constraint infrastructure:

- Config Options (74 fields + domains) → `cfg.SeriesFieldOption`-equivalent for
  the Dean family.
- Codependencies (47 allow-list tables) → `cfg.FeasibleConstraint`-equivalent
  rows (TableName per sub-table, Option1..Option4 legs, `Allowed`, series scope),
  bridged through a `cfg.ConstraintFieldMap`-equivalent (Dean field label → SFO
  code). The 4-field quad (Seal Option × Gland Type × Flush Plan × Barrier Plan)
  needs a 4-leg row shape (Fybroc's is 3-leg) — a schema note for D110.
- Enforcement reuses the **governed-domain allow-list** semantics already proven
  for Fybroc (a table only restricts values it names).
- Series×Size applicability + motor sizing loaded separately from the Data Sheet.

## 5. Exit-gate contribution

Every constraint-bearing artifact in both workbooks is now classified: VBA
audited (no hidden constraint code), PumpConfiguration_Logic established as the
complete field-constraint authority, and the Data Sheet's constraint sheets each
mapped as either SUBSET/superseded or UNIQUE (Series×Size, motor sizing). No
Dean constraint content remains structurally unexplained.

# D100 — Dean Source Inventory

**Date:** 2026-08-24  
**Milestone:** D100 — Dean Source Reconciliation  

---

## Workbook Inventory

### 1. Dean Data Sheet Rev 2.xlsm (PRIMARY)
The main Dean configuration workbook — contains everything: data sheet, Smart Number (Part Number construction), numbering tables, constraints, logic, pricing, seals, motors.

| Sheet | Rows | Cols | Purpose |
|-------|------|------|---------|
| Data Sheet | 113 | 26 | User-facing pump data sheet |
| Formal Quote | 98 | 19 | Quote generation template |
| Smart Number | 43 | 37 | Part Number construction (like Fybroc V6) |
| Wet End Numbering | 146,460 | 41 | Wet-end component combination table |
| Power End Numbering | 475 | 27 | Power-end component combinations |
| Constraints | 2,892 | 222 | Full constraint matrix |
| Config Info | 104 | 183 | Configuration field definitions |
| Logic | 60 | 70 | Configuration logic rules |
| Baseplate Numbering | 1,552 | 34 | Baseplate combination table |
| Motor Numbering | 114,100 | 54 | Motor combination table |
| User Selections | 100 | 99 | User input cells and options |
| Test and Doc Numbering | 500,016 | 31 | Testing/documentation combinations |
| Motor Constraints | 95 | 24 | Motor-specific constraints |
| External References | 663,757 | 37 | External data references |
| Reference Data | 200 | 3 | Lookup reference data |
| Seal Descriptions | 29 | 12 | Seal type descriptions |
| Misc Numbering | 209 | 16 | Miscellaneous numbering |
| Motors | 178 | 22 | Motor catalog |
| Formal Quote (OEM) | 98 | 18 | OEM quote variant |
| Seal Options | 193 | 200 | Seal configuration options |
| Seal Pricing | 48 | 192 | Seal pricing matrix |
| Pricing | 1,070 | 149 | Full pricing tables |

### 2. PumpConfiguration_Logic.xlsm
Configuration logic and dependency rules in a separate workbook.

| Sheet | Rows | Cols | Purpose |
|-------|------|------|---------|
| Pump Options | 233 | 599 | All pump option combinations/applicability |
| Price Options | 225 | 686 | Pricing option applicability |
| Codependencies | 171 | 50 | Field interdependency rules |
| Config Options | 103 | 148 | Configuration option definitions |

### 3. Copy of Motor Numbering.xlsm
Motor-specific configuration and pricing.

| Sheet | Rows | Cols | Purpose |
|-------|------|------|---------|
| Constraints | 112 | 15 | Motor constraints |
| Numbering | 6,646 | 16 | Motor part number combinations |
| Pricing | 59,675 | 20 | Motor pricing (large matrix) |

### 4. Dean Pricing Matrix.xlsx
Dedicated pricing workbook.

| Sheet | Rows | Cols | Purpose |
|-------|------|------|---------|
| Std Options | 495 | 163 | Standard option pricing |
| COUPLINGS | 686 | 6 | Coupling pricing |
| Base Plates | 1,071 | 26 | Baseplate pricing |
| Shaft Configuration | 676 | 9 | Shaft configuration pricing |
| Sheet2 | 105 | 345 | Additional pricing data |

---

## Structural Comparison to Fybroc

| Dimension | Fybroc | Dean |
|-----------|--------|------|
| Primary workbook | Nomenclature_V6.xlsm | Dean Data Sheet Rev 2.xlsm |
| Configuration model | Rev0.3 (14 sheets) | Data Sheet Rev 2 (22 sheets) |
| Price Estimator | Price Estimator-Fybroc.xlsm | Dean Pricing Matrix.xlsx |
| Combination table size | 138,240 (Pump Options H) | 146,460 (Wet End) + 114,100 (Motor) |
| Constraint sheets | 34 fields, 20 feasible tables | 2,892 rows x 222 cols |
| Separate logic workbook | N/A | PumpConfiguration_Logic.xlsm |
| Motor numbering | In Nomenclature V6 (702 combos) | Dedicated workbook (6,646 + 59,675 pricing rows) |

---

## Key Observations

1. **Dean is significantly larger** — 146K wet-end combinations, 114K motor numbering, 500K test/doc numbering
2. **Dean has separate logic workbook** — PumpConfiguration_Logic.xlsm adds codependency rules not in the main workbook
3. **Motor pricing is massive** — 59,675 rows in dedicated motor numbering workbook
4. **Smart Number exists** — same pattern as Fybroc V6 (row 43 x col 37)
5. **Dean uses A-number → D-number conversion** — per roadmap D130 specification

---

## Source Lineage

| Workbook | Role | Precedence |
|----------|------|------------|
| Dean Data Sheet Rev 2.xlsm | PRIMARY — configuration, constraints, numbering, pricing | Authoritative |
| PumpConfiguration_Logic.xlsm | Configuration logic and codependencies | Supplements primary |
| Copy of Motor Numbering.xlsm | Motor configuration and pricing | Authoritative for motors |
| Dean Pricing Matrix.xlsx | Pricing tables (std options, couplings, baseplates, shaft) | Authoritative for pricing |

---

## Next Steps (D110)

1. Compile Dean Smart Number sheet (Part Number construction flow)
2. Compile User Selections (configuration field definitions)
3. Compile Constraints sheet (2,892 x 222 constraint matrix)
4. Compile Codependencies from PumpConfiguration_Logic
5. Cross-reference with existing SQL Dean metadata (from prior M023 work)

# D120 — Dean Pricing & Adders

**Date:** 2026-08-24  
**Milestone:** D120  

---

## Pricing Sources

### 1. Dean Pricing Matrix.xlsx (PRIMARY PRICING)

| Sheet | Rows | Key Structure |
|-------|------|---------------|
| Std Options | 495 x 163 | Group/Style/Series/Size/Material → Pump List Price |
| COUPLINGS | 686 x 6 | Series/Frame → Coupling type + List price |
| Base Plates | 1,071 x 26 | Series/Frame Type/Frame Size/Baseplate Type/Material → List + options |
| Shaft Configuration | 676 x 9 | Shaft config pricing per series/size |
| Sheet2 | 105 x 345 | Additional pricing data |

### 2. Dean Data Sheet Rev 2.xlsm Pricing Sheets

| Sheet | Rows | Key Structure |
|-------|------|---------------|
| Pricing | 1,070 x 149 | Full pricing tables (multiple blocks) |
| Seal Pricing | 48 x 192 | Seal pricing matrix (seal type x series) |
| Motors (catalog) | 178 x 22 | Motor options and pricing |

### 3. Copy of Motor Numbering.xlsm

| Sheet | Rows | Key Structure |
|-------|------|---------------|
| Pricing | 59,675 x 20 | Motor pricing (HP x RPM x Frame x Voltage x Enclosure) |

---

## Pricing Components Identified

1. **Base Pump Price** — Std Options: Series + Size + Material → List Price
2. **Coupling** — Series + Frame → Coupling type + price (686 combinations)
3. **Baseplate** — Series + Frame Type + Frame Size + Baseplate Type → price (1,071 rows)
4. **Shaft Configuration** — per series/size pricing (676 rows)
5. **Seal Pricing** — Seal type x configuration matrix (48 x 192)
6. **Motor Pricing** — HP x RPM x Frame x Voltage x Enclosure (59,675 rows)
7. **Standard Options Adders** — embedded in Std Options sheet (163 columns of option pricing)

---

## Comparison to Fybroc Pricing

| Component | Fybroc Source | Dean Source |
|-----------|--------------|-------------|
| Base pump | Pricebook (15 blocks) | Std Options (495 rows) |
| Coupling | Coupling sheet (248 rows) | COUPLINGS (686 rows) |
| Baseplate | Baseplate sheet (367 rows) | Base Plates (1,071 rows) |
| Seal | Pricebook seal block (25 rows) | Seal Pricing (48 x 192) |
| Motor | M-$ (266 rows) | Motor Numbering Pricing (59,675 rows) |
| Adders | Adders (623 rows, 14 sections) | Embedded in Std Options columns |
| Shaft | N/A (Fybroc uses material adders) | Shaft Configuration (676 rows) |

Dean has significantly more motor pricing granularity (59K vs 266 rows) and adds explicit shaft configuration pricing.

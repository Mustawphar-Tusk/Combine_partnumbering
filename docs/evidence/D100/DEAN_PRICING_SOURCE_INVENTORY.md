# D100 — Dean Pricing Source Inventory

**Date:** 2026-08-26
**Scope:** D100 inventories the pricing SOURCES (location, key, applicability,
precedence). Reconciling amounts/formulas and building the pricing publication is
**D120** — not done here. Analysis/inventory only.

---

## 1. Pricing sources overview

| Source | Sheet(s) | Keyed by | Covers |
|--------|----------|----------|--------|
| **Dean Pricing Matrix.xlsx** | Std Options, COUPLINGS, Base Plates, Shaft Configuration, Sheet2 | Series / Frame / Size / Material | Base pump + std options, couplings, baseplates, shaft config, wet-end |
| **PumpConfiguration_Logic.xlsm** | Price Options | A Number / Series / Size | Base list price per (size, config bundle) + per-material adders — parallels the constraint workbook's Pump Options matrix |
| **Copy of Motor Numbering.xlsm** | Pricing (59,675 rows) | Motor permutation (frame, speed, power, voltage, phase/freq, poles, enclosure, efficiency, brand) | Motor pricing |
| **Dean Data Sheet Rev 2.xlsm** | Pricing (1,070 × 149), Seal Pricing (48 × 192), Seal Options (193 × 200) | (workbook-internal) | Full pricing tables + seal pricing (candidate/legacy — reconcile vs Matrix in D120) |

## 2. Dean Pricing Matrix.xlsx (primary pricing workbook)

| Sheet | Dims | Key columns | Notes |
|-------|------|-------------|-------|
| **Std Options** | 495 × 163 | Group, Style, Series, Size, Material, **Pump List Price**, then per-Casing-Material columns (None, (22) Ductile Iron, (40) Cast Steel, (50) 316 S/S, …) | Base pump list price + material adder matrix (wide, 163 cols) |
| **COUPLINGS** | 686 × 6 | Series, Frame, Coupling, **List** | Coupling list price by series+frame+coupling |
| **Base Plates** | 1071 × 26 | Series, Frame Type, Frame Size, Baseplate Type, Baseplate Material, **List**, + option adder columns (Alignment Lugs, Lifting Lugs, …) | Baseplate list + lug/option adders (X-marked applicability) |
| **Shaft Configuration** | 676 × 9 | Series, Material, Shaft Material, then per-Shaft-Configuration columns (Sleeved, Sleeveless, Motor, Motor w/Shaft Extension, No Keyway, Custom) | Shaft config pricing matrix |
| **Sheet2** | 105 × 345 | "Pump Wet-End" (wide) | Wet-end pricing detail — classify in D120 |

## 3. PumpConfiguration_Logic — Price Options

- Dims 225 × 686. Row-per (`A Number`, `Series`, `Size`), e.g. `A779 / RA2096 /
  1x1.5x6`.
- Column groups mirror the constraint workbook's Pump Options: **Pump
  Configuration** bundle columns (Pump Only, Pump and Baseplate, …) carry the
  **base list price** (e.g. Pump Only = `6790`); **Pump Material** columns carry
  per-material **adders** (Custom = 0); **Casing Material** columns follow.
- This is the price twin of the Pump Options applicability matrix → base price by
  (A Number, size, bundle) + material/casing adders.

## 4. Copy of Motor Numbering — Pricing

- 59,675 rows keyed on the full motor permutation: Permutation, Motor, Motor
  Control, Frame Size, Rated Speed, Rated Power, Voltage, Phase/Frequency, Num
  Poles, Enclosure, Efficiency, Brand.
- Motor pricing is a large per-permutation lookup (the Dean analogue of Fybroc's
  multi-condition motor pricing). The workbook also has a `Constraints` sheet
  (Frame Size table: Power/Speed × RPM × Size/Style TC/TCZ/TS/…) driving motor
  frame sizing (see DEAN_CONSTRAINT_RECONCILIATION — motor sizing authority).

## 5. Dean Data Sheet Rev 2 — Pricing / Seal Pricing (candidate)

- `Pricing` (1,070 × 149) and `Seal Pricing` (48 × 192) + `Seal Options`
  (193 × 200) inside the 80 MB Data Sheet. These overlap the Matrix and must be
  reconciled for precedence in D120 (which is authoritative where they differ).

## 6. Proposed precedence (to confirm in D120)

1. **Dean Pricing Matrix.xlsx** = primary authoritative pricing (dedicated
   pricing workbook), for base pump, couplings, baseplates, shaft config.
2. **Copy of Motor Numbering.xlsm → Pricing** = authoritative for motor pricing.
3. **PumpConfiguration_Logic → Price Options** = cross-check / A-Number-keyed base
   price (same structure as the constraint workbook — useful to tie price to the
   A-number identity).
4. **Dean Data Sheet Rev 2 → Pricing/Seal Pricing** = reconcile; treat as
   candidate/legacy unless D120 confirms it is newer than the Matrix.

## 7. Each price/adder must ultimately identify (D120 requirement)

source workbook · worksheet · range/cell/table · applicability (series/size/
material/frame) · condition · precedence · amount or formula · publication
version. This inventory locates each source; D120 will extract and reconcile the
values.

## 8. Exit-gate contribution

All Dean pricing sources are located and structurally classified (5 workbooks/
sheets, keys, coverage, proposed precedence). No pricing source remains
unidentified. Value-level reconciliation is deferred to D120 per roadmap.

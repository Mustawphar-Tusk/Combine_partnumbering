# Dean Data Sheet Rev 2 — VBA/Macro Logic (authoritative behavioral reference)

**Date:** 2026-08-26
**Source:** `docs/evidence/D100/vba/Dean_Data_Sheet_Rev2/*` (extracted VBA).
**Purpose:** map how Dean configuration, constraints, numbering, and pricing tie
together per the workbook macros, to guide authoritative logic over implementation
(D110 config, D120 pricing, D130 identifier). This is a reading of the macros — no
implementation claims.

---

## 1. Module inventory

| Module | Role |
|--------|------|
| `Module1` | Globals + field/range maps; Access DB search/write helpers; `getSealOptions` |
| `Module2` | **Numbering engine** — enumerates valid combinations per segment into numbering tables |
| `Module3` | SQL connection test (scaffolding) |
| `Module4` | `GeneratePartNumber` via SQL stored proc `sp_GeneratePartNumber` (scaffolding) |
| `Sheet1` (Data Sheet) | **Configuration interaction logic** — the authoritative applicability cascade + STD defaults + config identity |
| `Sheet2` (Formal Quote) | Quote persistence (Access DB) + PDF render; NOT price computation |
| `MTR_Selection` | Motor sub-option userform (Casing/Impeller/Backhead/Shaft/Sleeve) |
| `ThisWorkbook` | empty `Workbook_Open` |

## 2. Canonical configuration field order (Module1 `headers`)

74 configuration fields (then quote lines). Order: Pump Spec Number, Part Number,
Revision, Date Created, By, **Pump Configuration**, Flow, Fluid, Fluid Temp, NPSHA,
TDH, Specific Gravity, Viscosity, **Series, Pump Size, Pump Material, Casing
Material, Casing Drain, Casing Taps, Casing Gasket, Flange Configuration, Spot
Facing, Casing Wear Rings, Tack weld Wear Rings, Casing Mounting, Seal Chamber
Config, Shipping Gasket, Casing Heat Jacket, Impeller Trim, Impeller Balance,
Impeller Material, Imp Wear Rings Material, Shaft Configuration, Shaft Material,
Lubrication Options, Oil Seal, Oiler Options, Sight Glass, Bearing Frame Cooling,
Magnetic Drain, Expansion Chamber, Coupling Type, Coupling Guard, Seal Option, Seal
Mfr, Seal Configuration, Seal Type, Gland Type, Gland Gasket, Shaft Sleeve
Material, Inboard/Outboard face materials + elastomers, Hydropads, Pumping Ring,
Throttle Bushing, Min Flo Bushing, Lantern Ring, Flush Plan(+Code), Barrier
Plan(+Code+Extras), Cooling Plan(+Piping+Extras), Motor Options, Motor Control,
Power HP, Speed, Voltage, Phase/Hertz, Frame, Enclosure, Efficiency, C Face Adapter
Option, Manufacturer, Custom Option 1-3, Drip Cover, Conduit box, Baseplate Type,
Drip Pan, Alignment lugs, Lifting lugs, Levelling Screws, Grounding Lug, Grout
Hole, Isolation Pads, Stilts, Performance Testing, Hydro Test, Vibration, Sound
Level, General Inspection, Documentation 1-4, Paint, Coating, Auxillary Nameplate,
Crating** + quote lines. Matches the D110 field set.

## 3. AUTHORITATIVE applicability cascade — `Sheet1.Worksheet_Change` (Data Sheet!D8)

Selecting **Pump Configuration** (cell D8) gates whether Baseplate, Coupling, and
Motor are part of the pump. This is the top-level applicability rule and is
directly relevant to D120 pricing (a component is only priced when the
configuration includes it; otherwise NONE / "supplied by others" → no charge):

| Pump Configuration | Baseplate (D38) | Coupling (D49) | Motor (G47) |
|--------------------|-----------------|----------------|-------------|
| Pump Only | NONE + options N/A | NONE | Supplied by others; motor opts cleared |
| Pump and Baseplate | (kept) | NONE | Supplied by others; motor opts cleared |
| Pump, Baseplate, and Coupling | (kept) | (kept) | Supplied by others; motor opts cleared |
| Pump and Motor | NONE + options N/A | NONE | (kept) |
| Pump, Baseplate, and Motor | (kept) | NONE | (kept) |
| Pump, Baseplate, Coupling and Motor | (kept) | (kept) | (kept) |
| Pump and Coupling | NONE + options N/A | (kept) | Supplied by others; motor opts cleared |

Secondary cascades:
- **Baseplate D38 = "NONE"** → baseplate options (`baseOptRanges` G48:H55) set N/A.
- **Motor G46 = "No Motor"** → motor options (`motorOptRanges` G31:H45) set N/A.
- **G62:G65 contains "MTR"** → opens `MTR_Selection` userform to pick motor
  sub-scope (Casing/Impeller/Backhead/Shaft/Sleeve).

## 4. STANDARD defaults — `Sheet1.SetDefaultOptions_Click`

STD defaults are pulled from a **"Standard Confs"** table (Access DB) keyed by
**Series + Pump Size** — populates the whole Data Sheet + Formal Quote from a
stored standard configuration. This corroborates D110's STD/X applicability being
per (series, size): the standard row IS the STD selection set for that model.

## 5. Configuration identity — `Sheet1.SavePumpConfiguration_Click` / `Sheet2.SaveToDatabase_Click`

- Config identity searched in **"Custom Confs"** (Access) on the FULL pump field
  set (headers 12..end = Series..Crating). An exact match restores the existing
  Part Number; else a new spec number `Left(SpecNo,4) & "_NNNNNN"` is minted.
- Part-number generation also has a SQL path: `Module4.GeneratePartNumber` →
  `sp_GeneratePartNumber(@config_id)` (D130 territory).

## 6. NUMBERING ENGINE — `Module2` (segment enumeration, authoritative structure)

Each segment's valid-combination table is generated by iterating the per-series
valid options from the **`Constraints`** sheet (`B4:B39` = 36 series; each segment
has an option-range block) and enumerating the cross product, applying segment
"unique checks", then base-36 encoding a sequential index as the segment code:

| Sub | Target sheet / table | Segment | Notable rule |
|-----|----------------------|---------|--------------|
| `numberWetEnd` | Wet End Numbering / Table100 | Wet end | 12 option lists; if Casing (b)="NONE" → downstream c..f="N/A"; excludes "Custom" |
| `numberImpellerOpts` | Wet End Numbering / Table106 | Impeller | seeds "NONE*N/A*N/A*N/A"; balance-holes list {Not Required, Required}; skips a="NONE" |
| `numberPowerEnd` | Power End Numbering / Table101 | Power end | 11 option lists; excludes "Custom"; cap 1000 |
| `numberBaseplates` | Baseplate Numbering | Baseplate | (commented-out variant) if Baseplate (a)="NONE" → downstream N/A |
| `numberTesting` | Test and Doc Numbering / Table108 | Testing | cross of Performance×Hydro×GenInspection×Vibration×Sound; base-36(2) |
| `numberDocumentation` | Test and Doc Numbering / Table109 | Documentation | 4 doc picks, no repeats (except NONE); base-36(5) |
| `numberAdditionalOptions` | Misc Numbering / Table105 | Add'l opts | ShippingGasket×AuxNameplate×Crating×Paint×Coating; excludes "Custom"; base-36(2) |
| `numberCoolingPlans` | Misc Numbering / Table104 | Cooling plan | Plan×Piping×Extras; base-36(2) |
| `numberMotors` | Motor Numbering / Table110 | Motor | from `Motor Constraints` Motor_Frame_Ratings_Table: frame ratings × frame styles × voltage/freq/poles × drive/enclosure/brand; base-36(3) |

Key point: **the `Constraints` sheet is the authoritative per-series valid-option
source that feeds numbering** — the Dean analogue of the applicability grid.
`NONE` on a controlling field forces dependents to `N/A` (structural dependency),
and `Custom` combinations are excluded from enumerated numbering (custom = manual).
Segment codes are base-36 encodings of the row index (identifier authority, D130).

## 7. Pricing (how it ties in)

- Sheet2 does NOT compute price in VBA — pricing is driven by worksheet formulas
  and Query connections ("Query - User Selections", "Query - Seal Options").
- **Seal** is resolved via `Module1.getSealOptions` against an external Access DB
  ("Seal Numbering.accdb" → "Combined Table") keyed on Seal Type, Manufacturer,
  faces, elastomers, hydropads, pumping ring, throttle bushing, min-flo bushing,
  lantern ring, seal chamber config, gland style/gasket, sleeve material — this is
  the seal numbering/pricing authority (why the Matrix marks seal "No Seal Only").
- **Baseplate** config fields = Baseplate Type + Drip Pan + the six lug flags
  (from `Baseplate Numbering` C2:K + Data Sheet). Confirms D120 finding: baseplate
  price is driven by Baseplate Type + Drip Pan (+ mounting), decomposed from the
  Matrix "Baseplate Material" dimension. Lug flags are applicability (Required/Not
  Required), matching the Matrix lug columns being 'X' markers, not dollars.

## 8. Implications for implementation

1. **D110 applicability**: Pump Configuration (D8) is the top-level gate for
   Baseplate/Coupling/Motor presence. If not already enforced, the config model
   should reflect these seven cascade rules (§3).
2. **D120 pricing**: price Baseplate/Coupling/Motor only when the Pump
   Configuration includes them; Baseplate price keyed by Type + Drip Pan (+
   mounting); Seal price comes from the seal Access DB authority (Matrix is "No
   Seal"); lugs are no-charge applicability.
3. **D130 identifier**: segment codes are base-36 row indices over the enumerated
   numbering tables (Module2); part number assembled from segment codes; SQL
   `sp_GeneratePartNumber` is the intended SQL path.
4. **Constraints sheet** is the per-series valid-option authority feeding
   numbering; `NONE`→`N/A` dependency and `Custom` exclusion are structural rules.

---

## 9. WORKBOOK FORMULAS (authoritative computation, extracted 2026-08-26)

Extracted every formula from Dean Data Sheet Rev 2 (14 sheets w/ formulas) +
PumpConfiguration_Logic (Pump Options, Price Options). Full dump:
`exports/dean_workbook_formulas.json`. The formulas — not just the macros — carry
the authoritative assembly and pricing logic.

### 9.1 Part Number assembly — `Smart Number!B5` (authoritative PN structure, D130)

```
B5 = "D" & C12 & "-" & D12 & "-" & H12 & I12 & "-" & K12 & "-" & O12
        & "-" & Q12 & S12 & U12 & "-" & W12 & X12 & "-" & Z12 & AB12 & "-" & AD12
J5 = "-" & AH12 & AJ12        (Testing & Documentation suffix)
```
Dean PN = `D<A#>-<WetEnd>-<Trim><ImpOpts>-<PowerEnd>-<Seal>-<Flush><Barrier><Cooling>-<Frame><Baseplate>-<AddlOpts>-<Testing><Doc>`.
Each segment code is a `VLOOKUP` / `BASE(MATCH(...),36,n)` into the Module2
numbering tables. Notable segment formulas:
- **Trim `H12`** = `VLOOKUP(inch, B31:C43) & VLOOKUP(decimal, E34:F41)` — inch-letter +
  decimal-letter encoding (same scheme as Fybroc).
- **Seal `O12`** = `IF('Data Sheet'!D49<>"Included","00000","TBD__")` — seal segment is
  `00000` unless seal Included → `TBD__` (seal resolved via the seal Access DB).
- **Motor frame `W12`** = `IF((Y13<>"NONE")+(M23<>"NONE")+(W13<>0), BASE(MATCH(frame,
  Table2486),36,2), "00")` — **motor frame code is `00` when there is no motor** →
  confirms Pump-Configuration gating flows into the identifier.
- **`S12`** = `VLOOKUP(T14, Table76, 4)` → base-36 flush/barrier/cooling code.
- The `F13:AK25` block maps Smart Number inputs to `'Data Sheet'` cells (the
  selection → segment source map).

### 9.2 Quote pricing math — `Formal Quote` (authoritative D120 composition)

Quote lines occupy rows 20-48; each line:
```
I<r> = G<r> * (1 - H<r>)      Net unit price = List * (1 - Discount)
J<r> = F<r> * I<r>            Extended       = Qty * Net
I49  = SUM(J20:J48)           Quote total    = Σ extended
```
So the workbook composition is **per-line `List × (1 − Discount) × Qty`, summed**.
The **List price (col G) is sourced from the pricebook (Matrix)** — the sheet does
NOT compute component list prices by formula; it computes net/extended/total.
Discount is a per-line input.

Line → component (col C description built from Data Sheet):
- C20 Series, C21 Size, C22 Pump Material, C23 Bearing Frame Cooling
- **C24 Seal** = `IF(D51="Packing", TEXTJOIN(D52,D66), TEXTJOIN(D49,D50,D52,D56,D57,D58))`;
  `N24 = VLOOKUP(D82,'Seal Descriptions'!B3:D29,3)` (seal description/authority)
- C25 outboard seal faces/elastomers, C26/C27 seal sub-items
- C29 **Motor** (`'Data Sheet'!G47`)
- **C30 Baseplate** = `TEXTJOIN(", ", IF(G48∉{Steel,Stainless},"",G48&" Drip Pan"),
  IF(G49="Required",F49,""), … IF(G55="Required",F55,""))` — baseplate line =
  **Drip Pan material + each "Required" lug**. Confirms: baseplate priced by Type +
  Drip Pan; **lugs are descriptive line items, not separate priced adders** (matches
  the Matrix lug columns being 'X' applicability markers, not dollars).
- C32 Casing Drain, C34 coupling, C35 coupling/mounting, C36 testing, C37 docs,
  C38-C47 additional options (`Logic!AZ2..AZ11`).

### 9.3 Config→description lookups

- **Data Sheet** `G15/G16/G20/G21` = `VLOOKUP(H14/H19, 'Config Info'!FA/FK ranges)` —
  selection codes resolve to descriptions via the `Config Info` sheet.
- **Logic** sheet derives conditional seal/hardware descriptions (e.g. `Z1`,`BB2:BB4`:
  "Type 9" seals expose Inboard/Outboard Hardware vs Elastomers differently;
  Throttle Bushing / Min-Flo rendered only when not "Not Required").
- **Seal Descriptions** builds `code = description` strings (`J3 = G3&" = "&H3`).
- **Constraints / *Numbering* header formulas** (`=Table..[[#Headers],[Field]]`) just
  label the per-field option-block columns feeding Module2 enumeration.

### 9.4 D120 pricing implications (formula-confirmed)

1. **Quote math = List × (1 − Discount) × Qty, summed.** Our resolve/quote total
   should compose per-line net×qty; List comes from the Matrix pricebook. (Discount
   is a sales input, default 0 for a list-price quote.)
2. **Baseplate**: priced by Baseplate Type + Drip Pan (Steel/Stainless); lugs are
   descriptive, no separate adder — matches the Matrix. Resolves the baseplate
   keying question pending engineering (Drip Pan is the disambiguator).
3. **Seal**: not priced by the Matrix nor by workbook formula — resolved via the
   external seal Access DB. D120 seal price = Rev2 fallback / seal authority, else
   C/F.
4. **Motor / Coupling / Baseplate presence** is gated by Pump Configuration (§3),
   and that gating even flows into the PN (motor frame `00` when no motor).

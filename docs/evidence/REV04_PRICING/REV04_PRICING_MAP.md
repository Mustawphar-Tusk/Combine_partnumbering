# Rev0.4 Fybroc Pricing — source map (extractor spec)

Source: `workbooks/Fybroc/Fybroc Configuration Rev0.4.xlsx` (read-only; authoritative
pricing per engineering, replacing `Price Estimator-Fybroc.xlsm`).

## Layout convention (the generic block pattern)

The pricing sheets store many tables **side by side as column blocks**, not as named
Excel Tables. Each block:
- **row 3**: a description ("1500 - Adder for Sleeve", "Mechanical Seal Pricing", ...)
- **row 5**: headers, always shaped `[Series] , Alt Size , <one or more option fields> , Price`
  (a few blocks omit `Series`; some price columns are named e.g. `Adder`, `VR-1 Base Price`)
- **row 6+**: data rows
- `Price` value `C/F` / `c/f` => call_for_price (no amount).

A generic extractor scans row 5 for header groups (contiguous columns, gap splits a
block), reads the row-3 description for the block, treats `Series`/`Alt Size` as keys,
every other non-Price header as an **option condition field**, and `Price` as the amount.

## Component mapping (block description -> ComponentCode + condition fields)

### 1500 Pricing (horizontal; 24 blocks; series column present)

| Block cols | Description | ComponentCode | Condition fields (besides Series/Alt Size) |
|---|---|---|---|
| B..E | Base Price (by size) | BASE_PUMP | Pump Material |
| G..I | VR-1 Base Price (dup of base for VR-1) | (skip; duplicate of BASE_PUMP) | — |
| K..N | Adder for pump material | PUMP_MATERIAL_ADDER | Pump Material |
| P..R | Adder for Shaft Material | SHAFT_MATERIAL | Shaft Material |
| U..X | Adder for Shaft Sleeve | SLEEVE | Sleeve |
| Z..AC | Adder for Gland Hardware | GLAND_HARDWARE | Gland Hardware |
| AE..AH | Adder for Power Frame Hardware | POWER_FRAME_HARDWARE | Power Frame Hardware |
| AJ..AM | Adder for Bearing Option | BEARING_OPTION | Bearing Option |
| AO..AR | Adder for Casing Hardware | CASING_HARDWARE | Casing Hardware |
| AT..AW | Coupling Guard Pricing | COUPLING_GUARD | Coupling Guard |
| AY..BC | Baseplate pricing | BASEPLATE | Frame Size, Baseplate Option |
| BE..BH | Adder for Baseplate Hardware | BASEPLATE_HARDWARE | Baseplate Hardware |
| BJ..BP | Mechanical Seal Pricing | SEAL | Seal Mfg, Seal Option, Seal Type, Seal Materials, Seal Elastomers |
| BR..BW | Coupling Pricing | COUPLING | F_MotorHpRpm, Frame Size, Coupling Option |
| BY..CB | Adder for Flange Type | FLANGE_TYPE | Flange Type |
| CD..CG | Adder for Cyclone Separator | CYCLONE_SEPARATOR | Cyclone Seperator |
| CI..CL | Flush Pricing | FLUSH | Flush Material, Flush |
| CN..CQ | Adder for Casing Drains | CASING_DRAINS | Casing Drains |
| CS..CV | Adder for Suction and Discharge Taps | SUCTION_DISCHARGE_TAPS | Suction Discharge Taps |
| CX..DA | Adder for Seal Guard | SEAL_GUARD | Seal Guard |
| DC..DF | Adder for Performance Testing | PERFORMANCE_TESTING | Performance Testing |
| DH..DK | Adder for Vibration Testing | VIBRATION_TESTING | Vibration Testing |
| DM..DP | Adder for Sound Level Testing | SOUND_LEVEL_TESTING | (header mislabeled 'Vibration Testing'; treat as Sound Level Testing) |
| DR..DV | Adder for C-Face Adaptor | C_FACE_ADAPTOR | Frame Size, C-Face Adaptor |

### 5500 Pricing (vertical; 13 blocks)

| Block cols | Description | ComponentCode | Condition fields |
|---|---|---|---|
| B..D | Size/Setting index (helper) | (skip; helper, not a price) | — |
| F..L | Base Price (size + setting/length) | BASE_PUMP | Length, Setting, Pump Material (+ Price conversion helper) |
| N..Q | Adder for Shaft Sleeve | SLEEVE | Sleeve |
| S..Z | Adder for Shaft and Shaft Sleeve | SHAFT_SLEEVE | Setting, Shaft Material, Sleeve (Shaft Adder/Sleeve Adder helpers) |
| AB..AG | Adder for Tailpipe | TAILPIPE | Pump Material, Wetted Hardware, Tailpipe Length |
| AI..AN | Coupling Adder | COUPLING | F_MotorHpRpm, F_Frame_Size, F_Coupling_Option |
| AP..AS | Flush Pricing | FLUSH | Flush Material, Flush |
| AU..AX | Adder for Performance Testing | PERFORMANCE_TESTING | Performance Testing |
| AZ..BC | Adder for Vibration Testing | VIBRATION_TESTING | Vibration Testing |
| BE..BH | Adder for Sound Level Testing | SOUND_LEVEL_TESTING | (header mislabeled 'Vibration Testing') |
| BJ..BM | Adder for Flange Type | FLANGE_TYPE | Flange Type (many c/f) |
| BO..BR | Adder for Custom Mounting Plate | MOUNTING_PLATE | Mounting Plate Option |
| BT..BY | Adder for Wetted Hardware | WETTED_HARDWARE | Wetted Hardware, Shaft Wetted Hardware, Wetted Hardware Selection |

### All Series Pricing (family-wide adders; 3 blocks; no Series column)

| Block cols | Description | ComponentCode | Condition fields |
|---|---|---|---|
| B..D | Adder for Pump Elastomers | PUMP_ELASTOMERS | Pump Elastomers |
| F..H | Adder for Hydrotest Certificate | HYDROTEST_CERTIFICATE | Hydrotest Certificate |
| J..L | Adder for Dynamically Balanced Impeller | IMPELLER_BALANCE | Impeller Balance |

### Motor tables (flat) — `1500 Motors` (144,002 rows), `5500 Motors` (150,626 rows)

Header row 2, data from row 3. Flat table (no blocks):
`Motor Enclosure | Motor Efficiency | Motor Voltage | Motor Hertz | Motor Hp |
Motor RPM | Frame Size | Motor Mfg | Shaft Grounding | Paint Upgrade | CPQ Conversion2 |
HpRPM | Price`. ComponentCode = **MOTOR**. Condition fields = the motor selection
columns (enclosure/efficiency/voltage/hertz/hp/rpm/frame/mfg + shaft grounding + paint
upgrade). Many rows are `C/F`. This is large; extraction must stream rows.

### Setting Groups — vertical setting/length groups (helper for 5500 base price keying).

## Phase split

- **Phase A** (adopt Rev0.4 at current granularity): `BASE_PUMP` (1500 B..E base;
  5500 F..L base) + `SEAL` (1500 BJ..BP). Publish a new IsCurrent version; runtime
  already prices these two.
- **Phase B** (full component pricing): all remaining blocks above + MOTOR (flat
  tables) + setting/length; extend the resolve endpoint to price them.

## Notes / hazards

- Header typos in the workbook: the Sound-Level block's option header is mislabeled
  'Vibration Testing' in both 1500 and 5500 — the extractor keys the ComponentCode off
  the **row-3 description**, not the header, so this is handled.
- `G..I` on 1500 duplicates the base price for VR-1 — skip to avoid double-count.
- `B..D` on 5500 and the `Price conversion`/adder-helper columns are keying helpers,
  not priced rows — skip.
- Vocabulary (sizes like `1x1.5x6`, materials like `VR-1`, options) matches the
  runtime's existing LIKE matching; values use underscores in some option fields
  (e.g. `303_SS`, `Not_Supplied_by_Fybroc`) — normalize consistently.
- `C/F`/`c/f` => call_for_price (Amount NULL).

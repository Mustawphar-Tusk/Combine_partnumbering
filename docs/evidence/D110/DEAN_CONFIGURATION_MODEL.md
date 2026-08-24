# D110 — Dean Configuration & Dependency Model

**Date:** 2026-08-24  
**Milestone:** D110  

---

## 1. Configuration Fields (95 total from User Selections)

### Wet End (13 fields)
- Series, Size, Pump Material, Casing Material, Casing Drain, Casing Taps
- Casing Gasket, Flange Configuration, Spot Facing, Casing Wear Rings
- Tack weld Wear Rings, Casing Mounting, Seal Chamber Config, Shipping Gasket, Casing Heat Jacket

### Impeller (6 fields)
- Impeller Range, Impeller Trim, Impeller Balance, Impeller Material
- Imp. Wear Ring Mat., Impeller Balance Holes

### Power Frame (11 fields)
- Shaft Configuration, Shaft Material, Lubrication Options, Oil Seal
- Oiler Options, Sight Glass, Bearing Frame Cooling, Magnetic Drain
- Expansion Chamber, Coupling Type, Coupling Guard

### Seal (20 fields)
- Seal Option, Seal Manufacturer, Seal Configuration, Seal Type
- Gland Type, Gland Gasket, Shaft Sleeve Material
- Inboard Rotating Face, Inboard Stationary Face, Inboard Seal Elastomers
- Outboard Rotating Face, Outboard Stationary Face, Outboard Seal Elastomers
- Hydropads, Pumping Ring, Throttle Bushing, Min Flo Bushing, Lantern Ring
- Flush Plan, Flush Plan Code

### Barrier/Cooling (7 fields)
- Barrier Plan, Barrier Plan Code, Barrier Plan Extras
- Cooling Plan, Cooling Plan Piping, Cooling Plan Extras

### Motor (12 fields)
- Motor Options, Motor Control, Power [HP], Speed, Voltage
- Phase/Hertz, Frame, Enclosure, Efficiency, C Face Adapter Option
- Manufacturer, Custom Option 1/2/3, Drip Cover, Conduit Box

### Baseplate (9 fields)
- Baseplate Type, Drip Pan, Alignment Lugs, Lifting Lugs
- Levelling Screws, Grounding Lug, Grout Hole, Isolation Pads, Stilts

### Testing/Documentation (10 fields)
- Performance Testing, Hydro Test, Vibration, Sound Level
- General Inspection, Documentation 1-4, Paint, Coating
- Auxiliary Nameplate, Crating

---

## 2. Part Number Construction (Smart Number)

Format: `D<A#>-<WetEnd>-<Trim><ImpOpts>-<PowerFrame>-<Seal>-<FlushPlan><BarrierPlan><CoolingPlan>-<Frame><Baseplate>-<Motor><MotorOpts>-<AddlOpts>-<Testing><Documentation>`

Example: `D610-00CA-AB01-ERR-TBD__-07617-0V03L-0KN00-00`

| Segment | Row 12 Code | Fields |
|---------|-------------|--------|
| Brand | D | Always DEAN |
| A# | 610 | Series → A-number (A610 → D610) |
| Wet End Options | 00CA | Material, Casing Mat, Flange, Taps, Drain, Mounting, Gasket, Wear Rings, Spot, Seal Chamber, etc. |
| Impeller Trim | AB | Inch(A=4") + Decimal(B=.125") = 4.125" |
| Impeller Options | 01 | Balance, Material, Wear Rings, Balance Holes |
| Power Frame Options | ERR | Shaft Config, Material, Lubrication, Oil Seal, Oiler, Sight Glass, etc. |
| Seal Options | TBD__ | Full seal configuration (5 chars) |
| Flush Plan | 07 | Flush Plan Number + Letter code |
| Barrier Plan | 6 | Barrier Plan code |
| Cooling Plan | 17 | Cooling Plan + Piping + Extras |
| Frame Size | 0V | Motor frame code |
| Baseplate Options | 03L | Baseplate type + options |
| Motor | 0KN | Motor HP/Speed/Voltage/etc. |
| Motor Options | 00 | Custom options + drip/conduit |
| Additional Options | 00 | Shipping gasket, nameplate, crating, paint, coating |
| Testing | 1Z | Performance + Hydro + Vibration + Sound + General Inspection |
| Documentation | 1IJ4 | Documentation 1-4 codes |

### Trim Encoding (same as Fybroc)
- Inch: 4"=A, 5"=B, ..., 16"=M
- Decimal: .000"=A, .125"=B, .250"=C, ..., .875"=H

---

## 3. Codependencies (from PumpConfiguration_Logic.xlsm)

25 dependency groups identified (paired columns in row 6):

| Source Field | Dependent Field |
|-------------|-----------------|
| Casing Material | Casing Drain |
| Casing Taps | (valid options) |
| Flush Plan | (valid plan numbers) |
| Series | Casing Material |
| Series | Flange Configuration |
| Impeller Material | Impeller Trim |
| Shaft Configuration | Seal Type |
| Series | Shaft Configuration |
| Series | Shaft Material |
| Bearing Lubrication | Bearing Seal |
| Seal Configuration | Seal Type |
| Series | Gland Type |
| Series | Seal Option |
| Gland Type | Seal Configuration |
| Seal Option | Gland Type |
| Seal Option | Flush Plan + Barrier Plan |
| Seal Configuration | Shaft Sleeve Material |
| Pumping Ring | Seal Configuration |
| Cooling Plan | Seal Chamber Config |
| Baseplate Type | Casing Mounting |

---

## 4. Key Differences vs Fybroc

| Dimension | Fybroc | Dean |
|-----------|--------|------|
| Configuration fields | 56 (Selections) | 95 (User Selections) |
| Part Number segments | 13 | 17 |
| Seal fields | 5 | 20 (much more granular) |
| Barrier/Cooling | N/A | 7 dedicated fields |
| Baseplate fields | 2 (Option + Hardware) | 9 (Type + 8 options) |
| Testing fields | 4 | 10 (includes documentation) |
| Trim encoding | Same (Inch + Decimal) | Same (Inch + Decimal) |
| Series numbering | F + direct series code | A# → D# conversion |
| Motor fields | 11 (in Motor Assy) | 12 + custom options |

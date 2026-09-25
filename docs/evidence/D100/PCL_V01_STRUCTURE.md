# PCL v0.1 — Cell-Level Structure Map

**Workbook:** `workbooks/Dean/PumpConfiguration_Logic_0.1.xlsm` (9,561,178 bytes, contains `vbaProject.bin`)
**Purpose:** authoritative source for re-loading the Dean config + identifier numbering into SQL.
**Sheets (14):** Pump Constraints (2), Pump Constraints, Flush_Barrier Plan Constraints, Motor Numbering, Wet End Numbering, Impeller Numbering, Power Frame Numbering, Price Options, Flush Plan Numbering, Barrier Plan Numbering, Cooling Plan Numbering, Baseplate Numbering, Codependencies, Config Options.
**Method:** openpyxl, bulk `iter_rows(values_only=True)` with bounded columns on the large sheets; `data_only=False` used to test code cells for formulas. No workbook or DB was modified. Column indices are **0-based**; the letter is the Excel column.

> Reproduce: `python scripts/_tmp_map_numbering.py`, `python scripts/_tmp_config_constraints.py`, `python scripts/_tmp_find_table.py`, `python scripts/_tmp_motor.py`, `python scripts/_tmp_detail.py` (temp scripts, deleted after use — see end).

---

## 0. Engine confirmation (VBA `Module1.BuildTable` / `Module2.BuildTable`)

Extracted VBA modules: `Module1.bas` (~640 lines), `Module2.bas`, `Module3.bas` (in `output/pcl_v01_vba/`). Confirmed behavior:

- The macro **finds the table by header search**, not fixed cells:
  `Cells.Find("Permutation")` → first table column; `Cells.Find("Alphanumeric Code")` → last column (it then `Offset(0,-1)` so the option block ends one column left of the code); `Cells.Find("Option Ranges")` → the block of Pump-Constraints column-range references used to pull each option's valid values.
- Option values are pulled per pump model from **Pump Constraints** rows (VBA loops `Range("A4:B166")` — rows 4..166, 163 pump models) using the Option-Ranges column pairs.
- **ComboString** = the option-column values, in header (left-to-right) order, joined with `*`; trailing `*` trimmed in a `Do While Right(tempStr,1)="*"` loop; rows whose string contains `"Custom"` are excluded; deduped via a `Scripting.Dictionary`. `dict.Count+1` (sequential) becomes the **Permutation** index and is what maps to the row.
- On write-back: `results(i,1)=dict(k)` (Permutation index), middle columns = the `*`-split tokens, `results(i,last)=k` (the ComboString). `B3` is set to `dict.Count`.

**Loader implication:** locate each table by searching for `Permutation` (col C in this workbook) and `Alphanumeric Code` (the table's last column); read the Permutation column, the option columns between them (in left-to-right order), and the Alphanumeric Code column; the ComboString is the `*`-join of the option columns in that order with trailing `*` trimmed.

### IMPORTANT — two regions per numbering sheet, and materialization state

Each numbering sheet has **two stacked regions**:

1. **Top region (rows 2..~15):** the *option-domain lists* — row 2 holds the option field headers starting at col **D**, and each option column lists its candidate values vertically. To the right is the **Option Ranges** block: row 2 = the literal `Option Ranges` header, row 3 = start-column letters, row 4 = `:endcolumn` letters (e.g. Wet End `P3='N' P4=':V'` → range `N:V` on Pump Constraints). `B3` holds a stale `dict.Count` from a prior run. Cols **A and C are blank** in this region.
2. **Materialized table (header at row 16, or row 26 for Flush):** the header row literally contains `Permutation` (**col C / idx 2**), the option columns (**D onward**), and `Alphanumeric Code` (the last table column). Data starts on the next row.

**Materialization status in v0.1:** the enumerated tables ARE populated (C = sequential Permutation index, code column = zero-padded code) **except**:
- **Barrier Plan Numbering** — header present at row 16 but **no data rows** (0 enumerated rows).
- **Cooling Plan Numbering** — **EMPTY** (`max_row=1, max_col=1`). ⚠️ FLAG.
- **Motor Numbering main code column (O)** — present but **inert**: a single constant value `000` across all 13,260 rows; the meaningful motor code lives in the Frame-Size **sub-table** (S/T/U). ⚠️ FLAG.

The Alphanumeric Code is a **literal zero-padded sequential string** (not a formula, no `BASE(...)`): Permutation *n* → code = zero-padded `n-1` (Wet End perm 1 → `0000`, perm 2 → `0001`; Impeller perm 1 → `00`). No BASE-36/hex encoding is used in the code column itself. (The hex-looking labels `AH`, `AN`, `GN`, `UN`, … are **Option-Ranges column references** into Pump Constraints, not codes.)

---

## Summary table — PN segment → numbering sheet

| Segment | Sheet | Table hdr row | Permutation col | Option cols (left→right) | Code col | Code width | Data rows | Materialized? |
|---|---|---|---|---|---|---|---|---|
| Wet End | Wet End Numbering | 16 | C (2) | D..M (10) | **N** (13) | 4 (`0000`…) | 64,196 (r17–64212) | ✅ |
| Impeller | Impeller Numbering | 16 | C (2) | D..F (3) | **G** (6) | 2 (`00`…) | 24 (r17–40) | ✅ + trim sub-table |
| Power Frame | Power Frame Numbering | 16 | C (2) | D..N (11) | **O** (14) | 4 (`0001`…) | 55,452 (r17–55468) | ✅ |
| Motor | Motor Numbering | 16 | C (2, empty) | D..N (11) | **O** (14) inert `000` | 3 | 13,260 (r17–13276) | ⚠️ main code inert; Frame sub-table live |
| Motor Frame Size | Motor Numbering (sub) | 16 | S (18) | T=Frame Size (19) | **U** (20) | 2 (`01`…) | 13,260 | ✅ |
| Flush Plan | Flush Plan Numbering | 26 | C (2) | D..H (5) | **I** (8) | 2 (`00`…) | 185 (r27–211) | ✅ |
| Barrier Plan | Barrier Plan Numbering | 16 | C (2) | (none populated) | **O** (14) | — | 0 | ⚠️ header only, no data |
| Baseplate | Baseplate Numbering | 16 | C (2) | D..L (9) | **M** (12) | 2 (`00`…) | 1,153 (r17–1169) | ✅ |
| Cooling Plan | Cooling Plan Numbering | — | — | — | — | — | 0 | ⚠️ EMPTY |

---

## 1. Wet End Numbering

- `max_row=64212`, `max_col=25 (Y)`.
- **Top region** row 2 option headers: D=Pump Material, E=Casing Material, F=Casing Drain, G=Casing Taps, H=Casing Gasket, I=Flange Configuration, J=Spot Facing, K=Casing Wear Ring, L=Casing Mounting, M=Seal Chamber Config. Option Ranges header at **P2 (idx 15)**; r3/r4 range refs: `N:V, X:AF, AH:AL, AN:AP, AR:AU, AW:BC, BE:BF, BH:BM, BO:BP, BR:BV` (Pump-Constraints columns).
- **Materialized table:** header **row 16**. Permutation **C (2)**; option cols **D(3)..M(12)** in this order:
  `Pump Material, Casing Material, Casing Drain, Casing Taps, Casing Gasket, Flange Configuration, Spot Facing, Casing Wear Ring, Casing Mounting, Seal Chamber Config`; Alphanumeric Code **N (13)**.
- Data rows **17 → 64212** = **64,196**. Code width min/max/mode = **4/4/4** (`0000`…). Literal (not a formula).
- Samples (combo in option-order → code):
  - perm 1 → `(22) Ductile Iron*Less Casing*Not Required*NPT Discharge*Grafoil*150# Flat*Not Required*NONE*Not Required*NONE` → `0000`
  - perm 2 → `…*Not Required*Foot Mount` → `0001`
  - perm 3 → `…*Required*NONE*Not Required*NONE` → `0002`
- No sub-table.

## 2. Impeller Numbering

- `max_row=40`, `max_col=13 (M)`.
- **Top region** row 2: D=Impeller Balance, E=Impeller Material, F=Impeller Wear Ring Material; Option Ranges at **I2 (8)**, refs `GN:GO, GQ:GX, GZ:HE`.
- **Materialized table:** header **row 16**. Permutation **C (2)**; option cols **D(3)..F(5)** = `Impeller Balance, Impeller Material, Impeller Wear Ring Material`; Alphanumeric Code **G (6)**.
- Data rows **17 → 40** = **24**. Code width **2** (`00`…). Literal.
- Samples: perm 1 → `*NONE` → `00`; perm 2 → `Single Plane*(20) Cast Iron*NONE` → `01`; perm 3 → `Single Plane*(50) 316 S/S*NONE` → `02`.
- **SUB-TABLE — Impeller-Trim decimal/inch → code letter** (cols **J..M**, header **row 16**):
  - J=`Inch`, K=`Code`, L=`Decimal`, M=`Code`.
  - Rows 17+: `4" → A`, `5" → B`, `6" → C`, `7" → D`, `8" → E`, `9" → F`, `10" → G`, `11" → H`, …  and decimal side `.000" → A`, `.125" → B`, `.250" → C`, `.375" → D`, `.500" → E`, `.563" → F`, `.625" → G`, `.750" → H`, …
  - This is the trim map: an inch value maps to one letter, a decimal fraction to a second letter (the two-letter impeller-trim code).

## 3. Power Frame Numbering

- `max_row=55468`, `max_col=27 (AA)`.
- **Top region** row 2: D=Shaft Configuration, E=Shaft Material, F=Bearing Lubrication, G=Bearing Seal, H=Oiler Options, I=Sight Glass, J=Bearing Frame Cooling, K=Magnetic Drain, L=Expansion Chamber, M=Coupling Type, N=Coupling Guard; Option Ranges at **Q2 (16)**, refs `HG:HL, HN:HT, HV:HY, IA:ID, IF:IK, IM:IN, IP:IS, IU:IV, IX:IY, JA:JD, JF:JI`.
- **Materialized table:** header **row 16**. Permutation **C (2)**; option cols **D(3)..N(13)** =
  `Shaft Configuration, Shaft Material, Bearing Lubrication, Bearing Seal, Oiler Options, Sight Glass, Bearing Frame Cooling, Magnetic Drain, Expansion Chamber, Coupling Type, Coupling Guard`; Alphanumeric Code **O (14)**.
- Data rows **17 → 55468** = **55,452**. Code width **4** (`0001`…). Literal.
- Samples: perm 1 → `Sleeveless*420 SS*Grease*Lip*NONE*Not Required*Aluminum Fan*Not Required*Not Required*Elastomeric Sleeve*Steel` → `0001`; perm 2 → `…*Non-Sparking (Aluminum)` → `0002`; perm 3 → `…*Grid*Steel` → `0003`.
- No sub-table.

## 4. Motor Numbering

- `max_row=13276`, `max_col=34 (AH)`.
- **Top region** row 2: D=Motor, E=Motor Control (only these two carry vertical domains here; the remaining motor attribute domains live in the wide columns to the right, e.g. `AC='75 HP'`, `AH='324TSC'`).
- **Materialized MAIN table:** header **row 16**. Permutation **C (2) — column is EMPTY** (index not materialized in C for Motor). Option cols **D(3)..N(13)** =
  `Motor, Motor Control, Frame Size, Rated Speed, Rated Power, Voltage, Phase/Frequency, Num Poles, Enclosure, Efficiency, Brand`; Alphanumeric Code **O (14)**.
- Data rows **17 → 13276** = **13,260**. O-code width **3**, but **only 1 distinct value: `000`** across all rows → the main-table code is **inert/placeholder in v0.1**. ⚠️ FLAG (main motor code not usable as-is; must be regenerated or the Frame sub-table used).
- Sample main combo (D..N): `Included*Single Speed*143T*1800 RPM*1 HP*208-230/460 - 190/380*3/(50/60)*4*TEFC*Premium*Dean Choice` → `000`.
- **SUB-TABLE — Frame Size → code** (cols **S..U**, header **row 16**): S=`Permutation`, T=`Frame Size`, U=`Alphanumeric Code`.
  - Data rows **17 → 13276** = **13,260**; U-code width **2** (`01`…), sequential by S.
  - Samples: `(1,143T)→01`, `(2,145T)→02`, `(3,182T)→03`, `(4,184T)→04`, `(5,213T)→05`.

## 5. Flush Plan Numbering

- `max_row=211`, `max_col=14 (N)`.
- **Top region** row 2: D=Flush Plan, E=Flush Plan Routing, F=Flush Connections, G=Flush Temperature Range, H=Flush Cooling Media; Option Ranges at **K2 (10)**, refs `C:F, H:I, K:L, N:P`.
- **Materialized table:** header **row 26** (note: not 16). Permutation **C (2)**; option cols **D(3)..H(7)** =
  `Flush Plan, Flush Plan Routing, Flush Connections, Flush Temperature Range, Flush Cooling Media`; Alphanumeric Code **I (8)**.
- Data rows **27 → 211** = **185**. Code width **2** (`00`…). Literal.
- Samples: perm 1 → `NONE` → `00`; perm 2 → `P1200*Carbon Steel Pipe*Threaded*Below 650 F*NONE` → `01`; perm 3 → `…*Above 650 F*NONE` → `02`.
- Built by `Module2` from **Flush_Barrier Plan Constraints** (see §11).

## 6. Barrier Plan Numbering

- `max_row=16`, `max_col=17 (Q)`.
- **Top region** row 2: D=Barrier Plan, E=Barrier Plan Routing, F=Barrier Connections, G=Barrier Temperature Range, H=Barrier Cooling Media, I=Tank Capacity; Option Ranges header at **Q2 (16)** but the range refs r3/r4 are **empty**.
- **Materialized table:** header **row 16** with only `Permutation` (C) and `Alphanumeric Code` (O) present — **no option-column headers and no data rows** (0 enumerated). ⚠️ FLAG: table is defined but un-built in v0.1; also built by `Module2` from Flush_Barrier constraints.

## 7. Baseplate Numbering

- `max_row=1169`, `max_col=23 (W)`.
- **Top region** row 2: D=Baseplate Type, E=Drip Pan, F=Alignment Lugs, G=Lifting Lugs, H=Levelling Screws, I=Grounding Lug, J=Grout Hole, K=Isolation Pads, L=Stilts; Option Ranges at **O2 (14)**, refs `UN:UR, UT:UV, UX:UY, VA:VB, VD:VE, VG:VH, VJ:VK, VM:VN, VP:VQ`.
- **Materialized table:** header **row 16**. Permutation **C (2)**; option cols **D(3)..L(11)** =
  `Baseplate Type, Drip Pan, Alignment Lugs, Lifting Lugs, Levelling Screws, Grounding Lug, Grout Hole, Isolation Pads, Stilts`; Alphanumeric Code **M (12)**.
- Data rows **17 → 1169** = **1,153**. Code width **2** (`00`…). Literal.
- Samples: perm 1 → `NONE` → `00`; perm 2 → `Formed*NONE*Not Required*Not Required*Not Required*Not Required*Not Required*Not Required*Not Required` → `01`; perm 3 → `…*Required` → `02`.
- No sub-table.

## 8. Cooling Plan Numbering — ⚠️ EMPTY

- `max_row=1`, `max_col=1`, no headers, no data. **The Cooling Plan numbering table does not exist in v0.1.** Cooling Plan option domains DO exist elsewhere (Config Options fields `Cooling Plan`, `Cooling Plan Routing`, `Cooling Plan Extras`, `Cooling Connections`, `Cooling Plan Temperature`; and a `Cooling Plan` group in Pump Constraints), but no enumerated numbering table is present. **Flag as a gap for engineering.**

---

## 9. Config Options — field catalog

- Header (field names) on **row 3**; value domains listed down each field column, **rows 4 → 103**. `max_col=172`.
- **86 fields.** Field header sits every 2 columns (B, D, F, …), with the value list under the same column.

| Col | Field | #vals | Sample values |
|---|---|---|---|
| B | Pump Configuration | 9 | Pump Only; Pump and Baseplate; Pump, Baseplate, and Coupling; Pump and Motor; Pump, Baseplate, and Motor; Pump, Baseplate, Coupling and Motor |
| D | Pump Material | 9 | (20) Cast Iron; (22) Ductile Iron; (40) Cast Steel; (41) Cast Steel (420 SS Trim); (50) 316 S/S; (55) CD4MCu |
| F | Casing Material | 9 | Less Casing; (20) Cast Iron; (22) Ductile Iron; … |
| H | Casing Drain | 5 | Not Required; NPT Plug; NPT Valve; NPT Nipple; Custom |
| J | Casing Taps | 3 | NONE; NPT Discharge; NPT Discharge & Suction |
| L | Casing Gasket | 4 | Grafoil; Spiral Wound; Teflon; Aramid |
| N | Flange Configuration | 7 | 125# Flat; 150# Flat; 150# Raised; 300# Flat; 300# Raised; 300# RTJ |
| P | Spot Facing | 2 | Not Required; Required |
| R | Casing Wear Ring | 6 | NONE; Hard Iron; 316 SS; 420 SS; CD4MCu; Custom |
| T | Tack weld wear rings | 2 | Not Required; Required |
| V | Casing Mounting | 5 | NONE; Foot Mount; Yoke Foot; Pedestal; Cooled Pedestal |
| X | Seal Chamber Config | 9 | NONE; Standard Bore; Standard Bore Jacketed; … |
| Z | Shipping Gasket | 2 | Not Required; Required |
| AB | Casing Heat Jacket | 2 | Not Required; Required |
| AD | Impeller Trim | 99 | 3.5625; 3.625; 3.75; 3.875; 3.9375; 4 |
| AF | Impeller Balance | 2 | Single Plane; Dual Plane |
| AH | Impeller Material | 8 | NONE; (20) Cast Iron; (41) Cast Steel (420 SS Trim); (50) 316 S/S; … |
| AJ | Impeller Wear Ring Material | 6 | NONE; Steel; 316 SS; 420 SS; CD4MCu; Custom |
| AL | Shaft Configuration | 6 | Sleeved; Sleeveless; Motor; Motor w/ Shaft Extension; No Keyway; Custom |
| AN | Shaft Material | 7 | Steel; 316 SS; Hybrid 316 SS; 420 SS; CD4MCu; Hastelloy |
| AP | Bearing Lubrication | 4 | NONE; Oil; Grease; Sealed |
| AR | Bearing Seal | 4 | NONE; Labyrinth; Magnetic; Lip |
| AT | Oiler Options | 6 | NONE; Thermoplastic Oiler; Glass/Alum Oiler; … |
| AV | Sight Glass | 2 | Not Required; Required |
| AX | Bearing Frame Cooling | 4 | Not Required; Steel Tube; Aluminum Fan; Stainless Steel Fan |
| AZ | Magnetic Drain | 2 | Not Required; Required |
| BB | Expansion Chamber | 2 | Not Required; Required |
| BD | Coupling Type | 4 | NONE; Elastomeric Sleeve; Grid; Spider |
| BF | Coupling Guard | 4 | NONE; Steel; Non-Sparking (Aluminum); Custom |
| BH | Seal Option | 3 | Included; Supplied by others, installed by Dean; Supplied by others, installed by Others |
| BJ | Seal Manufacturer | 4 | Dean Choice; John Crane; FlexASeal; Custom |
| BL | Seal Configuration | 7 | Single Component; Single Cartridge; Double Component; … |
| BN | Seal Type | 31 | SIU - Non-Pusher Elastomer Bellows Seal; … |
| BO | OLD JC Style | 31 | Type 1; Type 2; Type 21; Type 6A; … |
| BQ | Gland Type | 5 | NONE; Flush; Quench; FTBV-D; Packing |
| BS | Gland Gasket | 5 | NONE; Grafoil Sheet; Teflon Sheet; Spiral Wound; Aramid |
| BU | Shaft Sleeve Material | 8 | NONE; 316 SS; Alloy 20; 420 SS; 420 SS Hardened; Hastelloy |
| BW | Inboard Rotating Face Material | 4 | NONE; Carbon; Silicon Carbide; Tungsten Carbide |
| BY | Inboard Stationary Face Material | 5 | NONE; Ceramic; Silicon Carbide; Tungsten Carbide; Ni-Resist |
| CA | Inboard Elastomer | 10 | NONE; Buna-N; EPDM; Viton; Aflas; Kalrez |
| CC | Inboard Hardware Material | 6 | NONE; 316 SS; Hastelloy C; Monel; Inconel; Custom |
| CE | Outboard Rotating Face Material | 4 | NONE; Carbon; Silicon Carbide; Tungsten Carbide |
| CG | Outboard Stationary Face Material | 5 | NONE; Ceramic; Silicon Carbide; Tungsten Carbide; Ni-Resist |
| CI | Outboard Elastomers | 9 | NONE; Buna-N; EPDM; Viton; Aflas; Kalrez |
| CK | Outboard Hardware Material | 6 | NONE; 316 SS; Hastelloy C; Monel; Inconel; Custom |
| CM | Hydropads | 2 | Not Required; Required |
| CO | Pumping Ring | 2 | Not Required; Required |
| CQ | Throttle Bushing | 2 | Not Required; Carbon |
| CS | Min-Flo Bushing | 3 | Not Required; Type-O; Type-S |
| CU | Lantern Ring | 4 | Not Required; Teflon; Iron; 316 SS |
| CW | Flush Plan | 21 | NONE; P1200; Plan 11; Plan 12; Plan 13; Plan 14 |
| CY | Flush Plan Code | 100 | N/A; A; B; C; D; AA |
| DA | Flush Plan Routing | 4 | Carbon Steel Pipe; Stainless Pipe; Carbon Steel Pipe/Tube; Stainless Pipe/Tube |
| DC | Flush Connections | 2 | Threaded; Custom |
| DE | Flush Temperature Range | 2 | Below 650 F; Above 650 F |
| DG | Flush Cooling Media | 3 | NONE; Air; Liquid |
| DI | Barrier Plan | 10 | NONE; Plan 7352; Plan 7353; Plan 52; Plan 53; Plan 62 |
| DK | Barrier Plan Code | 19 | N/A; JA; JB; JC; JD; KA |
| DM | Barrier Plan Routing | 4 | Carbon Steel Pipe; Stainless Pipe; … |
| DO | Barrier Connections | 2 | Threaded; Custom |
| DQ | Barrier Temperature Range | 2 | Below 650 F; Above 650 F |
| DS | Barrier Cooling Media | 3 | NONE; Air; Liquid |
| DU | Tank Capacity | 3 | Not Required; 3 Gallon; Custom |
| DW | Level Switches | 6 | NONE; 1 SPDT Switch; 2 SPDT Switches; … |
| DY | Pressure Switch | 2 | Not Required; Required |
| EA | Cooling Plan | 14 | NONE; SK1191; Plan A; Plan B; Plan C; Plan D |
| EC | Cooling Plan Routing | 4 | Carbon Steel Pipe; Stainless Pipe; … |
| EE | Cooling Plan Extras | 4 | NONE; Valve; Flow Indicator; Valve & Flow Indicator |
| EG | Cooling Connections | 2 | Threaded; Custom |
| EI | Cooling Plan Temperature | 2 | Above 650 F; Below 650 F |
| EL | Frame Size | 84 | 143T; 145T; 182T; 184T; 213T; 215T |
| EN | Drip Cover | 2 | Not Required; Required |
| EP | Conduit Box | 2 | Not Required; Required |
| ER | Baseplate Type | 5 | NONE; Formed; ANSI; API; Custom |
| ET | Drip Pan | 3 | NONE; Stainless; Steel |
| EV | Alignment Lugs | 2 | Not Required; Required |
| EX | Lifting Lugs | 2 | Not Required; Required |
| EZ | Levelling Screws | 2 | Not Required; Required |
| FB | Grounding Lug | 2 | Not Required; Required |
| FD | Grout Hole | 2 | Not Required; Required |
| FF | Isolation Pads | 2 | Not Required; Required |
| FH | Stilts | 2 | Not Required; Required |
| FJ | Paint Options | 5 | Standard; 3 Part Epoxy; High Temp; Marine; Custom |
| FL | Coating | 2 | Not Required; SKOTCHKOTE |
| FN | Auxillary Nameplate | 2 | Not Required; Required |
| FP | Crating | 5 | Standard; Skeleton; Fully Enclosed; Ocean Freight Packaging; ISPM-15 |

> Full value lists are in `output/_tmp_config_constraints.json` (regenerate via the script). This is the **field catalog** that the numbering/constraint sheets reference by name.

---

## 10. Pump Constraints (offered-option applicability matrix)

- `max_row=233`, `max_col=603 (WE)`.
- **Row 2** = group headers (one per option field, spanning the field's value columns). **Row 3** = individual option-value headers. **Identity cols:** A=`A Number`, B=`Series`, C=`Size` (row 3).
- **Model data rows 4 → 209 = 206 models** (col A filled). (Note: the `Module1` macro loops `A4:B166` = the first **163** models when building numbering; the sheet holds 206.)
- Cell values are **`STD` / `X` / blank** per (model × option value): `STD` = default, `X` = available, blank = not offered.
- **Pump Configuration bundle** (group `Pump Configuration`, cols **E..M**, 8 named values + 1 trailing spacer col M):
  `E=Pump Only, F=Pump and Baseplate, G=Pump, Baseplate, and Coupling, H=Pump and Motor, I=Pump, Baseplate, and Motor, J=Pump, Baseplate, Coupling and Motor, K=Pump and Coupling, L=Pump, Coupling and Motor`.
- **68 option-group headers with spans** (col range = value columns for that group):

| Group | Span | Group | Span |
|---|---|---|---|
| Pump Configuration | E..M | Seal Configuration | JP..JW |
| Pump Material | N..W | Seal Type | JX..LD (33) |
| Casing Material | X..AG | Gland Type | LE..LJ |
| Casing Drain | AH..AM | Gland Gasket | LK..LP |
| Casing Taps | AN..AQ | Shaft Sleeve Material | LQ..LY |
| Casing Gasket | AR..AV | Inboard Rotating Face Material | LZ..MD |
| Flange Configuration | AW..BD | Inboard Stationary Face Material | ME..MJ |
| Spot Facing | BE..BG | Inboard Elastomer | MK..MU |
| Casing Wear Ring | BH..BN | Inboard Hardware Material | MV..NB |
| Tack weld wear rings | BO..BQ | Outboard Rotating Face Material | NC..NG |
| Casing Mounting | BR..BW | Outboard Stationary Face Material | NH..NM |
| Seal Chamber Config | BX..CG | Outboard Elastomers | NN..NW |
| Shipping Gasket | CH..CJ | Outboard Hardware Material | NX..OD |
| Casing Heat Jacket | CK..CM | Hydropads | OE..OG |
| **Impeller Trim** | **CN..GI (100)** | Pumping Ring | OH..OJ |
| Impeller Balance | GJ..GL | Throttle Bushing | OK..OM |
| Impeller Material | GM..GU | Min-Flo Bushing | ON..OQ |
| Impeller Wear Ring Material | GV..HB | Lantern Ring | OR..OV |
| Shaft Configuration | HC..HI | Flush Plan | OW..PR (22) |
| Shaft Material | HJ..HQ | Barrier Plan | PS..QC |
| Bearing Lubrication | HR..HV | Cooling Plan | QD..QR |
| Bearing Seal | HW..IA | Cooling Plan Routing | QS..QW |
| Oiler Options | IB..IH | Cooling Plan Extras | QX..RB |
| Sight Glass | II..IK | **Frame Size** | **RC..UI (85)** |
| Bearing Frame Cooling | IL..IP | Baseplate Type | UJ..UO |
| Magnetic Drain | IQ..IS | Drip Pan | UP..US |
| Expansion Chamber | IT..IV | Alignment Lugs | UT..UV |
| Coupling Type | IW..JA | Lifting Lugs | UW..UY |
| Coupling Guard | JB..JF | Levelling Screws | UZ..VB |
| Seal Option | JG..JJ | Grounding Lug | VC..VE |
| Seal Manufacturer | JK..JO | Grout Hole | VF..VH |
| | | Isolation Pads | VI..VK |
| | | Stilts | VL..VN |
| | | Paint Options | VO..VT |
| | | Coating | VU..VW |
| | | Auxillary Nameplate | VX..VZ |
| | | Crating | WA..WE |

## 10b. Pump Constraints (2)

- `max_row=415`, `max_col=602 (WD)`. Same layout as Pump Constraints but **shifted one column right** (identity A/B/C at cols 0/1/2, group block begins at **F** instead of E; group `Pump Configuration` = F..N, etc.).
- **Model data rows 4 → 415 = 412 models** (a larger family/superset).
- Same 68 groups. Notable structural difference: **Seal Type span = KC..LC (27 cols)** here vs **JX..LD (33 cols)** on `Pump Constraints`, and **Casing Drain = AI..AQ (9)** vs `AH..AM (6)` — the two sheets are NOT column-identical; treat each as its own family matrix.
- **D column** here also carries a `Pump Material` value in row 3/4 (an extra identity-ish column) that is absent on `Pump Constraints`.

> ⚠️ Two applicability matrices with different model counts (206 vs 412) and slightly different spans. The loader must key by (A Number, Series, Size) and by group-header text, **not** by absolute column, and must not assume the two sheets share a column layout.

---

## 11. Flush_Barrier Plan Constraints

- `max_row=58`, `max_col=30 (AD)`.
- **Row 2** = group headers: C=`Flush Plan Routing`, H=`Flush Connections`, K=`Flush Temperature Range`, N=`Flush Cooling Media` (further groups for Barrier extend right).
- **Row 3** = value sub-headers under each group: `Carbon Steel Pipe / Stainless Pipe / Carbon Steel Pipe/Tube / Stainless Pipe/Tube` (routing), `Threaded / Custom` (connections), `Below 650 F / Above 650 F` (temp), `NONE / Air / Liquid` (media). Col **A = `Flush Plan`** (the row key).
- **Data rows 4 → …** keyed by Flush Plan name (A col); **47 flush-plan rows** with A filled. Cells are `STD` / `X` / blank marking which routing/connection/temp/media combos are valid per plan.
  - e.g. r5 `P1200`: routing `Carbon Steel Pipe/Tube=STD`, others `X`; `Threaded=STD, Custom=X`; `Below 650 F=STD, Above 650 F=X`; `NONE=STD`.
- This is the source `Module2.BuildTable` reads to enumerate **Flush Plan Numbering** (§5) and **Barrier Plan Numbering** (§6).

---

## 12. Price Options

- `max_row=225`, `max_col=686 (ZK)`.
- **Row 2** = group headers, **row 3** = value/bundle headers. Identity A=`A Number`, B=`Series`, C=`Size`.
- **Model data rows 4 → 209 = 206 models** (same model set as Pump Constraints).
- **Pump Configuration price columns E..M** (same 8 bundle names as Pump Constraints): row 4 shows numeric prices (e.g. `E=6790`) for the bundle, and option-group columns to the right carry per-option price adders (`0`, numeric) or `STD`/`X` applicability. So this sheet overlays **prices** on the same A/B/C + group layout as Pump Constraints.
- First 14 groups (identical group order to Pump Constraints): Pump Configuration (E..M), Pump Material (N..W), Casing Material (X..AG), Casing Drain (AH..AP), Casing Taps (AQ..AU), Casing Gasket (AV..AZ), Flange Configuration (BA..BH), Spot Facing (BI..BK), Casing Wear Ring (BL..BR), Tack weld wear rings (BS..BU), Casing Mounting (BV..CA), Seal Chamber Config (CB..CK), Shipping Gasket (CL..CN), Casing Heat Jacket (CO..CQ), … (67 groups total).

---

## 13. Codependencies

- `max_row=171`, `max_col=53 (BA)`.
- **Row 3** = NONE-collapse notes: `B3="IF CASING IS NONE, DON'T ASK ANY OF THE QUESTIONS BELOW"`, `L3="IF IMPELLER IS NONE, DON'T ASK ANY OF THE QUESTIONS BELOW"`. These are the *NONE-collapse* directives: when the trigger field (Casing / Impeller) is `NONE`, the dependent questions in that block are suppressed.
- **Row 6** = rule headers, laid out as **paired/tripled driver columns** — a trigger field followed by the affected field(s); the value lists sit in **rows 7+** under each column. The full row-6 header sequence:
  `B=Casing Material, C=Casing Drain, E=Casing Taps, F=Flush Plan | H=Series, I=Casing Material, J=Flange Configuration | L=Impeller Material, M=Impeller Trim | O=Shaft Configuration, P=Seal Type | R=Series, S=Shaft Configuration, T=Shaft Material | V=Bearing Lubrication, W=Bearing Seal | Y=Seal Configuration, Z=Seal Type | AB=Series, AC=Gland Type, AD=Seal Option | AF=Gland Type, AG=Seal Configuration | AI=Seal Option, AJ=Gland Type, AK=Flush Plan, AL=Barrier Plan | AN=Seal Configuration, AO=Shaft Sleeve Material | AQ=Pumping Ring, AR=Seal Configuration | AT=Cooling Plan, AU=Seal Chamber Config | AW=Baseplate Type, AX=Casing Mounting | AZ=Seal Manufacturer, BA=Seal Type`.
- **Rule interpretation (allow/deny):** each block reads "for the driver value in the left column, the listed values in the adjacent column(s) are the allowed set" (a whitelist). Example rows (7+):
  - `B=NONE, C=NPT Plug, E=No Taps, F=P1200 …` → when Casing Material context applies, the enumerated Casing Drain / Casing Taps / Flush Plan values are the permitted ones.
  - `H=Deanline, I=(50) 316 S/S, J=125# Flat` → Series `Deanline` allows Casing Material `(50) 316 S/S`, Flange `125# Flat`.
  - `L=NONE, M=3.5625 / 3.9375 / 4 / …` → Impeller Material vs Impeller Trim allowances.
  - `O=Sleeveless, P=SIB - Pusher O-Ring Seal / …` → Shaft Configuration `Sleeveless` allowed Seal Types.
  - `R=DL200/DL230, S=Motor, T=316 SS/Steel` → Series → Shaft Configuration → Shaft Material chains.
- Structure summary: rows 1–5 = titles + NONE-collapse notes; row 6 = column-group headers (driver → dependent); rows 7–171 = the value whitelists (variable length per column, blank-terminated). Loader should read each contiguous column group, take the left column as the key/driver and the remaining column(s) as the allowed dependent values.

---

## 14. Cross-cutting facts (explicit callouts)

- **(a) Cooling Plan Numbering is EMPTY** (`max_row=1, max_col=1`) and **Barrier Plan Numbering has header only / 0 data rows**; **Motor main Alphanumeric Code (col O) is inert** (single constant `000`). All three are gaps for engineering before SQL re-load can be considered complete for those segments.
- **(b) A# / Series / Size source** = **Pump Constraints** columns **A (`A Number`), B (`Series`), C (`Size`)** (row 3 headers; data rows 4–209 = 206 models; the parallel `Pump Constraints (2)` carries 412 models with the same A/B/C identity). The VBA numbering build reads `A4:B166` (first 163 models).
- **(c) Single-source-of-truth:** the **offered options** (Pump Constraints STD/X matrix) and the **numbering** (the per-segment enumerated tables driven, via the Option-Ranges blocks, from those same Pump Constraints columns) now derive from the **same workbook**, `PumpConfiguration_Logic_0.1.xlsm`. The Config Options field catalog, the applicability matrices, the codependency rules, the pricing overlay, and the identifier numbering tables are all internally cross-referenced by option-field **name**.
- **(d) Code encoding:** every Alphanumeric Code is a **literal zero-padded sequential string** (width per sheet: Wet End/Power Frame = 4; Motor-frame/Impeller/Flush/Baseplate = 2; Motor-main = 3-inert). No `BASE()`/hex formula is used; the "hex-looking" `AH/GN/UN/...` tokens are Option-Ranges *column references* into Pump Constraints, not codes.
- **(e) Loader rule (per Module1/Module2):** locate each table by searching `Permutation` (col C here) → last col `Alphanumeric Code`; read option columns strictly between them in left-to-right order; ComboString = those values `*`-joined with trailing `*` trimmed, rows containing `Custom` excluded, deduped; Permutation index ↔ Alphanumeric Code. Use `iter_rows(values_only=True)` with bounded columns on the big sheets (Wet End 64,212 / Power Frame 55,468 / Motor 13,276 rows).

---

*Generated for milestone D100. Source workbook and DB were not modified. Temp probe scripts were removed after extraction; JSON dumps `output/_tmp_numbering_map.json` and `output/_tmp_config_constraints.json` hold the full machine-readable detail and can be regenerated.*

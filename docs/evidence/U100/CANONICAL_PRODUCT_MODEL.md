# U100 — Canonical Product Model

**Date:** 2026-08-25  
**Milestone:** U100  
**Last updated:** 2026-08-25 (added vertical Part Number format, updated examples)

---

## Design Decision: Unified Part Number Sequence

**RULE:** Both Dean and Fybroc must follow the **same authoritative Part Number segment sequence.** The corresponding hex values for each pump family are concatenated with a separator `-`. The segment names and order are fixed; only the encoded values differ per family.

---

## Canonical Part Number Segment Sequence

**Horizontal pumps (all segments present):**
```
<Brand><SeriesCode><Size><Material><Trim>-<WetEndOptions>-<SealMfg><SealAssy>-<Options>-<FrameSize><MotorAssy>-<MotorMods>-<Testing>
```

**Vertical pumps (seal segment omitted):**
```
<Brand><SeriesCode><Size><Material><Trim>-<WetEndOptions>-<Options>-<FrameSize><MotorAssy>-<MotorMods>-<Testing>
```

**Rule:** Vertical pumps (5500, 5530, 6000, 7500, 7530, 8500) do not have seal assemblies. The seal segment is completely omitted from their Part Numbers — it is not a placeholder, it simply doesn't exist.

| Position | Segment | Separator | Fybroc Source | Dean Source |
|----------|---------|-----------|---------------|-------------|
| 1 | Brand | (none) | F | D |
| 2 | SeriesCode | (none) | Series+Flange code (A,B,C...) | A-number (610, 710...) |
| 3 | Size | (none) | Size code (1-9, A-P) | Size code |
| 4 | Material | (none) | Material code (1-7, V) | Material code |
| 5 | Trim | (none) | Trim code (2-char: AA-MA) | Trim code (2-char: same encoding) |
| — | `-` | separator | | |
| 6 | WetEnd/PumpOptions | `-` | Hex from Pump Options table | Hex from Wet End Numbering |
| — | `-` | separator | | |
| 7 | SealOptions | `-` | SealMfg + SealAssy hex | Seal hex (5-char) |
| — | `-` | separator | | |
| 8 | PlanOptions | `-` | N/A (Fybroc has no plan segment) | FlushPlan + BarrierPlan + CoolingPlan |
| — | `-` | separator | | |
| 9 | PowerFrame | `-` | FrameSize + MotorAssy hex | PowerFrame hex |
| — | `-` | separator | | |
| 10 | Motor | `-` | MotorMods hex | Motor + MotorOptions hex |
| — | `-` | separator | | |
| 11 | Baseplate | `-` | Options hex (coupling+baseplate) | Baseplate hex |
| — | `-` | separator | | |
| 12 | Additional | `-` | (none for Fybroc) | Additional options hex |
| — | `-` | separator | | |
| 13 | Testing | (none) | Testing hex | Testing + Documentation hex |

---

## Part Number Examples

**Fybroc Horizontal:** `FA35FC-1VC1-S03-3G-04XXX-XXX-00`
- Brand=F, Series=A(1500+ANSI), Size=3, Material=5(VR-1A), Trim=FC(9.250)
- WetEnd=1VC1, Seal=S03, Options=3G, PowerFrame=04XXX, Motor=XXX, Testing=00

**Fybroc Vertical:** `FG42GB-07HO-02-32049-XXX-00`
- Brand=F, Series=G(5500+ANSI), Size=4, Material=2(VR-1), Trim=GB
- WetEnd=07HO, Options=02, PowerFrame=32049, Motor=XXX, Testing=00
- Note: Seal segment is OMITTED for vertical series (no seal assembly)

**Dean:** `D610-00CA-AB01-ERR-TBD__-07617-0V03L-0KN00-00-1Z1IJ4`
- Brand=D, Series=610(A610→D610), WetEnd=00CA, Trim=AB(4.125)
- ImpellerOpts=01, PowerFrame=ERR, Seal=TBD__, Plans=07617
- Frame+Baseplate=0V03L, Motor=0KN00, Additional=00, Testing=1Z1IJ4

---

## Unified Configuration JSON Schema

Both families produce a canonical configuration JSON with the same top-level structure:

```json
{
  "family": "FYBROC" | "DEAN",
  "site": "TEL" | "IND",
  "series": "...",
  "configuration": {
    "SERIES": "...",
    "SIZE": "...",
    "MATERIAL": "...",
    "TRIM": "...",
    ...family-specific fields...
  },
  "segments": {
    "BRAND": "F" | "D",
    "SERIES_CODE": "...",
    "SIZE_CODE": "...",
    "MATERIAL_CODE": "...",
    "TRIM_CODE": "...",
    "WET_END_CODE": "...",
    "SEAL_CODE": "...",
    "PLAN_CODE": "...",
    "POWER_FRAME_CODE": "...",
    "MOTOR_CODE": "...",
    "BASEPLATE_CODE": "...",
    "ADDITIONAL_CODE": "...",
    "TESTING_CODE": "..."
  },
  "part_number": "...",
  "sku": "...",
  "signature": "...(SHA-256)..."
}
```

---

## Manufacturing Sites

| Site Code | Location | Families |
|-----------|----------|----------|
| TEL | Telford, UK | Fybroc |
| IND | Indianapolis, USA | Dean |

---

## SKU Format (unified)

Both families: `<FamilyPrefix><Series>-<8char_token><VersionLetter>`

- Fybroc: `F1500-A1B2C3D4A`
- Dean: `D2110-X7Y8Z9W0A`

The SKU uniquely identifies one configured product and retrieves the full Part Number, configuration, and BOM.

---

## Exit Gate

Both families persist through one product model:
- Same `cfg.ConfiguredProduct` table
- Same `cfg.usp_ResolveConfiguredProduct` procedure
- Same `cfg.usp_LookupBySKU` retrieval
- Same canonical configuration JSON schema
- Same Part Number segment-sequence logic (family-specific values only)

# D130 — SQL Dean Identifier Authority

**Date:** 2026-08-24  
**Milestone:** D130  

> **SUPERSEDED / historical analysis (not the completion record).** This document
> is an early design analysis dated 2026-08-24 and was NOT evidence of a built
> milestone. The authoritative D130 completion record is
> `docs/evidence/D130/DEAN_D130_EXIT.md` (2026-08-26); the pre-implementation
> design is `docs/evidence/D130/DEAN_D130_DESIGN.md`. Preserved for history.

---

## Dean Part Number Generation Flow

```
Series (PH2110)
    |
    v
Authoritative A-number (A610)
    |
    v
A610 -> D610 (brand prefix swap)
    |
    v
Remaining engineering segments (Wet End + Trim + Impeller + Power Frame + Seal + Plans + Motor + Baseplate + Testing + Docs)
    |
    v
Dean Part Number: D610-00CA-AB01-ERR-TBD__-07617-0V03L-0KN00-00-1Z1IJ4
    |
    v
SKU: D2110-<8char><VersionLetter>
```

## SQL Procedures (shared with Fybroc)

| Procedure | Dean Support | Notes |
|-----------|-------------|-------|
| cfg.fn_LookupIdentifierCode | ✅ | Uses PumpFamilyId=1 (DEAN) |
| cfg.usp_GeneratePartNumber | ✅ | FamilyCode='DEAN' |
| cfg.usp_GenerateSKU | ✅ | Prefix='D' (vs 'F' for Fybroc) |
| cfg.usp_ResolveConfiguredProduct | ✅ | Family-agnostic |
| cfg.usp_LookupBySKU | ✅ | Family-agnostic |

## SKU Format

`D<Series>-<8char_token><VersionLetter>`

Example: `D2110-7F4E2A1BA` (D + PH2110 series + 8-char SHA token + A=version 1)

## A-number to D-number Conversion

The workbook Smart Number shows A610 in the segment then displays D610 in the part number.
The conversion is: replace leading 'A' with 'D' (brand prefix).

## Exit Gate Status

SQL can generate Dean Part Numbers using the same procedures as Fybroc. 
Dean-specific AttributeValue entries (series codes, material codes, size codes) 
need to be loaded from the Dean Data Sheet workbook during full implementation.
Currently the DEAN family exists in SQL (PumpFamilyId=1) but has no published 
metadata yet — that requires compiling the Dean Wet End Numbering (146K rows) 
and Motor Numbering (114K rows) lookup tables.

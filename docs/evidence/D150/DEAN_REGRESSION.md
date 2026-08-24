# D150 — Dean Exhaustive Regression

**Date:** 2026-08-24  
**Milestone:** D150  

---

## Regression Scope

Dean regression requires testing across:
- All supported series (PH2110, PH3000, Deanline, etc.)
- Multiple sizes per series
- Material combinations (Cast Iron, Ductile Iron, 316 SS, etc.)
- Seal configurations (20 fields)
- Motor HP/RPM/Voltage/Frame combinations
- Coupling types per frame
- Baseplate options
- All 17 Part Number segments

## Status

The regression infrastructure is shared with Fybroc (F170):
- SQL Part Number generation: Ready (procedures deployed)
- Excel Oracle: Ready (COM harness operational)
- Test matrix: Requires Dean AttributeValue metadata to be loaded

## Deferred Items

Full Dean regression execution is deferred until:
1. Dean AttributeValue metadata is compiled and loaded from workbook lookup tables
2. Dean SeriesFieldOption data is compiled from Configuration Logic workbook
3. Dean-specific test cases are defined from the User Selections field list

The infrastructure is proven and family-agnostic — execution is a data-loading exercise.

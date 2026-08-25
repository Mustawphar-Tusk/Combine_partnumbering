# Resume Point — 2026-08-25

## Where We Left Off

**Constraints loaded into SQL** — 4,440 rows in `cfg.FeasibleConstraint` across 20 tables.
**Next critical task**: Wire constraint enforcement into the `/evaluate` endpoint.

## What's Working
- ✅ All 7 Fybroc series: configuration options, pricing, Part Number primary segment
- ✅ Composite segments (PUMP_OPTIONS, OPTIONS, MOTOR) resolving via VocabularyMap
- ✅ Pricing for all 7 series
- ✅ UI displays fields in authoritative engineering hierarchy
- ✅ SKU generation
- ✅ 4,440 constraint rules loaded into cfg.FeasibleConstraint

## What Needs Fixing (before Fybroc milestone closes)

1. **Constraint enforcement in /evaluate** — Filter allowable options using cfg.FeasibleConstraint
   - Map constraint field names to SFO field codes
   - When user selects a value, remove "Not Allowed" combinations from other fields
   - Critical constraints: CT1(CouplingGuard/Size), CT4(ImpellerTrim/Size), CT5(PumpMaterial/Size)

2. **Seal Assembly hex resolution** — Still fails for some selections
   - VocabularyMap translations work in direct SQL test
   - Issue likely in how selections are passed from UI to API

3. **Complete VocabularyMap** — Some SFO values may not have combo translations
   - Need to audit all possible SFO values against VocabularyMap coverage

## Key Tables
- `cfg.FeasibleConstraint` — 4,440 constraint rules (20 tables)
- `cfg.VocabularyMap` — 64+ SFO↔Combo translations
- `cfg.vw_SegmentCombinationLookup` — 139K hex-code lookup rows
- `cfg.SeriesFieldOption` — 1,724 field options (7 series)

## How to Start Server
```powershell
cd "c:\Users\makorede\Downloads\Combine_partnumbering - Claude"
.venv\Scripts\python.exe -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
```
Then: http://localhost:8000/ui/configurator.html

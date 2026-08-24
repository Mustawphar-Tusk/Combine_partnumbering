# Resume Point — 2026-08-24

## Where We Left Off

**Current state:** Part Number composite segments are resolving via `cfg.VocabularyMap` (confirmed working in direct SQL test: PUMP_OPTIONS→`06O5`, SEAL→`01`, OPTIONS→`0A`). The UI at `http://localhost:8000/ui/configurator.html` needs final testing to confirm end-to-end.

## What's Working

- ✅ Primary identity segment: Brand + Series + Size + Material + Trim (e.g., `FI47GC`)
- ✅ Pricing from SQL: Base pump prices resolving ($9,520 - $65,335 confirmed)
- ✅ SKU generation: `F1500-xxxA` format
- ✅ VocabularyMap: 64 mappings translating SFO values to combo table values
- ✅ Segment combination lookup: 139K rows accessible via `cfg.vw_SegmentCombinationLookup`
- ✅ All 7 Fybroc series have selectable configuration options
- ✅ UI allows selecting, changing, and re-selecting any field

## What Needs Testing/Fixing Next

1. **End-to-end Part Number in UI** — refresh and test with: CASING_DRAINS=`supplied by fybroc`, SHAFT_MATERIAL=`316 ss`, FLUSH=`internal flush`, SEAL_TYPE=`8b2 single outside`, COUPLING_OPTION=`coupling included`
2. **Motor segment** — MOTOR_OPTION=`installed by fybroc` should resolve via VocabularyMap → `Motor Included` → hex from MOTOR_ASSEMBLY table
3. **Frame Size segment** — needs FRAME_SIZE field loaded or resolved from motor specs
4. **Testing segment** — needs Testing combination table (from F110.10 compilation)
5. **5500 series pricing** — no pricing rules loaded for 5500 (only horizontal series have pricing)
6. **Dean metadata** — DEAN family has no SeriesFieldOption data (needs User Selections compiled from workbook)

## Key Architecture

```
User Selection (lowercase SFO vocabulary)
    ↓
cfg.VocabularyMap (SQL - 64 mappings)
    ↓  translates to combo vocabulary
cfg.vw_SegmentCombinationLookup (SQL view - 139K rows)
    ↓  finds matching hex code
Part Number segment
```

## How to Start the Server

```powershell
cd "c:\Users\makorede\Downloads\Combine_partnumbering - Claude"
.venv\Scripts\python.exe -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
```

Then open: `http://localhost:8000/ui/configurator.html`

## Git State

- Branch: `feature/m021-shared-excel-production-hardening`
- Tags: `f180-fybroc-complete`, `d160-dean-complete`, `u170-unified-complete`
- Phases complete: F (Fybroc), D (Dean), U (Unified backend)
- Current work: UI testing + Part Number end-to-end validation

## Roadmap Position

- Roadmap version: 1.6+
- All infrastructure milestones (F100-F180, D100-D160, U100-U170) complete
- Phase T (Testing/UAT) in progress — building test UI before formal UAT
- The configurator UI is the pre-UAT validation tool

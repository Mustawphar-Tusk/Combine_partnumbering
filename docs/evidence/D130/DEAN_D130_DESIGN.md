# D130 — SQL Dean Identifier Authority: Design

**Date:** 2026-08-26
**Milestone:** D130 — SQL Dean Identifier Authority
**Status:** DESIGN (pre-implementation). Records the Dean Part Number model,
sources, storage, and SQL assembly plan agreed before coding.

> **Record-keeping note:** `MilestoneRegister.md` and an older
> `docs/evidence/D130/DEAN_IDENTIFIER_AUTHORITY.md` (2026-08-24) marked D130
> "Complete", but the code shows it is NOT built (no Dean identifier data, PN
> assembly is Fybroc-only). Per the user, we preserve the old analysis doc, add
> this design + a new EXIT doc, and correct the register when D130 truly exits.

---

## 1. Authoritative Dean Part Number structure

From `config/identifier_profiles/dean.json` + `Smart Number!B5` (workbook) +
`docs/evidence/D100/DEAN_DATASHEET_VBA_LOGIC.md`:

```
Dean PN = D<A#> - <WetEnd(4)> - <Trim(2)><ImpOpts(2)> - <PowerEnd(3)>
          - <Seal(5)> - <Flush(2)><Barrier(2)><Cooling(2)> - <Frame><Baseplate(3)>
          - <AddlOpts(2)> - <Testing(2)><Doc(4)>
```
- **Base identifier**: Series+Size → **A-number** → **D-number** (`A461` → `D461`:
  base_prefix `D`, remove_model_prefix `A`).
- Each engineering segment is a **base-36 code** = the row index of the selected
  option-combination in that segment's numbering table (authoritative data in the
  Dean Data Sheet Rev 2 numbering sheets).
- **Seal** segment = `00000` unless seal Included → `TBD__` (external seal DB).
- **Motor frame** code = `00`/absent when no motor (Pump Configuration gating).

## 2. Sources (authoritative)

| Element | Source | Notes |
|---------|--------|-------|
| Series+Size → A# → D# | `exports/m023_dean_source_reconciliation.json` `model_reconciliation` (206 models, model_key `SERIES\|SIZE`, `authoritative_model_identifier`=A#, `authoritative_base_identifier`=D#) | also in workbook `Reference Data` |
| Wet End code | `Wet End Numbering` sheet: String (`*`-joined) → Base-36 (col P, width 4) | 101,910 rows |
| Power End code | `Power End Numbering`: String → Base-36 (width 2) | 460 rows |
| Impeller Trim | `Config Info` trim letters (inch+decimal) | per D100 |
| Impeller Options | `Wet End Numbering` (Impeller Table106) | width 2 |
| Baseplate code | `Baseplate Numbering`: String → Base-36 (width 3) | 1,537 rows |
| Cooling code | `Misc Numbering` (cooling): String → Base-36 (width 2) | 190 rows |
| Additional Options | `Misc Numbering` (addl opts): String → Base-36 (width 2) | — |
| Testing code | `Test and Doc Numbering` (testing): String → Base-36 (width 2) | — |
| Documentation code | `Test and Doc Numbering` (doc): String → Base-36 (width 4) | ~500K combos |
| Motor code | `Motor Numbering`: String → Base-36 (width ~4) | ~114K rows |

## 3. Load-vs-compute decision: **LOAD the String→Code map**

The base-36 code is the enumeration row-index, but reproducing Excel's exact
iteration order (incl. `NONE→N/A` collapse and `Custom` exclusion) in code is
fragile. The workbook itself looks the code up via `VLOOKUP(String, Table,
code_col)`. Since the exit gate is **"SQL matches the approved workbook output"**,
we **load the authoritative String→Code map** per segment — it IS the workbook's
own lookup, exact and low-risk. Volume (~760K rows across segments) is fine for an
indexed SQL lookup.

## 4. Storage (family-scoped, additive — no Fybroc impact)

- **A#/D# identity:** load Series+Size → A#/D# into `cfg.AttributeValue`
  (family-scoped, PumpFamilyId=DEAN) under a field like `SERIES_SIZE` →
  IdentifierCode = D-number; OR a small dedicated `cfg.DeanModelIdentity` table.
  Decision: reuse `cfg.AttributeValue` where it fits (it is the existing
  identifier-code store, already family-scoped); use a dedicated table only if the
  (series,size)-keyed shape doesn't fit AttributeValue's (FieldCode, DisplayValue)
  model.
- **Segment String→Code maps:** a new family-scoped table
  `cfg.SegmentCombinationCode` (PumpFamilyId, SegmentCode, ComboString, Code) with
  a unique index on (PumpFamilyId, SegmentCode, ComboString). Loaded from the
  numbering sheets. This is additive; Fybroc uses its existing segment-combination
  path untouched.

## 5. SQL assembly — additive Dean branch

`cfg.usp_AssembleConfiguredProduct` currently hardcodes the Fybroc PN shape
(branch on `@IsVertical` only). Add a **`@FamilyCode='DEAN'` branch** that
assembles the Dean PN per §1 from the resolved segment codes in `@SegmentsJson`.
The Fybroc branch is **byte-for-byte unchanged** (guarded by the gate). The API
resolve path computes the Dean segment codes (A#/D# + each segment String→Code
lookup) and passes them in `@SegmentsJson`, exactly as it does for Fybroc.
`cfg.usp_GenerateSKU` already handles DEAN (prefix `D`, PN-derived token) — reused
as-is.

## 6. API resolve (Dean segment resolution)

The Python resolve path builds each Dean segment's `*`-joined ComboString from the
selections (in the numbering table's column order), looks up the code in
`cfg.SegmentCombinationCode` (family DEAN), assembles the Python parity PN, and
passes the segment codes to the SQL assembler. Seal → `00000`/`TBD__`; motor/
gated-out segments → their no-charge/absent code. Fybroc resolve path unchanged
(Dean-gated on `family_upper == 'DEAN'`).

## 7. Verification (per milestone-exit-audit)

- `scripts/audit_dean_identifier.py`: representative Dean (series,size,config) →
  PN matches the workbook Smart Number output segment-by-segment; SQL==python
  parity; SKU = D + PN-derived token (1:1); deterministic reuse; no `?` where
  segments are known.
- `scripts/run_all_fybroc_audits.py` → ALL CORRECTIONS INTACT 7/7; Fybroc
  identifier rows + PN/SKU unchanged (isolation).

## 7a. CORRECTED segment spec (from Smart Number formula trace, 2026-08-26)

**Important correction to §1-3:** the live workbook `Smart Number` sheet does NOT
`VLOOKUP` a `*`-joined `String` column. Each row-12 segment code is computed by an
Excel dynamic-array `FILTER(Table[Base-36 Code], (Table[colA]=selA)*(Table[colB]=
selB)*...)` keyed on the **individual option columns**, in a fixed predicate order.
The numbering sheets' `String` column IS the pre-joined key in that same column
order, so loading `String -> Base-36 Code` per sheet is equivalent to the FILTER —
the resolver just rebuilds the identical `*`-join in the predicate column order.
Source: `output/dean_smart_number_trace.txt` (full Smart Number dump).

**B5 / J5 assembly (exact):**
```
B5 = "D" & C12 & "-" & D12 & "-" & H12 & I12 & "-" & K12 & "-" & O12
        & "-" & Q12 & S12 & U12 & "-" & W12 & X12 & "-" & Z12 & AB12 & "-" & AD12
J5 = "-" & AH12 & AJ12
```

| PN piece | Cell | Segment | Table | Predicate column order (ComboString) | Special rule |
|----------|------|---------|-------|--------------------------------------|--------------|
| `D` | B12 literal | brand | — | — | always `D` |
| `<A#>` | C12 | A# base | A_Table | key = (Series=DS!D14, Size=DS!D15) → A#, then strip leading `A` | fallback `0000` |
| WetEnd(4) | D12 | Wet End | Table100 | PumpMaterialClass, CasingMaterial, FlangeStyle, CasingTaps, DrainOptions, CasingMount, CasingGasket, ShippingGasket, CasingWearRing, TackWeldWearRings, SealChamberConfig, SpotFacing (12) | any "Custom" in F13:G25 → `____`; no match → `ERR` |
| Trim(2) | H12 | Impeller Trim | (local B31:C43 + E34:F41) | inch-letter + decimal-letter of DS!D31 | Fybroc-style; no table |
| ImpOpts(2) | I12 | Impeller Opts | Table106 | ImpellerBalance, ImpellerMaterial, ImpWearRingMaterial, BalanceHoles (4) | any "Custom" in J13:J16 → `__` |
| PowerEnd(3) | K12 | Power Frame | Table101 | ShaftConfiguration, ShaftMaterial, LubricationOptions, OilerOptions, OilSeal, SightGlass, MagneticDrain, ExpansionChamber, BearingFrameCooling, CouplingGuard, CouplingType (11) | no match → `ERR` |
| Seal(5) | O12 | Seal | — (special) | `IF(DS!D49<>"Included","00000","TBD__")` | external seal DB |
| Flush(2) | Q12 | Flush Plan | Config Info FH | FA=flush-letter (DS!H14); Plans 21/22/23 add FG≥flow threshold | array lookup |
| Barrier(1) | S12 | Barrier Plan | Table76 | `VLOOKUP(DS!H19, Table76[Code..Base-36], 4)` | VLOOKUP (not FILTER); narrow width |
| Cooling(2) | U12 | Cooling Plan | Table104 | CoolingPlan, CoolingPlanPiping, CoolingPlanExtras (3) | — |
| Frame(2) | W12 | Motor Frame | Table2486 | `BASE(MATCH(DS!G36, Table2486[MotorFrameSize]),36,2)` | gate: baseplate OR coupling OR frame present else `00` |
| Baseplate(3) | X12 | Baseplate | Table124 | BaseplateType, DripPan, AlignmentLugs, LiftingLugs, LevellingScrews, GroundingLug, GroutHole, IsolationPads, Stilts (9) | BaseplateType="NONE" → `000` |
| Motor(3) | Z12 | Motor | Table110 | Motor, MotorControl, RatedPower, RatedSpeed, Voltage, Phase/Frequency, Enclosure, Efficiency, Brand (9) | MotorOptions(DS!G29)≠"Included" → `0000` |
| MotorOpts(2) | AB12 | Motor Opts | — | **NO FORMULA — static `00` (INERT, pending engineering)** | inert |
| AddlOpts(2) | AD12 | Additional | Table105 | ShippingGasket, AuxNameplate, Crating, PaintOptions, Coating (5) | — |
| Testing(2) | AH12 | Testing | Table108 | PerformanceTesting, Hydrotest, Vibration, SoundLevel, GeneralInspection (5) | — |
| Doc(4) | AJ12 | Documentation | DocumentationNumbering | Document1, Document2, Document3, Document4 (4) | — |

All selection inputs flow from the **`Data Sheet`** sheet (D-column wet-end/
impeller/power/coupling block + G-column flush/barrier/cooling/frame/baseplate/
motor/testing/doc block, plus H14/H19 flush/barrier letters, D11 flow/size, D14/
D15 series/size, D49 seal, D31 trim). Example live PN:
`D610-00CA-AB01-ERR-TBD__-07617-0V03L-0KN00-00` + `-1Z1IJ4`.

**NONE→N/A** is NOT a generic per-value ComboString substitution in the live
formulas — it lives in the numbering-table row DATA (Module2 enumeration stored
dependents as `N/A` when a controller was `NONE`), so loading the sheets' String
column captures it. Segment-level gates (seal/motor/frame/baseplate) short-circuit
the lookup entirely.

## 7b. SEAL SEGMENT REMOVED FROM THE DEAN PN (decision 2026-08-26)

Empirical search across ALL Dean workbooks (`Dean Data Sheet Rev 2.xlsm`,
`DeanMasterConfig_v14`, `PumpConfiguration_Logic.xlsm`) confirmed there is NO seal
base-36 numbering/hexcode table anywhere: the seal sheets (`Seal Options`, `Seal
Pricing`, `Seal Descriptions`) carry only descriptions/prices, and the only seal
formulas are two `VLOOKUP`s into `Seal Descriptions` for the quote-line TEXT. The
seal CODE is authored solely in the external `Seal Numbering.accdb` (queried by the
VBA `getSealOptions`), which is not in the workspace. The workbook's own Smart
Number seal cell only ever emits the placeholder `IF(D49<>"Included","00000",
"TBD__")`.

**Decision:** the seal segment is REMOVED from the Dean Part Number (SQL Dean
branch + Python resolver both updated, parity preserved). Seal STATUS is still
resolved into `segment_debug` (`seal_status` = `included_external_db` | `none`,
`seal_code_placeholder` = the workbook 00000/TBD__ value). If the seal Access DB is
later provided, seal can be re-added to the PN cleanly (load it like the other
numbering tables). New Dean PN:

```
D<A#>-<WetEnd>-<Trim><ImpOpts>-<PowerEnd>-<Flush><Barrier><Cooling>
  -<Frame><Baseplate>-<Motor><MotorOpts>-<AddlOpts>-<Testing><Doc>
```

## 8. Known gaps (expected)

- **Seal** segment `TBD__` when seal Included (external seal Access DB is the seal
  numbering authority — same as D120 seal pricing).
- **Motor** code where motor is C/F / gated out.
- Any (series,size) not in `model_reconciliation` READY set → no A#/D# → PN base
  unresolved (report, don't fabricate).
- **Motor Options segment (AB12)** is INERT in the workbook (static `00`, no
  formula) — we emit `00` to match, flag as pending-engineering.
- **Seal segment** `TBD__` when seal Included (external seal Access DB authority).
- **Impeller Trim (H12)** and **Flush (Q12, Config Info array)** and **Barrier
  (S12, Table76 VLOOKUP)** use non-FILTER mechanisms; loader handles each per its
  actual formula, not the generic String→Code path.

## 8a. STORAGE DECISION REVISED (DB inspection, 2026-08-26) — reuse Fybroc infra, NO new table

Inspecting the live DB corrected §4. The Fybroc identifier RUNTIME does NOT use
`cfg.SegmentCombination` / `cfg.AttributeValue` for composite segments — those
metadata tables are EMPTY for both families. The authoritative runtime segment
store is **`stg.SegmentCombinationImport`** (batched by
`stg.SegmentCombinationImportBatch`, `FamilyCode`+`Status='Loaded'`), columns
`SegmentCode, SelectionsJson, SegmentValue(=code), ExpectedWidth, CombinationKey`,
with `CHECK(LEN(SegmentValue)=ExpectedWidth)` and unique
`(ImportBatchId,SegmentCode,CombinationKeyHash)`. The API reads it via
`_segment_rows`/`_seg_first_match` filtered to `FamilyCode='FYBROC'`.

**Therefore Dean reuses the SAME infra, family-scoped — NO new
`cfg.SegmentCombinationCode` table:**
- **Segment String→Code maps** → load into `stg.SegmentCombinationImport` under a
  `FamilyCode='DEAN'` batch. `SelectionsJson` = the ComboString components (as a
  JSON object in FILTER-predicate column order); `SegmentValue` = Base-36 code;
  `ExpectedWidth` = the segment width. Dean resolver looks these up by an EXACT
  ComboString match (vs Fybroc's substring), family-gated.
- **A#/D# identity** (Series+Size→A#→D#) → load into existing family-scoped
  `cfg.PumpModelReference` (PumpFamilyId, ConfigurationVersionId, ModelIdentifier=
  A#, SeriesCode, SizeCode, BaseIdentifier=D#). Dean ConfigurationVersion already
  exists (cvid=1, VersionCode 'REV2'). This table is currently empty (both
  families) so loading Dean rows is additive and touches no Fybroc data.
- **No schema migration required** — both tables exist. (Supersedes the design's
  proposed `cfg.SegmentCombinationCode` migration.)
- SKU: `cfg.usp_GenerateSKU` already DEAN-aware. Assembly: additive
  `@FamilyCode='DEAN'` branch in `cfg.usp_AssembleConfiguredProduct` reads Dean
  segment keys from `@SegmentsJson` and concatenates per §7a B5/J5.

Fybroc isolation: Dean rows go under a DEAN batch / DEAN family rows only; the
Fybroc `FamilyCode='FYBROC'` batch and its 1151 ConfiguredProducts are untouched.

## 9. Load scope decision (large sheets)

The numbering sheets are large (Wet End 146,460; Motor 114,100; Test+Doc 500,016).
The workbook's own FILTER only ever returns rows that exist in the enumerated
table, so loading the full `String → Base-36 Code` map per sheet is the faithful,
lowest-risk approach (it IS the workbook's lookup domain). Volume is fine for an
indexed SQL table (~760K rows total across segments). Load ALL rows; do not prune
to "reachable" combos (pruning risks diverging from the workbook on edge configs).
Loader reads via bulk `iter_rows(values_only=True)` bounded to the String+Code
columns only (openpyxl random `ws.cell` access is far too slow at these sizes).

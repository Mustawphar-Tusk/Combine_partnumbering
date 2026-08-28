# Fybroc Constraint Extraction Alignment Audit

Purpose: confirm that our extracted constraint data aligns with the
authoritative Rev0.3 workbook — both the raw cells AND the workbook's own
computed (formula/LAMBDA) outputs.

Source: `workbooks/Fybroc/Fybroc Configuration Rev0.3.xlsx` (read-only).
Rev0.3 is a `.xlsx` — **no VBA macros**; all logic is cell formulas, named
LAMBDA functions, and dynamic-array spills.

## 1. Feasible Constraints tables — cell-level reconciliation

An independent re-scan of the `Feasible Constraints` sheet (whole-sheet anchor
detection, per-table row counting) was compared against the extracted
`FYBROC_CONSTRAINT_MODEL.json`.

Result: **29/29 ConstraintTables match exactly** on row count, including the
large ones (ConstraintTable21 = 3477 rows, ConstraintTable4 = 517 rows). No
mismatches. The nine tables that a prior extractor missed (stacked vertically
within a column group: CT2, CT3, CT6, CT11, CT13, CT14, CT15, CT17, CT26) are
present and correct.

## 2. Constraints sheet — enforcement chain (formulas)

The `Constraints` sheet computes its combination matrix via formulas, not
static data:

- `D6` = `twolists(B5:B39, B5:B39)` — a custom LAMBDA that generates the
  field-pair combination grid (spilled array `D6:E1230`).
- Per-series verdict columns `F..M` (headers 1500..5530) hold literal computed
  verdicts: `Yes` / `No` / `No Combination` / `Ignore`.
- `N` "Any yes?" = `IF(OR(F..M="Yes"),"Yes","No")`
- `O` "All No Combination?" = `IF(AND(F..M="No Combination"),"Yes","No")`
- `P` "Ignore combination" = `IF(OR(COUNTIF(...)=0, D=E),"Ignore","")`
- `Q` "Combination?" = `IF(R="","No Combination","Combination exists")`
- `R` "answer" (ArrayFormula) = `IFERROR(UNIQUE(DUPLICATES(ANCHORARRAY(AU6)),1),"")`

Our extraction reads the computed literal verdicts from columns
`F..M / N / O / P / Q / R` (matching header row 5), i.e. the **outputs** of
these formulas — the correct thing to consume, since the formulas themselves
are the workbook's derivation of those verdicts.

## 3. Named LAMBDA engine + per-series spills

Rev0.3 defines a small LAMBDA library that powers the live per-series logic:

- `twolists`, `DUPLICATES` — combination generation / duplicate detection.
- `onefilter`, `twofilter`, `threefilter`, `fourfilter` — multi-key FILTER
  lookups (the 1/2/3/4-key allowed/not-allowed resolution).

Per-series computed projections are exposed as named dynamic-array spills:

- `Questions<series>` -> `Selections!R2..AA2` — the **applicable field set per
  series** (computed from the base X/STD matrix via the filters).
- `Items<series>` -> `Items!CA4..CJ4`, `ItemQuestions<series>` -> `Items!Q474..`

### Verified: base-matrix extraction == workbook computed spill

We compared the workbook's computed `Questions<series>` spill (the authoritative
per-series applicable-field output) against our base-matrix extraction
(distinct fields carrying an X/STD marker per series in `cfg.SeriesFieldOption`):

| Series | Workbook `Questions<series>` spill | Our extraction (fields) |
|---|---|---|
| 1500 | 46 | 46 |
| 5500 | 38 | 38 |
| 7500 | 4 | 4 |

The counts match. Our extraction of the base Selections X/STD matrix reproduces
the same per-series field applicability the workbook derives through its LAMBDA
spill — so consuming the base matrix is equivalent to consuming the workbook's
computed output.

## Conclusion

Extraction is aligned with the authoritative workbook at three levels:
1. Feasible Constraints tables — exact cell/row-count match (29/29).
2. Constraints combination-matrix verdicts — reads the formula outputs.
3. Per-series applicable fields — matches the LAMBDA-computed `Questions<series>`
   spill.

No macros exist to reconcile (Rev0.3 is `.xlsx`). The LAMBDA library and spill
ranges are the workbook's "logic"; our compiled artifacts consume their results
faithfully.

## 4. Motor Constraints sheet — audit + correction

The `Motor Constraints` sheet (955 x 86) holds 19 mini-tables across 6
series-scope groups (row 2: `1500 and 1600`, `1530 and 1630`, `2530`, `3000`,
`5500`, `5530`), each a 3-column `(dim1, dim2, Allowed?)` block. Dimensions:
`Alt_Size x F_Frame_Size`, `Alt_Size x F_MotorHpRpm`,
`F_Frame_Size x F_MotorHpRpm`, plus `F_MotorHpRpm x F_Motor Type` for the
1500/1600 group.

**Defect found and fixed.** The block structure (19 blocks, dimensions, series
scopes) matched, but an independent per-block row count revealed the extractor
was **truncating** several blocks. `compile_fybroc_motor_constraint_model.py`
had `MOTOR_MAX_SCAN_ROW = 210` (comment: "last populated row is 199"), which is
only true for the short `Alt_Size x F_Frame_Size` blocks. The
`Alt_Size x F_MotorHpRpm` blocks are much longer — e.g. the 1500/1600 one runs
continuously with valid `Allowed` rows from row 6 to row 530 (`10x12x16 /
100-1200 / Allowed`), ending at a genuine blank at row 531. The 210 cap dropped
~877 legitimate motor constraint rows overall.

Corrected per-block counts (extraction now == workbook):

| Series scope | Block | Rows |
|---|---|---|
| 1500 and 1600 | Alt_Size x F_Frame_Size | 282 |
| 1500 and 1600 | Alt_Size x F_MotorHpRpm | 525 |
| 1500 and 1600 | F_Frame_Size x F_MotorHpRpm | 55 |
| 1500 and 1600 | F_MotorHpRpm x F_Motor Type | 170 |
| 1530 and 1630 | Alt_Size x F_Frame_Size | 152 |
| 1530 and 1630 | Alt_Size x F_MotorHpRpm | 375 |
| 1530 and 1630 | F_Frame_Size x F_MotorHpRpm | 38 |
| 2530 | Alt_Size x F_Frame_Size | 96 |
| 2530 | Alt_Size x F_MotorHpRpm | 200 |
| 2530 | F_Frame_Size x F_MotorHpRpm | 40 |
| 3000 | Alt_Size x F_Frame_Size | 76 |
| 3000 | Alt_Size x F_MotorHpRpm | 78 |
| 3000 | F_Frame_Size x F_MotorHpRpm | 56 |
| 5500 | Alt_Size x F_Frame_Size | 201 |
| 5500 | Alt_Size x F_MotorHpRpm | 417 |
| 5500 | F_Frame_Size x F_MotorHpRpm | 50 |
| 5530 | Alt_Size x F_Frame_Size | 134 |
| 5530 | Alt_Size x F_MotorHpRpm | 303 |
| 5530 | F_Frame_Size x F_MotorHpRpm | 30 |

**Total: 3278 rows (was 2401).** The fix removed the artificial row cap; each
block now stops dynamically at its first blank key cell.

Note: `FYBROC_MOTOR_CONSTRAINT_MODEL.json` is currently an evidence artifact —
no SQL loader consumes it yet, so these motor constraints are not enforced at
runtime. Wiring a loader (parallel to `load_constraints_to_sql.py`) is a
separate integration step, not done here.

## 5. Combine Variables sheet — audit

The `Combine Variables` sheet (120 x 36) is extracted by
`compile_fybroc_motor_constraint_model.py` into 4 tables. Column positions all
match the workbook's row-3 headers.

**3 of 4 tables verified correct** (genuine row-aligned key -> value mappings):

- `MotorHpRpm_to_HpAndRpm` (key col 5 -> cols 6,7): 56 rows, e.g. `"1-1200"` ->
  Hp `1`, RPM `1200`. Correct decomposition of the composite HpRpm key.
- `MotorMfg_to_MotorOption` (col 19 -> 20): 4 rows. Correct.
- `WettedHardware_to_ShaftMaterial` (col 24 -> 25): 2 rows. Correct.

**1 table mismodeled - flagged for engineering decision:
`MotorType_decomposition` (key col 10, value cols 12-17).**

The extractor treats `MotorType` (col 10) as a key row-aligned to the six
value columns and stops at the key column's 5 entries (row 8). That
row-alignment is coincidental and semantically wrong. The actual layout of that
region is:

- **Rows 4-22 (cols 10-17): independent per-attribute VALUE DOMAINS**, not a
  row-aligned mapping. Each column is its own list of valid values:
  MotorType (5), F_MotorEnclosure (3: TEFC/TEFC_SD/IEEE_841),
  F_MotorEfficiency (1: PE), F_MotorVoltage (3), F_MotorHertz (2),
  F_MotorHp (19: 1..200), F_MotorRPM (4: 900/1200/1800/3600).
- **Rows 24-77 (cols 12-16): a separate 54-row COMBINATION ENUMERATION** of
  `(Enclosure, Efficiency, Voltage, Hertz, ...)` = the full TEFC/TEFC_SD x
  voltage x voltage x 50/60hz cartesian. The extractor misses this block
  entirely (it stopped at row 8). No MotorType key sits alongside it (cols
  9-11 blank).

### Resolution (informed by V6 ' Motor Assy')

The V6 `' Motor Assy'` sheet clarifies the model. Its display section (rows
3-8) lays out the **11 motor attributes as independent domain columns**
(Motor Option, Motor Class, Motor Orientation, Motor Horsepower, Motor RPM,
Motor Voltage, Motor Hertz, Motor Frame, Motor Enclosure, Motor Efficiency,
Motor Manufacturer) - exactly the same "per-attribute value list" shape. Its
data section (rows 27-728) is the enumerated valid motor combinations, where
`C` concatenates all 11 attributes into a key and a base-36 ID becomes the
hex code.

Cross-checking Rev0.3 confirmed the MotorType columns are NOT row-aligned: row
4's `F_MotorVoltage='230'` / `F_MotorHertz='3ph - 50 hz'` do not decompose the
MotorType `TEFC_PE_230/460-3-60` (which encodes 230/460 and 3-60). They are the
first entries of each attribute's independent domain list.

**Correction applied.** `compile_fybroc_motor_constraint_model.py` now models
the MotorType region as `MotorType_domains` - independent per-attribute value
domains, each column read to its own first blank:

| Attribute | Values |
|---|---|
| MotorType | 5 (TEFC_PE_230/460-3-60 ...) |
| F_MotorEnclosure | 3 (TEFC, TEFC_SD, IEEE_841) |
| F_MotorEfficiency | 1 (PE) |
| F_MotorVoltage | 3 (230, 230/460, 460) |
| F_MotorHertz | 2 (50 hz, 60 hz) |
| F_MotorHp | 19 (1 .. 200) |
| F_MotorRPM | 4 (900, 1200, 1800, 3600) |

The prior 5-row row-aligned `MotorType_decomposition` is removed. The three
genuine key->value tables (MotorHpRpm, MotorMfg, WettedHardware) are unchanged
and correct. The output now carries `combine_variable_tables` (key->value) and
`combine_value_domain_tables` (the MotorType domains) separately.

Note on the row-24-77 enumeration: it is the (Enclosure, Efficiency, Voltage,
Hertz) combination expansion the workbook uses as a pricing/reference aid (per
the adjacent note cell). It is the same universe V6 ' Motor Assy' enumerates in
its data section with hex codes; the authoritative motor combination + hex
mapping is consumed from V6 ' Motor Assy' (via the segment-combination
compiler), so it is not re-extracted from this Rev0.3 helper block.

## 6. Items + Hierarchy sheets — audit + correction

Extracted by `compile_fybroc_items_hierarchy_model.py` (F120.1).

### Items — truncation defect found and fixed

The `Items` sheet (17285 x 92) main table holds one row per `(series, item)`
with a `{series}_{item}` composite key in col A and 35 `F_*` field-flag
columns (cols 5-39) carrying `X` where a field applies.

The extractor had `ITEMS_DATA_END_ROW = 99` (comment: "last populated row in
the main table"). That was wrong: the main table runs continuously from row 3
to **row 469 (467 rows)** - every row has a real composite key (e.g. row 100
`7500_6A`, row 469 `8500_NP2`). The 99 cap captured only **97 of 467 rows**,
dropping ~370 item records and badly skewing per-series coverage (the longer
series 5500/7500/8500 were mostly lost).

Fixed: removed the fixed cap; the loop now reads dynamically and stops at the
first blank col-A key. Verified per-series counts now match an independent
workbook scan exactly:

| Series | Items | | Series | Items |
|---|---|---|---|---|
| 1500 | 32 | | 3000 | 29 |
| 1530 | 36 | | 5500 | 82 |
| 1600 | 34 | | 5530 | 44 |
| 1630 | 38 | | 7500 | 68 |
| 2530 | 28 | | 8500 | 76 |

Total: **467 rows (was 97)**. The deliberate `not_compiled` exclusion of cols
66-88 (the per-series item-code cross-reference block, which carries an
explicit in-sheet engineering warning that row position does not align items
across series) is unchanged and intentional.

### Hierarchy — verified correct, no change

The `Hierarchy` sheet (14 x 23) defines 8 field groups. All 8 groups and their
fields match the workbook exactly, including the Impeller group which has a gap
(ImpellerTrim, Dynamic Impeller in rows 2-3, then Trim Range at row 14) that
the extractor captures correctly:

| Group | Fields |
|---|---|
| Pump Options | 12 |
| Impeller | 3 (incl. Trim Range at row 14) |
| Mechanical Seal | 9 |
| Motor | 11 |
| Baseplate | 4 |
| Mounting plate | 1 |
| Vertical | 6 |
| Other | 2 |

No correction needed for Hierarchy.

## 7. Row-cap sweep across all Fybroc compilers

Motivation: three separate extractors (Motor Constraints, Combine Variables,
Items) shared the same defect - a hardcoded row cap with a "verified: last
populated row is N" comment that was only true for part of the data. This
sweep checked every remaining compiler's hardcoded row bound against the true
data extent in the authoritative workbook (scanning 500 rows past each cap to
confirm nothing is cut off).

| Compiler / bound | True last data row | Cap | Result |
|---|---|---|---|
| v6_testing DATA_END_ROW | 69 | 70 | OK |
| v6_setting_length DATA_END | 206 | 684 | OK |
| v6_seal_assembly DATA_END_ROW | 80 | 80 | OK (exact) |
| v6_options_vertical DATA_END_ROW | 107 | 107 | OK (exact) |
| v6_options_horizontal DATA_END_ROW | 203 | 203 | OK (exact) |
| v6_attributes TRIM_DATA_END (col P) | 104 | 104 | OK (exact) |
| v6_attributes SIZE_TRIM_END (col AP) | 523 | 523 | OK (exact) |
| v6_motor_assy data end (key col C) | 728 | 728 | OK (exact) |
| v6_pump_options_horizontal DATA_END_ROW | 138251 | 138251 | OK (exact, = sheet end) |
| v6_pump_options_vertical DATA_END_ROW | 23053 | 23053 | OK (exact, = sheet end) |
| selections DATA_END_ROW (Question col B) | 678 | 678 | OK (exact) |

All remaining caps are correct today (data ends at or before the cap). Several
sit exactly at the true end; the V6 segment/attribute compilers additionally
break at the first blank key/hex cell, so they are robust to those bounds. No
further truncation defects found.

Fixed defects (documented above): Motor Constraints (210 -> dynamic, +877
rows), Items (99 -> dynamic, +370 rows), Combine Variables MotorType
(row-aligned mis-model -> value domains). These three were the only compilers
whose caps were BELOW the true data extent.

## 8. Sheet3 — the workbook's own validation harness (confirms our model)

`Sheet3` (99 x 47) is not a data source - it is a **worked example** the
workbook uses to demonstrate per-series option resolution, computed live for
series 1500. Row 2 lists the 46 applicable question labels; each column below
spills the valid answers via:

    =CHOOSECOLS(
        FILTER(QATable[],
               ((QATable[1500]="X") + (QATable[1500]="STD")) * (QATable[Question]=<label>)),
        2)

Three things this confirms directly from the authoritative workbook:

1. **Resolution rule = marker is "X" OR "STD".** The FILTER predicate
   `((...="X")+(...="STD"))` is exactly the availability rule our loaders use
   (`load_all_series.py` keeps X and STD, treats STD as the default). Sheet3
   validates the STD three-state handling end-to-end.

2. **QATable = the Selections sheet.** The `QATable` table is defined as
   `Selections!B1:M678` (columns Question / Answers / per-series 1500..8500).
   So Sheet3 exercises the SAME source our extraction consumes - not a
   separate dataset.

3. **Testing fields captured correctly.** Sheet3 exposes the four testing
   fields with their Non-Wit / Wit interpretations; all are present in
   cfg.SeriesFieldOption with the right STD default:
     - Performance Testing (5): Not Included [STD], Non-Wit Perf Test,
       Wit Perf Test, Non-Wit Perf Test NPSHR, Wit Perf Test NPSHR
     - Hydrotest Certificate (3): Not Included [STD], Non-Wit / Wit Hydro Test Certificate
     - Sound Level Testing (3): Not Included [STD], Non-Wit / Wit Sound Level Testing
     - Vibration Testing (3): Not Included [STD], Non-Wit / Wit Vibration Testing

Verified against the live DB (series 1500): all four testing fields match Sheet3
exactly in option set and STD default. No correction was required - Sheet3
serves as an independent confirmation that the Selections extraction, the
X/STD semantics, and the testing-field interpretations are all correct.

## 9. Combine Variables — formula-verified relationship audit (Mfg/Option, Wetted/Shaft)

Driven by the authoritative formula inventory
(`FYBROC_FORMULA_INVENTORY.{json,txt}`), which enumerates every formula and
defined name in Rev0.3 + V6 so constraints are built from the workbook's own
logic, not inferred from data shapes.

The prior `compile_fybroc_motor_constraint_model.py` declared THREE key->value
relationships on the Combine Variables sheet:

| Declared relationship | Verdict | Evidence |
|---|---|---|
| `MotorHpRpm_to_HpAndRpm` | **REAL** (kept) | Composite key col E split by formulas `F4=TEXTBEFORE(E4,"-")`, `G4=TEXTAFTER(E4,"-")`; 56 genuinely row-aligned pairs. Cross-checked: the 56 composites == the 56 F_MotorHpRpm values used in Motor Constraints exactly; illegal `1-3600` appears in neither. |
| `MotorMfg_to_MotorOption` | **ARTIFACT** (removed) | Cols S/T are NOT paired. Each is an independent ArrayFormula spill from the QATable: `=CHOOSECOLS(FILTER(QATable[],QATable[Question]=<hdr>),2)`. Lengths differ (Mfg=4, Option=3). Both "Motor Mfg" and "Motor Option" are separate QATable Questions. The false row-pairing produced a phantom `Toshiba -> (blank)` that would have wrongly filtered Motor Option to empty when Toshiba is selected. |
| `WettedHardware_to_ShaftMaterial` | **ARTIFACT** (removed) | Same defect. Col X (Wetted Hardware) is a QATable spill of 2 values; the adjacent Shaft Material domain is a separate 7-value list. Lengths differ (2 vs 7). Not row-aligned. |

Correction applied:
- `COMBINE_KEY_VALUE_TABLES` now contains ONLY `MotorHpRpm_to_HpAndRpm`.
- Motor Mfg (4), Motor Option (3), Wetted Hardware (2), Shaft Material (7) moved
  to `COMBINE_VALUE_DOMAIN_TABLES` as independent per-attribute domains
  (`MotorMfgOption_domains`, `WettedHardwareShaft_domains`), matching how the
  MotorType region is already modeled.

Runtime effect (live DB, pub_id=2, FYBROC family_id=2):
- `cfg.CombineVariable`: 118 -> **112** (only the real MotorHpRpm relationship;
  the 4 + 2 fabricated pair-rows removed).
- `cfg.CombineValueDomain`: 37 -> **53** (added Motor Mfg 4, Motor Option 3,
  Wetted Hardware 2, Shaft Material 7).

No enforcement code was added for Mfg/Option or Wetted/Shaft because no such
cross-field constraint exists in the workbook. The only Combine Variables
constraint enforced in the evaluate endpoint remains Hp -> RPM (verified:
1 HP -> [1200, 1800]; 2 HP -> [1200, 1800, 3600]).

Lesson (why formula-first matters): both artifacts came from row-zipping
side-by-side but independent spill columns. Reading the FORMULAS (spill source
= QATable filter) and the COLUMN LENGTHS (unequal => cannot be paired)
distinguishes a real row-aligned mapping from two coincidentally-adjacent
domains. This is exactly the class of guess the formula inventory exists to
prevent.

## 10. "Blank = not allowed" audit + the FLANGE_TYPE apparent-discrepancy (V6 authority)

Prompted by the engineering rule: on Selections, a per-series marker of X or STD
means the option is allowed; a BLANK means NOT allowed. We audited whether the
runtime honors this at the option-row level and whether any allowed option was
lost.

Audit method: for each series, count workbook X/STD-allowed (question, answer)
pairs and compare to cfg.SeriesFieldOption. Also verified the export CSV
(exports/fybroc_series_constraint_candidates.csv) contains exactly the X/STD
pairs and no blank-marked ones.

Findings:
- The blank rule is honored: no blank-marked option leaked into the DB; the CSV
  export equals the workbook's X/STD set exactly (e.g. 1500=290, 2530=180,
  5500=571).
- Per-series field counts match the Selections Q:AA applicability for all 10
  series (see Section 8 / Q:AA audit).
- Per-series OPTION counts matched for 8/10 series. 2530 and 5500 were each
  short by exactly 2. Traced to ONE field: FLANGE_TYPE. Rev0.3 Selections marks
  all three flange answers allowed for 2530 and 5500 (ANSI=STD, DIN/ISO=X,
  JIS=X), but the DB offers only ANSI for those series.

Verdict: NOT a defect. This is the intentional, documented V6 flange authority.
- The runtime loader `scripts/load_all_series.py` applies a V6-authoritative
  rule: DIN/ISO and JIS are offered ONLY for series 1500/1530/1600/1630; all
  other series are ANSI-only.
- Verified directly against V6 (`Nomenclature_V6.xlsm` Attributes Series+Flange
  code table, rows 23-42): DIN codes (I,J,K,L) and JIS codes (M,N,O,P) exist
  ONLY for 1500/1530/1600/1630. 2530 (E), 3000 (F), 5500 (G) and the vertical
  series have ANSI only - no DIN/JIS code exists. Offering DIN/JIS for 2530/5500
  would generate a #N/A part number.
- V6 governs over Rev0.3 Selections, which is over-permissive on flange. The DB
  is correct as-is.

Loader-of-record note (important for future reloads): the ACTIVE publication
(pub_id=2) is produced by `scripts/load_all_series.py`, NOT by
`scripts/load_and_publish_fybroc_series_constraints.py` (the CSV loader). Only
load_all_series.py (a) applies the V6 flange authority, (b) populates the
SelectionMarker / IsStandard three-state, and (c) lowercases option values. A
reload from the CSV path would REINTRODUCE the over-permissive DIN/JIS options
for 2530/5500 and drop the marker columns. Always reload SeriesFieldOption via
load_all_series.py.

## 11. V6 Motor Assy Hertz->Voltage / Hertz->RPM (R2/R3): extracted, NOT runtime-enforced

The V6 ' Motor Assy' sheet was re-extracted to capture all five regions
(scripts/compile_fybroc_v6_motor_assy.py -> docs/evidence/F110/
FYBROC_V6_MOTOR_ASSY.{json,txt}), correcting a prior version that read only the
first 6 option rows and dropped the '-' value. New evidence includes:
  R1  option domains (D2:Q21), '-' preserved
  R2  Hertz -> Voltage (U2:V17)
  R3  Hertz -> RPM (U20:V34)
  R4  Frame+Hp+RPM -> hex (Z2:AD52, 50 rows)
  R5  combination -> hex (C26:P728, 702 rows)

We audited whether R2/R3 should be enforced as runtime selection constraints
(like the Rev0.3 Combine Variables Hp->RPM rule). Conclusion: NO - enforcing
them would be incorrect. Reasons:

1. Different authority / scope. R2/R3 describe the full V6 motor NOMENCLATURE
   catalog (every hertz/voltage/RPM the part-number encoding supports). The
   AUTHORITATIVE runtime offering is Rev0.3 Selections, which is far narrower:
     - MOTOR_HERTZ runtime = {3ph - 60 hz, 3ph - 50 hz} only (no 3/(50/60)).
     - MOTOR_VOLTAGE runtime = {230, 230/460, 460, custom} (V6 lists ~16).
     - MOTOR_RPM runtime = {900,1200,1800,3600} - the 60hz set only; the 50hz
       RPMs (3000/1500/1000) are NEVER offered.
   So there is nothing for a Hertz->RPM/Voltage allow-list to remove, and V6's
   vocabulary doesn't even contain runtime values like 'custom' - filtering by
   it would wrongly delete valid options.

2. Opposite hierarchy direction. In the Rev0.3 runtime field hierarchy the
   order is MOTOR_RPM -> MOTOR_VOLTAGE -> MOTOR_HERTZ, i.e. Hertz is selected
   AFTER RPM and Voltage. R2/R3 model Hertz as the DRIVER, so a Hertz->RPM/
   Voltage gate cannot apply to fields already chosen upstream.

3. Verified live: MOTOR_RPM options are {1200,1800} at its step for both 1500
   and 5500 (further narrowed by the Hp->RPM rule), all from the 60hz set; no
   50hz-specific RPM/voltage is ever selectable, on any series.

R2/R3 remain authoritative for the V6 part-number ENCODING (they feed the
motor-assembly hex lookup, R5), and are preserved in the evidence. They are not
loaded as cfg constraints and not enforced in the evaluate endpoint, because the
runtime motor domains (Rev0.3 Selections) are the narrower authoritative source
and already internally consistent. This mirrors the V6 flange-authority finding
(Section 10): V6 governs the encoding; Rev0.3 Selections governs what is offered.

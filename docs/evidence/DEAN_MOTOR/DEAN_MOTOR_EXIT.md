# Dean Motor Numbering - Evidence

**Source:** `workbooks/Dean/Motor Numbering.xlsm`, sheet `Pricing` only (`Constraints` and `Base Codes` ignored, owner 2026-08-27).

| Range | Meaning | Loaded into |
|---|---|---|
| `A1:AC72` | Selectable options per motor field (header row 1) | `cfg.SeriesFieldOption` (Dean, series level) via `scripts/load_dean_motor_options.py` |
| `R98:AD34179` | Selectable motor combinations: spec (S..AB), Alphanumeric Code (AC), Price or `C.F.` (AD) | `stg.SegmentCombinationImport` (`MOTOR_SPEC`) + `price.DeanMotorPrice` via `scripts/load_dean_motor_numbering.py` |

## What changed
- **Options** come from `A1:AC72` for the 9 motor fields (Motor, Motor Control, Rated Speed, Rated Power, Voltage, Phase/Frequency, Enclosure, Efficiency, Brand) on every Dean series. Previously they were derived from the combinations; values are identical, but the block is now the authority. `d110` calls the same loader, so a Pump Constraints re-ingest no longer leaves the motor fields empty.
- **Motor STD = `Included`**, and the configurator auto-selects Motor = `Included` whenever the chosen Pump Configuration includes a motor (fresh seed and on change; reported in `reset_fields`). Bundles without a motor drop all motor fields.
- **Frame sizes** stay per series and size from Pump Constraints (owner: most series have frame sizes, some do not). Series with none: `M300 (FRAME III)`, `RM5140`, `RMA5140`. The configurator shows a series' Pump Constraints frames that have a motor combination.
- **Combination range** is now rows 98..34179 (was 96..34179). Rows 96-97 (`B001`, `L001`) are not loaded. 34,082 combinations; 491 priced, 33,591 `C.F.` (engineering prices them at quote review).
- **Permutation numbers regenerated.** Workbook column R repeats one number per spec across all 9 brands (3,955 distinct values for 34,082 rows), so it cannot identify a combination. The loader walks the rows in sheet order, keeps the earlier row if a spec (all 10 values) or a code repeats (none do), and numbers the kept rows 1..34,082. The number is stored as `stg.SegmentCombinationImport.SourceId` and the new nullable column `price.DeanMotorPrice.PermutationNo`; the workbook's R value is kept in `SourceCellsJson.workbook_permutation` for traceability. Codes are unchanged.

## Verification
- `scripts/audit_dean_motor.py` (new) 20/20: option sets == `A1:AC72`; Motor STD only `Included`; FRAME_SIZE per (series, size) == Pump Constraints (206 models); block values == combination values; 34,082 combinations with unique codes and specs; rows 96-97 not loaded; permutations 1..N increasing and unique; price row and matching PermutationNo for every code; motor bundle seeds and auto-selects `Included`; non-motor bundles carry no motor fields; frame options == Pump Constraints frames with a combination (all 37 series); priced spec -> PN `...-T00T` with Motor 661.23, `C.F.` spec -> PN `...-M001` with Motor C/F; non-Dean counts unchanged.
- Regression: `audit_dean_motor_numbering` 27/0 (expected counts updated to the new range; series compared case-insensitively since Pump Model Reference spells `DEANLINE`), `audit_dean_revision` 15/15, `audit_dean_config` 28/0, `audit_dean_wet_end_resolve` 33/0, `audit_cpq_u3` 20/20, `audit_cpq_u4` 17/17, `audit_cpq_a2` 11/11, `audit_dean_seal` 115/115, `audit_dean_seal_options` PASS. DEAN `stg.SegmentCombinationImport` watermark 140,976 -> 140,974 (the two dropped rows).

- Fybroc gate `run_all_fybroc_audits.py`: ALL CORRECTIONS INTACT (9/9), run because `src/api/v2_routes.py` is shared.

## Known gaps
- 16 Pump Constraints frame sizes have no motor combination (`364T`, `365T`, `404T`, `405T`, `444T`, `445T`, `447T`, `449T` and TS/TSC/TC variants, plus `C/F` on 33 series). They are not offered for selection; a pump with such a frame cannot carry a motor code.
- The Pricing block has 5 frame values that no series offers (`143TCZ`, `145TCZ`, `405HP`, `444HP`, `445HP`).
- Motor Control, Efficiency and Motor have a single value each in the workbook.

## Reproduce
```
uv run python scripts/load_dean_motor_numbering.py   # combinations, price, options
$env:PYTHONPATH="."; uv run python scripts/audit_dean_motor.py   # API on 127.0.0.1:8080
```

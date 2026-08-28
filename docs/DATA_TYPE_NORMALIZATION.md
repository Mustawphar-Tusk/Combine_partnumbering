# Series Data-Type Normalization (Fybroc)

## Scope

This note documents ONE specific, deliberate type correction: normalizing the
Fybroc **series code** to a consistent application type. It is not a
general-purpose normalization layer; only the series-typing issue described
below is addressed.

## The workbook inconsistency

The authoritative `Nomenclature_V6.xlsm` **Attributes** sheet holds the
Series+Flange -> Code table (rows 23-42). Its series values are stored with
inconsistent cell types:

- **TEXT:** `1500`, `1530`, `1600`, `1630`, `5530`, `6000`, `7500`, `7530`, `8500`
- **INTEGER:** `2530`, `3000`, `5500`

This is a hand-built-spreadsheet data-entry artifact. The workbook remains the
authoritative source of series *values*; only their *type* is inconsistent.

## The correction

The application's canonical type for a series code is **TEXT** (bare digits,
e.g. `"5500"`). All ingestion of series values goes through
`src/compiler/workbook_types.norm_series`, which converts an integer or whole
float (`5500`, `5500.0`) to the text `"5500"` and leaves already-text series
unchanged. Downstream (`cfg.SeriesFieldOption.SeriesCode`, the API, the
configuration map) a series is always the same string.

Applied in:
- `scripts/load_all_series.py` — series read from the Rev0.3 Selections header
  is normalized via `norm_series` before loading `cfg.SeriesFieldOption`.

## Related harness accommodation (F170)

`scripts/fybroc_regression_f170.py` writes values back INTO a disposable copy
of the workbook to drive its native XLOOKUP formulas. Because those formulas
compare against the raw (mixed-type) Attributes cells, the harness must write
each series with the type the lookup table stores — integer for
`2530/3000/5500`, text otherwise (`SERIES_STORED_AS_INT`). This is a
**harness-only** accommodation of the workbook's inconsistency and does not
change the canonical application type, which remains text everywhere else.

Additionally, the F170 harness is orientation-aware: horizontal series
(`1500/1530/1600/1630/2530/3000`) use the Smart Number horizontal input/output
cells, while vertical series (`5500/5530/6000/7500/7530/8500`) use the vertical
cells (input row 39/40, part number at D34, segment codes row 38).

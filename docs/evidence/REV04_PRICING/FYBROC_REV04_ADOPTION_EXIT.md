# Fybroc Rev0.4 Pricing Adoption — EXIT

**Source:** `workbooks/Fybroc/Fybroc Configuration Rev0.4.xlsx` (authoritative per
engineering; read-only / disposable copies only).
**Model:** series-gated overlay (option 2b), agreed with product owner.

## What was done

### 1. Rev0.4 is the authoritative pricing source for the completed series
Rev0.4 pricing is adopted **only for series 1500 & 5500** (both largely complete
per engineering's Pricing Index). All other series (1530, 1550, 1600, 1630, 1650,
2530, 2580, 2630, 3000) **retain their Price-Estimator prices**.

Overlay rule within 1500/5500:
- Rev0.4 **`found`** (determined) price → **updates** the price.
- Rev0.4 **`C/F` (Contact Factory)** → does **not** overwrite; the existing
  Price-Estimator price is retained where one exists, otherwise the configuration
  is Contact-Factory (no priced row; runtime returns call-for-price by default).

### 2. Merged publication (current)
`FYBROC-REV04-MERGE-20260914-V1` — 56,241 rules (56,088 found + 153 call-for-price).
Built by `scripts/merge_rev04_over_price_estimator.py`: the preserved
Price-Estimator baseline (`FYBROC-CONFIG-20260807-V3`) overlaid with Rev0.4 `found`
prices for 1500 & 5500. **All prior publications are preserved non-current**
(non-destructive supersession): Price-Estimator V1/V2/V3, DEV1, and the interim
Rev0.4-only `FYBROC-REV04-20260914-V1`.

Verified by `sql/25_Verify_Rev04_Pricing_Publication.sql` (PASSED: counts + source +
V3 preserved non-current).

### 3. Difference document
`docs/evidence/REV04_PRICING/REV04_vs_PriceEstimator_DIFF.md` (+ machine-readable
`exports/fybroc_merge_classification.json`). Highlights:
- **1500 BASE_PUMP**: 109 unchanged, **0 changed**, 21 retained (materials Rev0.4
  hasn't priced: VR-1V BPO/DMA, and two EY-2 at $0). Rev0.4's 1500 base prices
  **match Price-Estimator exactly** where both have them.
- **1500 SEAL**: 646 V3 rows superseded by the Rev0.4 series-independent seal table
  (decision a).
- **New from Rev0.4**: every non-BASE/SEAL component (sleeve, hardware, coupling,
  baseplate, flush, testing, adders, motor, tailpipe) and all 5500 pricing — the
  Price-Estimator had none of these.

### 4. How the sources are structured (evidence)
`docs/evidence/REV04_PRICING/REV04_PRICING_MAP.md` documents the Rev0.4 column-block
pricing layout (row-3 description, row-5 headers `[Series] Alt Size <fields> Price`,
row-6+ data), the flat Motor tables, and the block→ComponentCode map.

### 5. Runtime pricing (Phase B — complete)
The resolve endpoint prices, in addition to Base Pump + Seal:

**Single-option adders** (keyed by series + size + one selection value): Sleeve,
Shaft Material, Gland/Casing/Power-Frame/Baseplate hardware, Bearing, Coupling
Guard, Flange Type, Cyclone Separator, Casing Drains, Suction/Discharge Taps, Seal
Guard, Performance/Vibration/Sound testing, Pump Elastomers, Hydrotest, Impeller
Balance.

**Multi-condition components** (matched against `price.PriceCondition` — every
condition must equal the resolved selection): MOTOR (enclosure × efficiency ×
voltage × hertz × hp × rpm × frame × mfg × shaft-grounding × paint), COUPLING
(size × hp-rpm × frame × coupling-option; 5500 uses F_* variants), BASEPLATE
(size × frame × baseplate-option), TAILPIPE (size × material × wetted-hardware ×
length). Matching is done in SQL via `NOT EXISTS (a condition with no matching
selection)` over an `OPENJSON` array of the resolved selections — no per-rule IN
list, so it scales to the 46k-row TAILPIPE table. Derived condition fields are
resolved at runtime (`F_MOTORHPRPM = MOTOR_HP-MOTOR_RPM`, `F_FRAME_SIZE`,
`F_COUPLING_OPTION`). A config whose selections don't match any rule simply isn't
priced for that component (Contact-Factory / not-yet-determined = runtime default).

Verified against known workbook values: MOTOR 2779.48, BASEPLATE 2258, COUPLING
771, TAILPIPE 4087 all flow through resolve correctly.

Note: MOTOR is 290 priced of ~294k combinations — the rest are Contact-Factory by
engineering's own model, so most motor selections correctly resolve to
call-for-price.

## Verification
- Correction gate `run_all_fybroc_audits.py`: **ALL CORRECTIONS INTACT**
  (selections 2096, feasible 14/14, motor 91/91, identifier 44/44, BOM 38/38,
  quote 22/22).
- Rev0.4 publication verification `sql/25`: PASSED.
- Runtime: 1500 config returns Base Pump + priced adders from Rev0.4.

## Reproduce
```
# compile Rev0.4 found prices (all components, series 1500/5500 + family adders)
python scripts/compile_fybroc_rev04_pricing.py --all --found-only
# build the 2b overlay merge against the preserved Price-Estimator baseline
python scripts/merge_rev04_over_price_estimator.py
# publish the merged set as a new current version
python scripts/publish_fybroc_combined_pricing.py \
    --version-code FYBROC-REV04-MERGE-<date>-V1 --effective-from <date> \
    --input exports/fybroc_merged_pricing.json
# regenerate the difference document
python scripts/build_rev04_diff_doc.py
```
Note: `exports/*.json` are gitignored build artifacts (regenerable by the above).

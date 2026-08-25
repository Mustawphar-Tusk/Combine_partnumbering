# Engineering Note: Fybroc Configuration Platform — Status & Open Items

**Date:** August 25, 2026  
**From:** Configuration Platform Development Team  
**To:** Engineering Team  
**Subject:** Fybroc Configurator — Completion Summary, Known Gaps, and Engineering Decisions Needed

---

## 1. Summary

The Fybroc pump configuration platform is now operational across all 10 configurable series. The system generates Part Numbers, SKUs, enforces engineering constraints, and returns pricing — all from a single API that serves both the Excel VBA client and the React web UI identically.

**Automated testing confirms 100% Part Number resolution across all series.**

---

## 2. What Has Been Completed

### Configuration Engine
- All 10 series loaded from Rev0.3 Selections and V6 Nomenclature
- 4,440 feasibility constraint rules enforced (from Rev0.3 FeasibleConstraint + ConstraintTable3/6)
- Progressive field hierarchy — users cannot skip ahead; each field must be selected in engineering order
- Configuration dependencies respected (e.g., impeller trim constraints per size/material)

### Part Number Generation
- All Part Number segments resolve for every series
- Horizontal format: `<Brand><Series><Size><Material><Trim>-<PumpOpts>-<SealMfg><SealAssy>-<Options>-<Frame><MotorAssy>-<MotorMods>-<Testing>`
- Vertical format: `<Brand><Series><Size><Material><Trim>-<PumpOpts>-<Options>-<Frame><MotorAssy>-<MotorMods>-<Testing>` (seal segment correctly omitted)
- 702-row Motor Assembly combination table fully wired
- 134-row Seal Assembly combination table fully wired
- 23,040-row Vertical Pump Options combination table fully wired
- Horizontal Pump Options combination table fully wired
- Testing combination table (60 rows) fully wired
- Motor Modifications (31 codes) fully wired

### SKU Generation
- Format: `F<Series>-<8char><VersionLetter>` (e.g., `F1500-A1B2C3D4A`)
- Deterministic from SHA-256 configuration signature
- 1:1 mapping: SKU → Part Number → Configuration → BOM
- Reuse detection: identical configurations return the same SKU

### Pricing
- Price Estimator-Fybroc.xlsm is the authoritative pricing source
- Base pump pricing loaded for all series with pricing data
- Pricing matches verified (109/109 match between Rev0.3 and Price Estimator for series 1500)

### Constraint Enforcement
- Feasible constraints prevent invalid field combinations
- 20 constraint tables compiled from Rev0.3
- ConstraintTable3 and ConstraintTable6 correctly applied to series 5500 only

### API
- 4 V2 endpoints: dictionary, evaluate, validate, resolve
- In-memory caching (5-min TTL) for configuration dictionary
- Client-agnostic: same request/response for Excel and React

---

## 3. Test Results (Automated Bulk Testing — August 25, 2026)

| Series | Orientation | PN Resolution | Pricing Hit Rate | Notes |
|--------|-------------|:-------------:|:----------------:|-------|
| 1500 | Horizontal | 100% | 90% | Some DIN/JIS flange combos outside pricing range |
| 1530 | Horizontal | 100% | 100% | |
| 1600 | Horizontal | 100% | 80% | Some size/material combos outside pricing range |
| 1630 | Horizontal | 100% | 80% | Same as 1600 |
| 2530 | Horizontal | 100% | 100% | No seal configuration (correct — series has no seal) |
| 3000 | Horizontal | 100% | 100% | |
| 5500 | Vertical | 100% | 80% | Some vertical combos outside pricing range |
| 5530 | Vertical | 100% | 100% | |
| 7500 | Vertical | 100% | 10% | Only 1 pricing rule defined (limited size coverage) |
| 8500 | Vertical | 100% | 0% | No pricing rules exist in Pricebook |

---

## 4. What Still Needs Engineering Input

### 4.1 — Series 6000 and 7530: Configuration Data Missing

**Issue:** Series 6000 (V6 code Q) and 7530 (V6 code S) exist in V6 Nomenclature and have pricing in the Price Estimator Pricebook, but Rev0.3 defines ZERO configuration options for them.

**What we need from engineering:**
- Are 6000 and 7530 active production series that customers currently order?
- If yes, where are the field options (sizes, materials, etc.) documented?
- If no, should they be excluded from the configurator?

Without configuration options, these series cannot be included. The platform is ready to load them as soon as options are defined.

---

### 4.2 — Series 8500: No Pricing Rules

**Issue:** Series 8500 has configuration options loaded (7 fields) and resolves Part Numbers successfully, but no pricing rules exist in the Price Estimator Pricebook.

**What we need from engineering:**
- Does series 8500 have production pricing?
- If yes, where is it documented?
- If pricing is not applicable (e.g., quote-only series), should the configurator indicate "pricing on request"?

---

### 4.3 — Series 7500: Limited Pricing Coverage

**Issue:** Series 7500 has only 1 pricing rule in the Pricebook. Only 10% of random configurations match a price. Most size combinations are not covered.

**What we need from engineering:**
- Is the 7500 Pricebook block intentionally limited to one size/material combination?
- Are additional 7500 prices available elsewhere?

---

### 4.4 — Series 2530: No Seal Assembly Configuration

**Issue:** Series 2530 has no SEAL_OPTION, SEAL_TYPE, or any seal-related fields in Rev0.3. The configurator defaults to "noseal" for this series.

**What we need from engineering:**
- Confirm: Is it correct that 2530 pumps do not have user-selectable seal assemblies?
- If seals are configurable for 2530, where are the options defined?

---

### 4.5 — Pricing Gaps for DIN/JIS Flanges (Series 1500, 1600, 1630)

**Issue:** The Price Estimator Pricebook covers ANSI flange configurations well (90-100% hit rate), but some DIN/JIS flange + size + material combinations don't match any pricing rule.

**What we need from engineering:**
- Are DIN/JIS configurations priced differently from ANSI?
- Is there a separate pricing source for non-ANSI flanges?
- Or should DIN/JIS use the same base prices as ANSI equivalent?

---

### 4.6 — Series 2630: Legacy or Active?

**Issue:** Series 2630 appears in the Price Estimator Pricebook but not in V6 Nomenclature or Rev0.3 Selections. It has no V6 identifier code and no configuration options.

**What we need from engineering:**
- Is 2630 a legacy series that should be excluded?
- Or is it an active series that needs configuration data defined?

---

## 5. Remaining Platform Work (No Engineering Input Needed)

These items are development tasks that do not require engineering decisions:

- Performance optimization for vertical PUMP_OPTIONS lookups (23K row table, ~9s per query)
- React UI polish and field grouping
- Dean configuration integration (same architecture, different metadata)
- Azure TEST environment deployment
- UAT preparation

---

## 6. Data Sources Used

| Source | Purpose | Status |
|--------|---------|--------|
| Nomenclature_V6.xlsm | Identifier codes, combination tables | Fully compiled |
| Fybroc Configuration Rev0.3.xlsx | Configuration options, constraints, dependencies | Fully compiled |
| Price Estimator-Fybroc.xlsm | Authoritative production pricing | Fully loaded |
| Fybroc Attributes and Constraints.xlsx | Additional constraint data | Compiled |

---

## 7. How to Verify

The configurator UI is available for testing at:
```
http://localhost:8000/ui/configurator.html
```

Automated bulk testing script (requires server running):
```
python scripts/test_series_bulk.py ALL --count 10
```

---

**Please respond with decisions on items 4.1 through 4.6 so we can close out the Fybroc milestone.**

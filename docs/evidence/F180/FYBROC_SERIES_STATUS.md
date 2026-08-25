# Fybroc Series Status — Complete Audit

**Date:** 2026-08-25  
**Verified from:** V6 Nomenclature, Rev0.3 Selections, Price Estimator Pricebook  

---

## All Fybroc Series

| Series | Orientation | V6 Code | Rev0.3 Config | Pricing | SQL Loaded | Status |
|--------|-------------|---------|---------------|---------|------------|--------|
| 1500 | Horizontal | A (ANSI), I (DIN), M (JIS) | ✅ 259 opts | ✅ 776 rules | ✅ | COMPLETE |
| 1530 | Horizontal | B (ANSI), J (DIN), N (JIS) | ✅ 195 opts | ✅ 624 rules | ✅ | COMPLETE |
| 1600 | Horizontal | C (ANSI), K (DIN), O (JIS) | ✅ 199 opts | ✅ 222 rules | ✅ | COMPLETE |
| 1630 | Horizontal | D (ANSI), L (DIN), P (JIS) | ✅ 176 opts | ✅ 222 rules | ✅ | COMPLETE |
| 2530 | Horizontal | E (ANSI) | ✅ 164 opts | ✅ 30 rules | ✅ | COMPLETE |
| 3000 | Horizontal | F (ANSI) | ✅ 181 opts | ✅ 222 rules | ✅ | COMPLETE |
| 5500 | Vertical | G (ANSI) | ✅ 550 opts | ✅ 72 rules | ✅ | PARTIAL (pump_options/motor lookup gaps for some combos) |
| 5530 | Vertical | H (ANSI) | ✅ 155 opts | ✅ 16 rules | ✅ | PARTIAL (pump_options works, seal N/A for vertical) |
| 7500 | Vertical | R (ANSI) | ✅ 19 opts | ✅ 1 rule | ✅ | PARTIAL (same vertical gaps) |
| 8500 | Vertical | T (ANSI) | ✅ 7 opts | No pricing | ✅ | CONFIG ONLY |
| 6000 | Vertical | Q (ANSI) | ❌ No data in Rev0.3 | In Pricebook | ❌ | NO CONFIG DATA |
| 7530 | Vertical | S (ANSI) | ❌ No data in Rev0.3 | In Pricebook | ❌ | NO CONFIG DATA |

---

## Key Findings

1. **10 of 12 series have configuration options** from Rev0.3 Selections
2. **6000 and 7530 have NO configuration data** in Rev0.3 — they exist in V6 Nomenclature (have identifier codes Q/S) and have Pricebook pricing blocks, but no selectable options are defined
3. **5530, 7500, 8500** now loaded into SQL with their configuration options
4. **Pricing needs loading** for 5530, 7500, 8500 from the Pricebook
5. **2630 exists in Pricebook** but not in V6 Attributes or Rev0.3 — likely a legacy/variant series

## Source Cross-Reference

| Source | Series Covered |
|--------|---------------|
| V6 Nomenclature Attributes | 1530,1600,1630,2530,3000,5500,5530,6000,7500,7530,8500 (11) |
| V6 Series+Flange Codes | 1500,1530,1600,1630,2530,3000,5500,5530,6000,7500,7530,8500 (12) |
| Rev0.3 Selections | 1500,1530,1600,1630,2530,3000,5500,5530,7500,8500 (10) |
| Price Estimator Pricebook | 1500,1530,1600,1630,2530,2630,3000,5500,5530,7500,7530 (11) |
| SQL SeriesFieldOption (current) | 1500,1530,1600,1630,2530,3000,5500,5530,7500,8500 (10) |

## Engineering Decision Needed

- **6000**: Has V6 code (Q) and pricing but no configuration options. Is this an active production series?
- **7530**: Has V6 code (S) and pricing but no configuration options. Same question.
- **2630**: Has pricing in Pricebook but no V6 code and no configuration. Legacy?


---

## Known Limitation: Vertical Series Segment Lookup

**Status:** Horizontal series (1500-3000) are FULLY OPERATIONAL.  
Vertical series (5500, 5530, 7500, 8500) have partial Part Number resolution.

**Root cause:** The VocabularyMap translation layer works for horizontal series but has gaps for vertical series because vertical pumps use different field names and values in their combination tables (e.g., `WETTED_HARDWARE`, `VAPOR_PROTECTION`, `STRAINER`, `FLUSH_OPTIONS` which don't exist in horizontal).

**Fix required:** Re-index the vertical combination table (`PUMP_OPTIONS_VERTICAL`) to use SFO-normalized values directly in `SelectionsJson`, eliminating the need for VocabularyMap translation. This is a data migration task, not an architecture change.

**What works for vertical:**
- Primary segment (Brand + Series + Size + Material + Trim) ✅
- Pricing ✅
- Configuration options + constraint enforcement ✅
- Some pump_options combinations resolve (when VocabMap translation succeeds)

**What doesn't:**
- pump_options `????` for certain field value combinations
- Seal segment correctly omitted (vertical pumps don't have seal assemblies)

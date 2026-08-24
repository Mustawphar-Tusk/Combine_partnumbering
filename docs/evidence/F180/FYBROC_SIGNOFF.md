# F180 — Fybroc Configuration Signoff & Freeze

**Date:** 2026-08-24  
**Version:** F140-corrections-v1 (MetadataPublication ID=2)  
**Status:** CONFIGURATION-COMPLETE  

---

## 1. Approved Metadata Publication

| Component | Count | Source |
|-----------|-------|--------|
| SeriesFieldOption | 1,724 rows | Rev0.3 Selections (authoritative) |
| FieldOptionDependency | 10,574 rows | SQL snapshot + CT4 constraint corrections |
| AttributeValue | 266 rows | V6 Nomenclature Attributes |
| Active Pricing Rules | 2,884 | Price Estimator-Fybroc.xlsm |

## 2. Series Coverage

| Series | Fields | Options | Status |
|--------|--------|---------|--------|
| 1500 | 46 | 259 | ✅ Complete |
| 1530 | 40 | 195 | ✅ Complete |
| 1600 | 45 | 199 | ✅ Complete |
| 1630 | 39 | 176 | ✅ Complete |
| 2530 | 29 | 164 | ✅ Complete |
| 3000 | 42 | 181 | ✅ Complete |
| 5500 | 38 | 550 | ✅ Complete |

## 3. SQL Identifier Authority

| Procedure | Status | Verified |
|-----------|--------|----------|
| cfg.fn_LookupIdentifierCode | DEPLOYED | ✅ |
| cfg.usp_GeneratePartNumber | DEPLOYED | ✅ 10/10 correct PNs |
| cfg.usp_GenerateSKU | DEPLOYED | ✅ F<Series>-<8char><VersionLetter> |
| cfg.usp_ResolveConfiguredProduct | DEPLOYED | ✅ |
| cfg.usp_LookupBySKU | DEPLOYED | ✅ |

**Part Number format:** `<Brand><Series+Flange><Size><Material><Trim>-<PumpOptions>-<SealMfg><SealAssy>-<Options>-<FrameSize><MotorAssy>-<MotorMods>-<Testing>`

**SKU format:** `<FamilyPrefix><Series>-<8char_token><VersionLetter>`

## 4. Regression Package

| Test | Cases | SQL Passed | Excel Oracle Passed |
|------|-------|------------|---------------------|
| Part Number generation | 10 | 10/10 ✅ | 2/2 (where operational) |
| SQL vs Excel parity | 2 (5500 series) | Match ✅ | Match ✅ |

## 5. Source Lineage

| Source Workbook | Role | Status |
|-----------------|------|--------|
| Nomenclature_V6.xlsm | Identifier codes, segment combinations | AUTHORITATIVE |
| Fybroc Configuration Rev0.3.xlsx | Configuration model, constraints, selections | AUTHORITATIVE |
| Price Estimator-Fybroc.xlsm | Production pricing (base, adders, components) | AUTHORITATIVE |
| Fybroc Nomenclature_V5.xlsm | Legacy reference | SUPERSEDED by V6 |
| Fybroc Attributes and Constraints.xlsx | Legacy reference | SUPERSEDED by Rev0.3 |

## 6. Known Limitations

1. **Excel Oracle horizontal series COM limitation** — Data validation VLOOKUPs in Nomenclature_V6 fail when series/flange values are written via COM without populating the full Named Range dependency chain. 5500 series works. Resolution: U150 (Excel V2 API flow) will replace COM cell manipulation with API-driven configuration.

2. **Series 5530** — Appears in Rev0.3 selections but not in current SQL supported series list. Engineering decision needed: is 5530 a production series or a future/staging series?

3. **5500 Setting-level pricing granularity** — Rev0.3 has 19 settings per size; Price Estimator has 4. Rev0.3 may have newer engineering data not yet in production pricebook.

4. **Flexaseal seal pricing** — Not yet in production pricebook. Engineering review item.

5. **MOTOR_MODIFICATIONS dependency** — 8,485 SQL rows with 11-key motor-spec context. Not yet reconciled against Rev0.3 Motor Constraints (different dimension structure). Deferred to Dean phase (D110) as the dependency structure may change.

## 7. Corrections Applied (F140)

- 2,604 over-permissive IMPELLER_TRIM dependency rows removed (CT4 enforcement)
- +182 net new SeriesFieldOption rows from Rev0.3 selections
- SEAL_TYPE vendor prefixes removed (Crane_, Flowserve_ → clean names)
- BASEPLATE_OPTION vocabulary updated (by others → no baseplate, supplied by fybroc → baseplate included)
- COUPLING_OPTION vocabulary updated (same pattern)
- Publication 1 (v0.2.0-fybroc-attributes) retired

## 8. Engineering Signoff

**Configuration completeness:** All 7 supported series project valid options from corrected metadata.  
**Identifier authority:** SQL generates Part Numbers matching V6 Nomenclature codes.  
**Pricing reconciliation:** 109/109 base prices match between Rev0.3 and Price Estimator (0 mismatches).  
**Constraint enforcement:** ConstraintTable4 (517 allowed size×trim pairs) enforced in SQL dependencies.  

---

**Fybroc declared CONFIGURATION-COMPLETE.**

**Next milestone:** D100 — Dean Source Reconciliation

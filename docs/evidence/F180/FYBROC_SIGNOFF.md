# F180 — Fybroc Configuration Signoff & Freeze

**Date:** 2026-08-26
**Code baseline:** commit `70c69d2` (branch `feature/m021-shared-excel-production-hardening`)
**Metadata publication:** id=2 `F140-corrections-v1`
**Pricing publication:** id=7 `FYBROC-REV04-MERGE-20260914-V1`
**Status:** CONFIGURATION-COMPLETE (pending engineering signature — §8)

> Supersedes the 2026-08-24 signoff. That version predated the F150 SQL identity
> authority, the Rev0.4 pricing adoption, the free-edit endpoint, and the
> all-series batch regression, and its publication/series counts were stale.

---

## 1. Approved metadata publication

Publication id=2, version `F140-corrections-v1` (active).

| Component | Count |
|-----------|------:|
| SeriesFieldOption | 2,096 rows |
| FeasibleConstraint | 4,487 rows (29 tables) |
| ConstraintFieldMap | 28 rows |
| MotorConstraint | 3,278 rows |
| AttributeValue | 532 rows |

## 2. Series coverage (10 series)

| Series | Orientation | Fields | Options | Status |
|--------|-------------|-------:|--------:|--------|
| 1500 | Horizontal | 46 | 290 | ✅ Complete |
| 1530 | Horizontal | 40 | 220 | ✅ Complete |
| 1600 | Horizontal | 45 | 229 | ✅ Complete |
| 1630 | Horizontal | 39 | 200 | ✅ Complete |
| 2530 | Horizontal | 29 | 178 | ✅ Complete |
| 3000 | Horizontal | 42 | 208 | ✅ Complete |
| 5500 | Vertical | 38 | 569 | ✅ Complete |
| 5530 | Vertical | 26 | 170 | ✅ Complete |
| 7500 | Vertical | 4 | 22 | ⚠ Sparse (see §6.1) |
| 8500 | Vertical | 4 | 10 | ⚠ Sparse (see §6.1) |

## 3. Approved pricing publication

Current Fybroc pricebook: PriceBookVersion id=7 `FYBROC-REV04-MERGE-20260914-V1`
— 56,241 active rules. Rev0.4 pricing adopted for series 1500 & 5500; other
series retain Price-Estimator pricing (option-2b scope). Components with no
current price resolve to Contact-Factory (C/F) and are reported per-config via
the resolve response `component_pricing`.

## 4. SQL identifier authority (F150)

SQL owns configured-product identity; the Python engine remains a parity oracle.

| Element | Authority | Verified |
|---------|-----------|----------|
| Canonical config signature (SHA-256) | SQL (python parity oracle) | ✅ identifier + BOM audits |
| Part Number | SQL `usp_AssembleConfiguredProduct` | ✅ 44/44 parity, oracle 6/6 |
| SKU V2 | SQL `usp_GenerateSKU` | ✅ deterministic, SKU↔PN 1:1 |
| Configured-product reuse | SQL | ✅ existing_configuration determinism |
| BOM | SQL `usp_GenerateBOM` | ✅ 38/38 signature parity + reuse |

- **Part Number format:** `<Brand><Series+Flange><Size><Material><Trim>-<PumpOptions>-<SealMfg><SealAssy>-<Options>-<FrameSize><MotorAssy>-<MotorMods>-<Testing>` (vertical series omit the seal segment).
- **SKU format:** `F<Series>-<8-char token><VersionLetter>` (Dean will use `D` prefix).

## 5. Regression package (F170)

See `docs/evidence/F170/FYBROC_EXHAUSTIVE_REGRESSION.md`. Summary:

- Correction gate `run_all_fybroc_audits.py` → **ALL CORRECTIONS INTACT**
  (selections clean, feasible 14/14, motor 91/91, identifier 44/44, BOM 38/38,
  quote 22/22, free-config 32/32).
- Excel oracle `fybroc_oracle_compare.py` → **6/6** (Excel == API).
- Per-series free-edit batch `audit_series_batch.py` → **0 errors** across all
  10 series (1,466 resolve-state + 1,466 resolve/pricing calls).

## 6. Known limitations (carried forward)

1. **7500 / 8500 sparse metadata** — only 4 configurable fields each; pricing
   largely C/F. Resolves correctly for what is defined; fuller config/pricing is
   a future engineering revision.
2. **6000 / 7530** — no configuration data in the active publication; require
   engineering to define options before support.
3. **Vertical motor_assy / horizontal seal_assy combo-table gaps** — some SFO
   values lack a matching combination row (data gap, not architecture).
4. **Excel COM oracle horizontal limitation** — COM VLOOKUP dependency-chain
   issue; API/SQL is authoritative, oracle confirms parity on drivable cases.
5. **Pricebook `IsCurrent` anomaly** — a legacy `DEV1` PriceBookVersion (id=1,
   89 rows) still carries `IsCurrent=1` alongside the Fybroc-authoritative
   `FYBROC-REV04-MERGE-20260914-V1` (id=7). The runtime targets the Rev0.4-merge
   book for Fybroc; the DEV1 flag should be cleared in a pricing-hygiene pass.

## 7. Source lineage

| Source workbook | Role | Status |
|-----------------|------|--------|
| Nomenclature_V6.xlsm | Identifier codes, segment combinations | AUTHORITATIVE |
| Fybroc Configuration Rev0.3.xlsx | Configuration model, constraints, selections | AUTHORITATIVE |
| Fybroc Rev0.4 (pricing) | 1500 & 5500 pricing adoption | AUTHORITATIVE (1500/5500) |
| Price Estimator-Fybroc.xlsm | Production pricing (other series, adders, components) | AUTHORITATIVE (non-Rev0.4) |
| Fybroc Nomenclature_V5.xlsm | Legacy reference | SUPERSEDED by V6 |
| Fybroc Attributes and Constraints.xlsx | Legacy reference | SUPERSEDED by Rev0.3 |

## 8. Engineering signoff

| Check | Result |
|-------|--------|
| All 10 series project valid options from corrected metadata | ✅ |
| Invalid combinations fail closed / reported as conflicts | ✅ |
| SQL Part Number == approved V6 nomenclature (oracle) | ✅ 6/6 |
| SKU deterministic + collision-protected + 1:1 with PN | ✅ |
| Pricing reconciled + per-config C/F visibility | ✅ |
| Correction gate green | ✅ ALL CORRECTIONS INTACT |

**Engineering signature:** _________________________  **Date:** ____________

---

**Fybroc declared CONFIGURATION-COMPLETE pending the engineering signature above.**

**Next milestone:** D100 — Dean Source Reconciliation.

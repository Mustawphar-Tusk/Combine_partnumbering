# D100 — Dean Source Reconciliation: Exit Summary

**Date:** 2026-08-26
**Milestone:** D100 — Dean Source Reconciliation
**Status:** COMPLETE — all Dean engineering sources classified and reconciled;
no workbook remains structurally unexplained.
**Constraint:** analysis/inventory only. No runtime, SQL, or Fybroc changes.

---

## Deliverables (docs/evidence/D100/)

| Deliverable | File | Covers |
|-------------|------|--------|
| Source inventory | `DEAN_SOURCE_INVENTORY.md` (prior) + this exit doc | Sheet-level inventory of the workbooks |
| Source lineage | `DEAN_SOURCE_LINEAGE.md` | Role/authority/precedence per workbook incl. DeanMasterConfig_v14 classification |
| Constraint authority | `DEAN_CONSTRAINT_AUTHORITY.md` | PumpConfiguration_Logic: 74 fields + 47 codependency allow-list tables (726 combos) |
| Constraint reconciliation | `DEAN_CONSTRAINT_RECONCILIATION.md` | Data Sheet constraint sheets mapped + deferred to PumpConfiguration_Logic; VBA audit |
| Field diff | `DEAN_FIELD_DIFF.md` | 74 fields classified (all NEW to SQL; 4 review flags) |
| Pricing source inventory | `DEAN_PRICING_SOURCE_INVENTORY.md` | 5 pricing sources located + proposed precedence (values → D120) |
| Conflict register | `DEAN_CONFLICT_REGISTER.md` | 5 blocked rules (root-caused), Config Options flags, model-ref + v14 items |
| VBA extraction | `vba/**` | All VBA from both code-bearing workbooks |

## Key outcomes

1. **Authority confirmed (engineering-directed):** `PumpConfiguration_Logic.xlsm`
   is the complete authority for **field codependencies + option domains** (74
   fields, 47 allow-list tables). Its VBA is a 25-line scratch helper — authority
   is 100% data-driven. This already matches `config/workbook_roles.json`.
2. **Data Sheet Rev 2** defers to PumpConfiguration_Logic for codependencies/
   options; it remains authoritative ONLY for **Series×Size applicability** and
   **motor sizing** (not in the logic workbook), plus part-number identity (VBA
   → SQL) for D110/D130.
3. **Prior M023.3 compile validated:** Codependencies already compiled to 47
   `ALLOWED_TUPLES` rules (42 READY / 542 tuples, publication_gate PASS,
   undirected-tuple semantics — same model class as Fybroc feasible constraints).
4. **5 blocked constraint rules root-caused:** all 184 blocked tuples are
   `UNKNOWN_DEPENDENCY_OPTION`. ~179 are Barrier-Plan **casing/normalization**
   mismatches (resolve with case/space-insensitive matching, as Fybroc already
   does); only **5 tuples** are true value-domain issues needing an engineering
   decision (Throttle Bushing "Required"; Bearing Frame Cooling "NONE").
5. **DeanMasterConfig_v14 classified (RESOLVED):** a D365 EcoRes **ERP
   product-master / attribute staging** workbook (personal "- RA - JASON" copy).
   Engineering-confirmed as an **ERP-mapping artifact**, deferred to ERP/product-
   master integration (U100/Phase P) — out of scope for the config build; does
   not supersede any governed source.
6. **SQL state:** no Dean rows published yet — publication is D110.

## Open engineering-review items (carried to D110/D120)

- Barrier Plan casing normalization (unblocks 179 tuples; loader-side, no
  workbook edit).
- **PENDING ENGINEERING** — genuine value-domain fixes (5 tuples), exact cells in
  `PumpConfiguration_Logic.xlsm → Codependencies`:
  - `AO124` Throttle Bushing `Required` → `Not Required` or `Carbon` (user verifying).
  - `AU99:AU102` Bearing Frame Cooling `NONE` → likely `Not Required`.
- Barrier Plan Extras empty domain; "Pump Configuration" instruction-as-option;
  OLD JC Style deprecation.
- Model-list reconciliation: DEANLINE 0.75x0.75 / 1.5x1.5 and MDL1-* non-A-prefix
  identifiers (PumpConfiguration_Logic vs Data Sheet Rev 2 model reference).
- D110 schema must support a **4-leg** allowed-tuple (Seal Option × Gland Type ×
  Flush Plan × Barrier Plan); Fybroc's feasible-constraint shape is 3-leg.

## Exit gate

> All Dean engineering sources classified and reconciled.

**MET.** Five governed workbooks classified with explicit authority/precedence;
the constraint authority fully modeled; VBA audited; fields and pricing sources
inventoried; conflicts registered and root-caused. No workbook remains
structurally unexplained.

**Next permitted milestone:** D110 — Dean Configuration & Dependency Completion
(publish the PumpConfiguration_Logic model to SQL for the Dean family, resolving
the normalization/value items above). **Do not start D110 without explicit
go-ahead.**

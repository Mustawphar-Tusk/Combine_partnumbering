# Targeted Price Adjustment — Procedure & How-To

**What this adds:** a supported, audited way to apply a **percentage** price change
to the live pricing, targeted by pump family / series / all-families and optionally a
single component — via a stored procedure, not hand edits.
**Date:** 2026-08-26 · **Mode:** FULL (shared pricing schema + proc; cross-family blast radius).
**Status:** mechanism deployed; **no live adjustment applied** (prices unchanged).

---

## 1. Where price rows live (for updates)

```
cfg.PumpFamily (DEAN=1, FYBROC=2)
  └─ price.PriceBook              one book per family ("<FAMILY>_STANDARD")
       └─ price.PriceBookVersion  versioned; exactly one IsCurrent=1 per book
            └─ price.PriceRule     ← THE PRICE ROWS. Amount is the price.
                 └─ price.PriceCondition   the selectors (SIZE, PUMP_MATERIAL, option values)
```

**`price.PriceRule.Amount`** is the price. Family is reached via
`PriceRule → PriceBookVersion → PriceBook.PumpFamilyId`. Only the `IsCurrent=1`
version is live (`price.vw_CurrentPricingRules` is the read view the runtime uses).
Prices are normally **published** from the Excel sources (compiler → merge →
publisher); this adjustment proc modifies the published `Amount` in bulk, with audit.

---

## 2. The model

A pump **SERIES** (Fybroc 1500, Dean PH2110, …) is the **parent**; its priced
**COMPONENTS** (BASE_PUMP, SEAL, SHAFT_MATERIAL, FLANGE_TYPE, CASING_DRAINS,
IMPELLER/PUMP_MATERIAL_ADDER, …) are the **children**. A FAMILY- or SERIES-scoped
adjustment with no component cascades to **all** child component rows under it.

Scope (most specific wins when you choose to narrow):
| ScopeType | Targets |
|---|---|
| `ALL_FAMILIES` | every family's current price book (the only cross-family scope) |
| `FAMILY` | one family — all its series and components |
| `SERIES` | one family + one series |
| + `ComponentCode` (optional) | narrows any scope to one child component (NULL = all) |

---

## 3. The procedure — `price.usp_ApplyPriceAdjustment`

(DDL: `sql/19_Create_Price_Adjustment.sql`)

```sql
EXEC price.usp_ApplyPriceAdjustment
     @ScopeType     = 'ALL_FAMILIES' | 'FAMILY' | 'SERIES',
     @PercentChange = 5,        -- +5%;  -2.5 => -2.5%
     @FamilyCode    = 'FYBROC', -- required for FAMILY/SERIES
     @SeriesCode    = '1500',   -- required for SERIES
     @ComponentCode = 'SHAFT_MATERIAL',  -- optional; NULL = all components
     @Reason        = '2026 list adjustment',
     @AppliedBy     = 'jdoe',
     @DryRun        = 1;        -- 1 = PREVIEW (default, writes nothing); 0 = APPLY
```

Behavior:
- Targets **only the current (`IsCurrent=1`) price book version** of each in-scope family.
- `SeriesCode` matches exact OR `code %` OR `code(%` (handles labels like `1530 (ANSI)`).
- New amount = `ROUND(Amount * (1 + @PercentChange/100), 4)`.
- **`@DryRun=1` (default)** returns a summary + per-component breakdown and **writes nothing**.
- **`@DryRun=0`** updates `price.PriceRule.Amount` in a transaction and writes a full audit:
  - `price.PriceAdjustment` — one header row (scope, percent, rows affected, before/after
    totals, reason, who, when).
  - `price.PriceAdjustmentRow` — one row per `PriceRule` changed (old → new amount).
- **Validation** (THROW 52001–52007): invalid scope; missing percent; `@PercentChange <= -100`
  (would zero/negate prices); missing family/series for the scope; unknown family; empty
  target set.
- **Family isolation:** FAMILY/SERIES scopes never touch another family. ALL_FAMILIES is the
  only cross-family scope, by design.

**Reversal:** apply the inverse percentage, or restore exact amounts from the row log:
```sql
UPDATE pr SET pr.Amount = ar.AmountBefore
FROM price.PriceRule pr
JOIN price.PriceAdjustmentRow ar ON ar.PriceRuleId = pr.PriceRuleId
WHERE ar.PriceAdjustmentId = <id>;
```

---

## 4. CLI wrapper (ergonomic) — `scripts/apply_price_adjustment.py`

Defaults to a **dry-run preview**; pass `--apply` to commit.
```
# preview +5% on all Fybroc shaft-material prices
python scripts/apply_price_adjustment.py --scope FAMILY --family FYBROC --component SHAFT_MATERIAL --percent 5

# apply +3% to every component on Fybroc 1500
python scripts/apply_price_adjustment.py --scope SERIES --family FYBROC --series 1500 --percent 3 --apply --reason "2026 list" --by jdoe

# preview +2.5% across ALL pumps
python scripts/apply_price_adjustment.py --scope ALL_FAMILIES --percent 2.5
```

---

## 5. Verification (commands + numbers)

- **Dry-run preview** (FYBROC SHAFT_MATERIAL +10%): 38 rows, $10,575 → $11,632.50; DB
  **unchanged** afterward.
- **Scope targeting** (dry-run row counts): ALL_FAMILIES **66,229** (= 56,355 FYBROC +
  9,874 DEAN); FAMILY FYBROC **56,355**; FAMILY DEAN **9,874**; SERIES FYBROC 1500 (all
  components) **5,193**; SERIES FYBROC 1500 + SHAFT_MATERIAL **38**.
- **Real round-trip**: applied +10% to the 38-row scope (audit header + 38 row-log entries),
  **FYBROC changed, DEAN untouched**, then reverted from the audit log → pricing
  **byte-identical** to before (checksums + sums + counts matched).
- **CLI**: dry-run FYBROC FLANGE_TYPE +5% = 36 rows $54,436 → $57,157.80; validation error
  path (SERIES without `--series`) rejected with THROW 52005 and non-zero exit.
- **Regression**: `run_all_fybroc_audits.py` = **ALL CORRECTIONS INTACT (9/9)**.
- **Final isolation**: FYBROC 56,355 / $186,402,219.28 and DEAN 9,874 / $19,442,824.55 —
  both equal baseline; `price.PriceAdjustment` has **0 rows** (no live adjustment left).
  `imports OK`.

---

## 6. Exit-gate decision — PASS

| Criterion | Result |
|---|---|
| Proc + audit tables deployed (idempotent) | **PASS** |
| Scopes target correct row sets (ALL/FAMILY/SERIES + component) | **PASS** |
| Dry-run previews, writes nothing | **PASS** |
| Real apply audited + reversible; family-isolated | **PASS** |
| CLI works + validates | **PASS** |
| Regression 9/9; pricing unchanged (mechanism only) | **PASS** |

---

## 7. Known notes / disclosures

- **Interaction with republish:** a future Excel republish (compiler → merge → publisher)
  mints a NEW price book version and regenerates `Amount` from source, which would **not**
  carry forward a manual adjustment. The audit log preserves what was applied so it can be
  re-applied after a republish; wiring the adjustments to auto-reapply on publish is a
  possible future enhancement (not in this change).
- Prices are stored as `decimal(19,4)`; percentage results are rounded to 4 dp.
- The proc only touches `IsCurrent=1` versions, so historical versions are never altered.

---

## 8. Reproducibility — deploy + verify
```
# deploy (idempotent)
sqlcmd/pyodbc: run sql/19_Create_Price_Adjustment.sql
# preview
python scripts/apply_price_adjustment.py --scope FAMILY --family FYBROC --component SHAFT_MATERIAL --percent 5
# regression
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\run_all_fybroc_audits.py
```

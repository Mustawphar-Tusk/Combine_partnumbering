# Phase C (CPQ Quotes UI) — Exit Evidence

**Milestone:** CPQ roadmap Phase C — Quotes UI (FULL milestone).
**Scope:** Add a Quotes page (list / create / open) and an "Add to a quote" action on
the configurator result page, both families, on top of the existing quote engine, with
one thin additive list endpoint. Fybroc frozen.
**Result:** PASS. See exit-gate decision at the bottom.

---

## 1. Deliverables inventory

| Artifact | Type | Note |
|---|---|---|
| `sql/26_Create_Quote_List.sql` | NEW SQL | `quote.usp_ListQuotes` — read-only aggregate over existing `quote.QuoteHeader`/`QuoteLine`. No table/DDL change, no change to existing procs. Applied via `sqlcmd -S localhost -d PumpConfiguratorDB -E -C -b -i sql\26_Create_Quote_List.sql`. |
| `src/api/v2_routes.py` | EDIT (additive) | New endpoint `GET /api/v2/families/{family}/quotes` → `{quotes:[…], count}`. No existing endpoint or response shape changed. |
| `ui/configurator.html` | EDIT (UI) | Quotes page (list/create/open sub-views) replacing the Phase A placeholder; "Add to a quote" panel on the result page; `showPage('quotes')` loads the list. |
| `scripts/audit_cpq_quotes_ui.py` | NEW | Re-runnable milestone audit. |

Reused unchanged: `quote.usp_CreateQuote`, `quote.usp_AddQuoteLine`, `quote.usp_GetQuote`,
`POST /quotes`, `POST /quotes/{id}/lines`, `GET /quotes/{id}`, and the authoritative
`/configured-products/resolve` flow (identity + BOM + pricing).

## 2. Exit-gate criteria → concrete checks

1. List endpoint returns each quote with `line_count` and `total_price`. ✅
2. List `total_price`/`line_count` for a quote **equal the authoritative** `GET /quotes/{id}`. ✅ (36438.0 == 36438.0; 2 == 2)
3. Full round-trip both families: create → add Fybroc line + Dean line → list → open. ✅
4. Each line persists PN/SKU, `extended == qty*unit`, honest pricing status. ✅
5. Fybroc frozen: regression gate 9/9 + Fybroc table watermarks unchanged. ✅

## 3. Milestone audit — `scripts/audit_cpq_quotes_ui.py`

Command: `$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\audit_cpq_quotes_ui.py` (API on 8080).
Result: **16 passed, 0 failed** (run twice — pre-gate and post-gate — both 16/0).

Representative output:
```
[PASS] quote created (Q-000063)
[PASS] FYBROC 1500: line PN present (FA?1??-0001-S01-01-??001-XXX-00)
[PASS] FYBROC 1500: extended == qty*unit (36438.0 == 18219.0*2)
[PASS] FYBROC 1500: honest pricing status (found)
[PASS] DEAN Deanline: extended == qty*unit (0.0 == 0.0*2)
[PASS] DEAN Deanline: honest pricing status (call_for_price)
[PASS] list total == get-quote total (36438.0 == 36438.0)
[PASS] list line_count == get-quote line_count (2 == 2)
```

## 4. Cross-family / prior-correction regression

`scripts/run_all_fybroc_audits.py` → **RESULT: ALL CORRECTIONS INTACT (9/9)**:
selections_vs_db, feasible_constraints, motor_constraints, identifier_parity, bom_engine,
**quote_engine**, free_config, fybroc_pricing, fybroc_motor_cpq. (The quote_engine audit
directly exercises the extended quote path.)

## 5. Isolation / no-collateral-damage

Table counts captured before AND after the gate + audit runs (`scripts/_tmp_watermarks.py`,
a throwaway probe, since deleted):

| Table | Before | After | Δ |
|---|---|---|---|
| cfg.FeasibleConstraint | 4743 | 4743 | 0 |
| cfg.ConstraintFieldMap | 59 | 59 | 0 |
| cfg.SeriesFieldOption | 52145 | 52145 | 0 |
| stg.SegmentCombinationImport | 407500 | 407500 | 0 |
| cfg.ConfiguredProduct (non-DEAN) | 1196 | 1196 | 0 |
| quote.QuoteHeader | 63 | 65 | +2 (feature) |
| quote.QuoteLine | 185 | 190 | +5 (feature) |

Every config/constraint/segment/non-Dean-product count is unchanged; only the quote tables
grew, by exactly the quotes/lines the audit runs created. The new proc/endpoint are
read-only over quote tables and add no constraint or pricing logic.

> Note on absolute watermark numbers: these combined totals (e.g. FeasibleConstraint 4743,
> SegmentCombinationImport 407500) are higher than figures recorded in much earlier D-milestone
> notes because Dean config has grown across the D-series milestones since. The Phase C test is
> the **before==after** equality above, and the Fybroc gate (which checks Fybroc's own invariants
> internally) — both hold. `cfg.ConfiguredProduct non-DEAN = 1196` matches the recorded Fybroc
> watermark exactly.

## 6. Build / tests

- `src/api/v2_routes.py` parses (ast.parse OK) and imports (API boots, serves `/ui` HTTP 200).
- UI structural checks: balanced tags, all quote JS functions present.
- Temp scripts removed: `_tmp_watermarks.py`, `_tmp_phasec.txt`, `_tmp_pc2.txt`, `_tmp_dc.txt`,
  `_tmp_fybroc_gate_c.txt`.

## 7. Known gaps (disclosed, not blocking Phase C)

- **Dean base price**: a Dean `Deanline` line resolves to `call_for_price` / $0.00 because the
  Dean STD config currently has no matching base-price rule. This is a **pre-existing pending
  Dean pricing gap**, not a Phase C regression — the quote engine honestly reports
  `call_for_price`, and the Fybroc line prices correctly ($18,219/ea). Dean pricing is tracked
  separately (Dean pricing milestone / D-series), not in CPQ Phase C.
- **Line edit/remove UI**: Phase C delivers list/create/open/add-line. Editing or removing an
  existing line is deferred (no `usp_*` for it yet); add in a later pass if needed.
- **Per-option price deltas / live plate**: deferred in Phase B (documented there), unchanged here.

## 8. Exit-gate decision — PASS

| Criterion | Verdict |
|---|---|
| List endpoint correct (count/total == get-quote) | PASS |
| Create→add(both families)→list→open round-trip | PASS |
| Line persistence (PN/SKU/ext=qty*unit/status) | PASS |
| Fybroc regression gate 9/9 ALL CORRECTIONS INTACT | PASS |
| Isolation (config/constraint/segment/non-Dean unchanged) | PASS |

**Phase C PASS.** Next permitted milestone: **Phase D (Accounts / contacts)**. Awaiting
explicit user go-ahead before starting it. D150 (Exhaustive Dean Regression) remains PARKED.

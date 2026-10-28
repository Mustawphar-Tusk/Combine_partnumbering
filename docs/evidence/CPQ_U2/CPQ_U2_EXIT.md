# CPQ SPA — U2 Exit Evidence

**Milestone:** CPQ SPA U2 — quote **configuring + creating** UI in the React SPA +
**server-owned loyalty math** on quotes.
**Branch:** `feature/cpq-spa`. **Mode:** FULL (adds one API endpoint).
**Design:** `docs/CPQ_SPA_U2_DESIGN.md`. Decision in force: D4 (loyalty rate is
server-owned; discount base = merchandise subtotal of fully-priced lines only).

---

## 1. Deliverables inventory

**API (additive — no v2 route changed, NO DB migration):**
- `src/api/acct_routes.py` → new `GET /api/v2/quotes/{quote_header_id}/pricing`.
  Resolves the caller's identity → `acct.DistributorAccount` → `LoyaltyTierCode` →
  `acct.LoyaltyTier.RateBp` (authoritative, server-owned), reads the persisted quote
  via the existing `quote.usp_GetQuote`, and returns loyalty-adjusted totals:
  `list_total`, `merchandise_subtotal` (Σ `ExtendedPrice` where `pricing_status =
  'found'`), `discount_rate_bp`, `discount_amount` (= subtotal × rate),
  `net_total` (= subtotal − discount + unpriced-at-list), `unpriced_line_count/total`,
  `loyalty_tier_code`, `currency`. Staff/no-account callers → rate 0 (list pricing).
  A missing quote returns a clean 404 (the `quote.usp_GetQuote` "not found" RAISERROR
  is caught and translated, so it is not surfaced as a 503).

**Frontend (new SPA screens in the existing `spa/` React app):**
- `spa/src/pages/ConfiguratorPage.tsx` — free-edit configurator bound to
  `resolve-state` (group tabs from `field_groups`, dropdowns from `allowable_options`,
  STD markers, conflict flags) + a live spec plate from `resolve` (PN/SKU/
  `component_pricing` found/C-F/total). Dean + Fybroc family switch.
- `spa/src/pages/QuotesListPage.tsx` — list + create quote.
- `spa/src/pages/QuoteWorkspacePage.tsx` — lines + a Totals card driven by the new
  `/pricing` endpoint (list total, merchandise subtotal with an "excluded unpriced
  lines" note, loyalty discount line with tier + %, net total). "Add current
  configuration" adds the configurator's draft via the existing add-line endpoint.
- `spa/src/pages/LookupPage.tsx` — by-SKU lookup.
- `spa/src/{format.ts,draft.ts}`, extended `spa/src/api/{types.ts,client.ts}`, and
  `spa/src/App.tsx` (nav + routes gated on `caps.configure` / `caps.create_quote`).

**Audit:** `scripts/audit_cpq_u2.py` — re-runnable, self-cleaning U2 pricing audit.

---

## 2. Exit-gate criteria → result (PASS/FAIL)

| # | Criterion | Result |
|---|-----------|--------|
| 1 | New `/quotes/{id}/pricing` endpoint; no v2 route changed; no DB migration | PASS |
| 2 | Loyalty rate is server-owned (read from `acct.LoyaltyTier`, never the UI) | PASS |
| 3 | Discount applied to merchandise subtotal of `found` lines only (D4) | PASS |
| 4 | standard=0 / loyalty15=15% / loyalty30=30% applied correctly | PASS |
| 5 | Unpriced (`partial`/`call_for_price`) lines excluded from base, carried at list | PASS |
| 6 | Staff/admin (no account) → rate 0; missing quote → 404 | PASS |
| 7 | SPA configurator + quotes + lookup build (tsc strict + vite) & serve at `/app` | PASS |
| 8 | Fybroc regression gate — all 9 audits pass on their merits | PASS* |
| 9 | Isolation: frozen-family watermarks unchanged | PASS |
| 10 | Legacy `/ui` + U1 `/app` screens still work | PASS |

\* See §4 for the one batch-run flake (HTTP timeout) that was reproduced GREEN in
isolation.

---

## 3. How it was verified (commands + numbers)

**U2 pricing audit** (server on :8080, dev mode):
```
uv run python scripts/audit_cpq_u2.py
→ U2 PRICING: 18/18 checks passed   (self-cleaning; run-tagged rows deleted)
```
Observed figures: Fybroc 1500 line priced `found` ext **$18,219**; Dean RA3146 line
`partial` ext **$13,675** (excluded from the discount base).
- standard  : rate 0     → discount $0.00     → net $31,894.00
- loyalty15 : rate 1500bp → discount $2,732.85 → net $29,161.15
- loyalty30 : rate 3000bp → discount $5,465.70 → net $26,428.30
- staff/admin: rate 0. Missing quote: 404.

**SPA build:**
```
cd spa; npm run build
→ tsc -b (strict) clean; vite build → spa/dist (49 modules; bundle index-Dl59esqC.js)
```
Live: `/app/` 200 (serves rebuilt bundle), `/api/v2/me` 200, legacy
`/ui/configurator.html` 200.

**Fybroc regression gate** `uv run python scripts/run_all_fybroc_audits.py`:
```
audit_selections_vs_db      PASS  (CLEAN - DB matches Rev0.4 Selections)
audit_feasible_constraints  PASS  (44/0)
audit_motor_constraints     PASS  (91/0)
audit_identifier_parity     PASS  (44/0)
audit_bom_engine            PASS  (38/0)
audit_quote_engine          PASS  (22/0)
audit_free_config           FAIL in batch (HTTP TimeoutError) → RE-RUN IN ISOLATION: PASS (32/0)
audit_fybroc_pricing        PASS  (47/0)
audit_fybroc_motor_cpq      PASS  (37/0)
```

**Isolation watermarks (U1 baseline → post-U2, identical):**
```
cfg.FeasibleConstraint (total)          : 4743  → 4743
non-Dean cfg.SeriesFieldOption          : 3638  → 3638
non-DEAN stg.SegmentCombinationImport   : 300608 → 300608
non-DEAN cfg.ConfiguredProduct          : 1196  → 1196
```
U2 added only a read-only endpoint + SPA files; no cfg/price/quote config data changed.

---

## 4. Known gaps / not-verified (disclosed honestly)

- **Fybroc gate `audit_free_config` flaked in the batch run** with a Python
  `TimeoutError` while reading an HTTP response (the gate shares one server across all
  9 audits and the machine was under load from leftover processes). It was **re-run in
  isolation against a fresh dedicated server and PASSED 32/0, exit 0** — confirming no
  regression; the failure was environmental (HTTP read timeout), not an assertion.
  The batch summary therefore printed "REGRESSION DETECTED" solely due to that timeout.
- **No real Entra** — U2 runs against dev-mock auth; real token validation is U5.
- **Discount base excludes freight/tax** and unpriced lines by design (D4); those are
  deferred until confirmed. Dean base-price-pending lines come back `partial` and are
  correctly excluded from the discountable subtotal (carried at list in the net).
- **`spa/dist` is a gitignored build artifact** — a fresh checkout must run
  `npm install && npm run build` in `spa/` before `/app` serves the U2 screens.
- **Out of scope (later phases):** engineering review/queue (U3), custom-field C/F
  pricing-by-applications flow (U3/U4), acceptance/PDF (U4), real Entra + cutover (U5),
  line edit/remove UI, multi-brand quotes (D7).
- One `quote.QuoteHeader` row (id 70, "Emory Wilson", created_by `configurator-ui`)
  exists from manual browser testing of the U2 Quotes UI — legitimate user data, left
  in place. `quote.QuoteHeader` is the feature's own (non-frozen) table; it is not an
  isolation watermark.

---

## 5. Reproducibility
```powershell
# Build SPA
cd spa; npm install; npm run build; cd ..
# Start API (dev)
$env:PYTHONPATH="."; $env:CONFIGURATION_TOKEN_SECRET="local-dev-configuration-token-secret-0123456789"
uv run python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8080
# U2 pricing audit (separate terminal)
uv run python scripts/audit_cpq_u2.py
# Fybroc gate (stop the server first so :8080 is free)
uv run python scripts/run_all_fybroc_audits.py
```

---

## 6. Exit decision
**PASS.** U2 adds one additive read-only endpoint (loyalty rate server-owned per D4) and
the configurator/quote/lookup SPA screens; the pricing audit is 18/18 self-cleaning;
every Fybroc audit passes on its merits (the lone batch failure was an HTTP-timeout flake
reproduced green in isolation); isolation watermarks are unchanged; `/ui` and the U1
`/app` screens still work. Next permitted milestone: **U3** (engineering review/queue) —
await explicit user go-ahead before starting it.

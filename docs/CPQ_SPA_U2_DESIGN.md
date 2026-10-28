# CPQ SPA — U2 Design (for approval)

**Track:** the authoritative CPQ SPA U-track defined in `docs/CPQ_SPA_U1_DESIGN.md` §5.
U1 shipped (SPA shell + identity + distributor onboarding + admin approval).
**U2 goal (per U1 design §5):** quote **configuring + creating** UI in the SPA, plus
**loyalty math on quotes** (apply the distributor's assigned loyalty-tier discount to
quote totals). Branch `feature/cpq-spa`.

**Decisions in force:** D4 — loyalty tiers `standard`/`loyalty15`/`loyalty30`
(0/15/30%), admin-assigned, **server-owned** (the UI never owns the rate); "total
sales"/discount base = **merchandise subtotal only** (custom/freight/tax excluded).
D5 — standard/priced/no-C-F quotes may complete without engineering when lead time is
available (engineering queue itself is U3). D7 — single-brand quotes.

Scope guardrails: **Fybroc frozen**; additive-only; authorization enforced on the API.

---

## 1. What already exists (reuse, do NOT change)

From `src/api/v2_routes.py` (unauthenticated v2 engine — authoritative):
- `POST /api/v2/families/{family}/configurations/resolve-state` — free-edit config
  state: `selections`, `allowable_options`, `standard_defaults`, `ordered_fields`,
  `field_groups`, `conflicts`, `resolved_codes`. (The configurator's data source.)
- `POST /api/v2/families/{family}/configured-products/resolve` — PN/SKU/signature +
  `pricing[]` (priced only) + `component_pricing[]` (all, status `found`/`C/F`) +
  `total_price`.
- `GET  /api/v2/configured-products/by-sku/{sku}` — lookup (family-agnostic).
- `POST /api/v2/families/{family}/quotes` — create quote header.
- `POST /api/v2/families/{family}/quotes/{id}/lines` — add line (resolves+prices+persists;
  line `pricing_status` ∈ `found`/`partial`/`call_for_price`).
- `GET  /api/v2/families/{family}/quotes/{id}` — quote document (header, lines,
  `total_price` = Σ line `extended_price`, `rendered_text`).
- `GET  /api/v2/families/{family}/quotes` — list quotes.

Families: DEAN, FYBROC (case-insensitive path). Currency: string, default USD. All
money values are JSON numbers (float).

## 2. The one additive backend change (why it's needed)

Decision **D4 says the loyalty rate is server-owned; the UI must never own it.** The
existing quote endpoints have **no discount concept** and return list totals only.
Doing the discount in the browser would put the rate in the client — violating D4 and
the handoff's "server entitlement, not a UI flag" rule.

**Therefore U2 adds exactly one thin, additive, read-only endpoint** (new `acct`
router — no change to any v2 route, no DB migration):

- `GET /api/v2/quotes/{quote_header_id}/pricing` — returns the quote's
  loyalty-adjusted totals computed **server-side**:
  - resolves the caller's identity → their `acct.DistributorAccount` →
    `LoyaltyTierCode` → `acct.LoyaltyTier.RateBp` (authoritative rate);
  - reads the persisted quote via `quote.usp_GetQuote` (existing);
  - **merchandise subtotal** = Σ line `extended_price` where `pricing_status = 'found'`
    (fully-priced lines only — D4 "merchandise subtotal only"; `partial`/`call_for_price`
    lines are listed but excluded from the discountable base and flagged);
  - `discount_rate_bp`, `discount_amount` = subtotal × rate, `net_total` = subtotal −
    discount; plus `unpriced_line_count` and the raw `list_total` for transparency.
  - **Admin / staff** callers (no distributor account) get `rate_bp = 0` (list pricing),
    so the endpoint is safe for everyone.

This keeps the rate authoritative and server-computed while every PN/price/number still
comes from the frozen engine. (No new table: it reads `acct.*` from U1 + the existing
quote tables.) Because it adds an endpoint, **U2 runs the FULL milestone ceremony.**

## 3. SPA (new screens in the existing `spa/` React app)

Additive pages + a typed client, capability-gated by U1's `/me` (`configure` /
`create_quote` must be true — i.e. staff, or an APPROVED distributor):

- **Configurator (`/app/configure`)** — the free-edit configurator bound to
  `resolve-state`: group tabs from `field_groups`, every field a dropdown from
  `allowable_options`, STD defaults, conflict flags (from `conflicts`), and a live
  spec/PN plate from `resolve` (PN, SKU, `component_pricing` with found/C-F, total).
  Dean + Fybroc (family switch). No mock engine — all values from the API.
- **Quote workspace (`/app/quotes/:id`)** — header + lines + totals. Totals come from
  the new `/pricing` endpoint: list subtotal, **loyalty discount line**, net total,
  and a note when unpriced/C-F lines are excluded from the discount base. "Add current
  configuration to this quote" calls the existing add-line endpoint.
- **Quotes list (`/app/quotes`)** — from `GET …/quotes`; create-quote action.
- **Lookup (`/app/lookup`)** — by-SKU → load into the configurator.

Capability gating: a distributor whose account is not APPROVED cannot reach configure/
quote (server `/me` entitlement + client route guard). Fybroc stays presentation-only.

## 4. What U2 does NOT do
Engineering review/queue (U3), acceptance/PDF (U4), real Entra (U5), custom-field C/F
*pricing-by-applications* flow (U3/U4), freight/tax in the discount base (deferred until
confirmed), multi-brand quotes (D7). Line edit/remove UI only if the existing endpoints
support it (no new quote proc planned; flag if needed).

## 5. U2 exit evidence (FULL ceremony)
- New `/api/v2/quotes/{id}/pricing` endpoint; **no v2 route changed, no DB migration.**
- Re-runnable self-cleaning audit `scripts/audit_cpq_u2.py`: build a config via
  resolve-state → resolve, create a quote, add a priced line + an unpriced (C/F) line,
  assert `/pricing` applies the account's tier to the priced subtotal only (standard→0,
  loyalty15→15%, loyalty30→30%), nets correctly, and excludes C/F from the base; staff
  caller gets rate 0. Clean up all rows.
- Fybroc gate 9/9; isolation watermarks unchanged; SPA build (tsc+vite) clean;
  legacy `/ui` + U1 `/app` screens still work.
- Evidence `docs/evidence/CPQ_U2/…`, roadmap/register bump, commit + push 4 refs.

## 6. One confirmation before building U2
**Q:** OK to add the single additive read-only endpoint
`GET /api/v2/quotes/{id}/pricing` (loyalty-adjusted totals computed server-side from the
account's tier) — rather than doing discount math in the browser? This is required to
keep the loyalty rate server-owned per D4. No existing endpoint or table changes; it
only reads U1's `acct.*` + the existing quote tables. (If you'd rather defer any backend
touch and show **list pricing only** in U2 — no discount yet — I can do that instead and
move loyalty math to a later phase.)

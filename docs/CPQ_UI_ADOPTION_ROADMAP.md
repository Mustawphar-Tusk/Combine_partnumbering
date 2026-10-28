# CPQ Full UI Adoption Roadmap — adopt the reference UI model (`docs/api/ui_logic.md`)

**Status:** DRAFT — awaiting user approval. No UI code started.
**Supersedes:** the incremental Phases A/B/C/F/G of `docs/CPQ_UI_EXPANSION_ROADMAP.md`
(Phase A nav shell, B polish, C quotes, F PDF, G data model). Those were already
shipped piecemeal; this replaces that approach with a single cohesive UI rebuilt on
the reference's model. Phase E (per-grouping custom-hex backend) remains a separate,
later, backend concern and is NOT part of this UI work.

---

## 1. What the user asked for (scope lock)

- **Adopt** from the reference (`docs/api/ui_logic.md`):
  1. its **UI presentation** (visual design, layout, the configurator's
     left-summary / right-options `vConfig` model, status pills, cards, tabs);
  2. its **quote application logic** (quote lifecycle + roles + applications flow);
  3. its **customizable-field logic for custom-field configuration** (letting a field
     be set to Custom/Contact-Factory and captured as a priced/pending line item).
- **Discard** the reference's **Custom-code Library** view and **Data-model** view.
- **Keep the backend EXACTLY as-is** — same v2 API endpoints and same database.
  The UI is presentation + orchestration only; it calls our authoritative engine.
- Apply to **both families** (Dean + Fybroc). Fybroc stays frozen (UI is
  presentation-only; it calls the same frozen endpoints).

## 2. Non-negotiable principle (why this is safe)

The reference computes pricing, part numbers, constraints, and option availability
**in the browser from mock data** (`priceCfg`, `encodeSpec`, `CONSTRAINTS`, `FIELD`,
`GROUPS`). We **do NOT port that mock engine.** Every authoritative value continues to
come from our v2 API / SQL Server:
- options / std defaults / constraints / groups → `POST /configurations/resolve-state`
- part number / SKU / signature / reuse / component pricing → `POST /configured-products/resolve`
- lookup → `GET /configured-products/by-sku/{sku}`
- quotes → `POST /quotes`, `POST /quotes/{id}/lines`, `GET /quotes/{id}`,
  `GET /families/{family}/quotes` (all already exist)

We adopt the reference's **shell, styling, and interaction patterns** and bind them to
these endpoints. No endpoint or DB change. No mock pricing/encoding in the client.

## 3. Target architecture

- A **new single-page UI** replacing `ui/configurator.html`, built on the reference's
  `state → render() → data-action` pattern (global `S` state, one `render()` that
  rebuilds `#app`, delegated `data-a`/`data-c`/`data-i` handlers). Client state holds
  only view/session/draft/quote-id/toast — never authoritative pricing or encoding.
- **Views kept** (reference → ours):
  - **Quotes log** (`vLog`) — list quotes from `GET /families/{family}/quotes`.
  - **Quote workspace** (`vQuote`) — header + lines + totals + activity + actions,
    over `GET /quotes/{id}` and the add-line/create endpoints.
  - **Configurator** (`vConfig`) — the better layout: left grouped **summary** pane +
    right **options** pane with group tabs, per-field state, the live spec-number plate,
    driven by `resolve-state` + `resolve`.
  - **Look up a pump** (`vLookup`) — `by-sku`, load into configurator.
  - **Applications queue** (`vQueue`) — quotes/lines needing attention (custom / C\/F /
    pending), derived from quote-line pricing status (uses the existing list endpoint;
    may add one thin additive read if needed — flagged in Phase 3).
- **Views discarded:** Custom-code Library (`vLibrary`), Data model (`vData`).
- **Roles:** the reference's Distributor vs Applications (`ae`) toggle drives who can
  edit and who prices custom items. This is **UI-side orchestration** over our persisted
  quotes (our quote status field + line pricing_status). No new auth.

## 4. Quote application logic (adopted, mapped to our backend)

- **Lifecycle:** Draft → With applications → Completed by applications → Released. Our
  `quote.QuoteHeader.Status` CHECK allows `Draft/Submitted/Approved/Expired/Cancelled`;
  we map the reference's labels onto these (or carry the display status in the UI and
  persist the nearest backend status). *Decision Q3 below.*
- **Line calc & totals:** unit/extended/net come from our `resolve` + quote line
  persistence + an account discount. (Accounts/discount = see Q2.)
- **"Send to applications" / "Complete & notify":** status transitions + activity log.
  Activity/history and the notify email are **UI-side** (we keep DB as-is; if we want
  history persisted, that's a later additive table — not now).
- **Custom / Consult-Factory line items:** a line with a custom (C\/F) field is "pending"
  until the applications role prices it; mirrors the reference's pend/finish flow. The
  **price/notes for a custom item are carried on the quote line** (pricing lineage JSON
  the add-line endpoint already persists) — no new backend.

## 5. Customizable-field logic (adopted)

- Any applicable field can be set to its **Custom / C-F** value (our resolver already
  emits C/F and has the custom-segment handling). In the configurator the user picks
  Custom on a field; the UI captures a **free-text spec/request** and (for the
  Applications role) a **price + note**.
- A custom line surfaces as **pending** in the quote + applications queue until priced,
  then shows the applications-entered price. This is the reference's seal/motor/special
  "X-code" UX **without** the global code-library view (discarded) and **without** backend
  changes — the custom description/price lives on the quote line.
- (The separate per-grouping **base-36 custom-hex** backend concept from the old roadmap
  Phase E is independent and NOT built here; if adopted later it slots in under the same
  UI with no UI change.)

## 6. Phased plan (each phase independently shippable + verified; Fybroc frozen)

Every phase: build against the real API, smoke-test **both families**, keep the old
`configurator.html` working until the new UI is verified, commit, push all 4 refs. A UI
change that only calls existing endpoints is LEAN; no DB writes, so no full gate unless a
phase adds an endpoint.

### Phase U1 — New SPA shell + configurator (presentation core)
New `ui/app.html` (+ `ui/app.js` or inline): the `state/render/action` shell, the
reference styling, top nav (Quotes · Look up · Configurator · Queue), family switch, and
the **`vConfig` configurator** (left summary + right options + live plate) bound to
`resolve-state`/`resolve`. Reaches functional parity with today's configurator in the new
look. Both families.

### Phase U2 — Look up a pump (`vLookup`)
SKU lookup → read-only sectioned view → "load into configurator", in the new shell.

### Phase U3 — Quotes (log + workspace + lifecycle)  [may add 1 thin endpoint]
Quotes log, quote workspace (lines/totals/activity/actions), create quote, add line from
a configuration, edit/duplicate/remove line, status transitions. Reuses existing quote
endpoints + the list endpoint. If line edit/remove needs a proc we don't have, add it
**additively** (flagged; FULL ceremony for that phase).

### Phase U4 — Customizable fields + Applications queue
Custom-field capture on the configurator (Custom/C-F + request text), pending-item flow,
Applications role pricing of custom items, and the Applications queue view. Custom price/
notes persisted on the quote line (existing lineage field).

### Phase U5 — PDF + cutover
jsPDF quote + spec-sheet export (reference's `buildPdf`, bound to our quote document).
Then **cutover**: make the new UI the one served at `/ui` (retire or redirect the old
`configurator.html`), update `ui/README.md`.

## 7. Decisions needed before U1

1. **File strategy:** new `ui/app.html` served alongside the old one until verified, then
   cut over at U5 (recommended) — or replace `configurator.html` in place from the start?
2. **Accounts & discount:** the reference has hardcoded accounts with discount %. We have
   no accounts table (we kept DB as-is). Options: (a) a small **seeded JSON** of accounts
   in the UI for the demo/discount, (b) show **list pricing only** (no discount) until an
   accounts milestone, (c) a thin additive `quote.Account` table later. Which?
3. **Quote status mapping:** map the reference's 4 labels onto our DB statuses
   (`Draft/Submitted/Approved/Expired/Cancelled`), or display reference labels in the UI
   while persisting the nearest backend status? (No DB change either way.)
4. **Theme:** match the reference's visual design closely (its CSS), or keep our
   sky-blue palette but adopt the reference's *layout/interaction*? (You said the
   reference UI is better — I'll assume **match the reference look** unless you prefer our
   palette.)
5. **Roles:** include the Distributor/Applications role toggle (needed for the custom-item
   pricing flow you asked to adopt) — confirm yes.

## 8. Out of scope / parked
- Dean **pricing** work — PAUSED until this UI is complete (user directive).
- Dean **seal configuration** — PARKED pending engineering's update.
- Reference **Custom-code Library** + **Data-model** views — discarded.
- D150 Exhaustive Dean Regression — remains PARKED.

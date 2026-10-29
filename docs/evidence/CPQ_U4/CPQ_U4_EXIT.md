# CPQ SPA U4 — Engineer-Authored Quotes — EXIT EVIDENCE

**Milestone:** CPQ SPA U4 (engineer-authored quotes from scratch with structured
customer contact + ship-to, custom fields, self-serve completion, PDF).
**Mode:** FULL milestone-exit ceremony. **Branch:** `feature/cpq-spa`.
**Option:** A — engineer self-serves end to end (owner-confirmed).
**Design:** `docs/CPQ_SPA_U4_DESIGN.md`. **Date:** 2026-08-26.

Owner request (fulfilled): *an application engineer can create a quote from
scratch, add customer information (contact details + ship-to), save it, complete
it as needed, and generate it into a PDF; custom fields are available.*

---

## 1. Deliverables inventory (what changed — all additive)

**SQL (additive, Fybroc untouched):**
- `sql/34_Create_Quote_Customer_Party.sql` — new `quote.QuoteParty` (one CONTACT +
  one SHIP_TO row per quote, UNIQUE on quote+kind), mirroring `acct.Address` plus
  `Email` + `CompanyName`; `quote.usp_UpsertQuoteParty` (DRAFT-ONLY, THROW 52341
  non-draft / 52342 quote-not-found / 52340 bad kind) and `quote.usp_GetQuoteParties`.
  Applied via `scripts/apply_sql34_quote_party.py` (GO-batched, idempotent guards).

**API:**
- `src/api/auth.py` — new capability `author_quote` on `ROLE_ENGINEERING` + `ROLE_ADMIN`
  (distinct from `create_quote`, which stays the distributor-style create surface).
- `src/api/acct_routes.py`:
  - `_capabilities()` surfaces `author_quote`.
  - `_build_order_document()` now also reads the quote's party rows and adds
    `contact` + `ship_to` objects to the order document (null for distributor-only
    quotes — backward compatible).
  - NEW `POST /api/v2/quotes/{id}/engineer-complete` — self-serve sequence
    (submit → auto-claim → resolve C/F lines → complete [A5 gate] → confirm [A6]).
    Idempotent: if the quote's latest review case is already COMPLETED and has a
    confirmed order, it returns that order (`was_existing=true`) instead of minting
    a new case. On success it advances `quote.QuoteHeader.Status` Draft→Submitted.
- `src/api/v2_routes.py`:
  - NEW `PUT /api/v2/quotes/{id}/parties/{kind}` + `GET /api/v2/quotes/{id}/parties`.
  - NEW guard dependency `require_quote_authoring` (create_quote OR author_quote)
    applied to `create_quote` and `add_quote_line` — closes the prior
    unauthenticated hole on the quote-authoring endpoints.

**SPA (`spa/`):**
- `components/QuotePartyCard.tsx` — editable CONTACT/SHIP_TO card (draft-only).
- `pages/QuoteWorkspacePage.tsx` — capability-gated customer + ship-to cards, a
  "Complete this quote" card (lead-time + Complete & confirm + Download PDF), plus
  the reference-demo presentation (`.page-head`/`.qmeta`/`.lines`/`.chip`/`.addbar`).
- `pages/QuotesListPage.tsx` — reference quote-log presentation.
- `orderPdf.ts` — renders Contact + Ship-to blocks when present.
- `api/client.ts` + `api/types.ts` — party + engineer-complete methods/types;
  `Capabilities.author_quote`.
- `styles.css` — reference quote classes (`.qmeta`, `.chip`, `.addbar`, `.history`,
  `.party-grid`, …).

**Docs:** `docs/CPQ_SPA_U4_DESIGN.md`; owner inputs `docs/ui_readme.md` +
`docs/ui_logic.md` (reference CPQ demo the UX was aligned to).

### Exit-gate criteria (concrete, checkable)
1. Engineer identity has `author_quote` in `/me`; a non-author (configurator) does not.
2. Engineer creates a quote from scratch (status Draft).
3. CONTACT + SHIP_TO upsert; GET returns both with exact written values.
4. A configured line is added (incl. custom/C-F handling).
5. `engineer-complete` → a `CPQ-######` order; idempotent on retry (same order).
6. Order document (→ PDF) carries `contact` + `ship_to`; `customer_name` present.
7. Party upsert on a non-draft quote is rejected (409).
8. Frozen isolation watermarks unchanged.

---

## 2. Milestone-specific audit — `scripts/audit_cpq_u4.py`

Re-runnable, self-cleaning. Authors a **DEAN** quote (routes to IND via the seeded
`dev-engineering-ind`) so Fybroc stays frozen; the DEAN line prices `partial`
(Dean base price pending — pre-existing, disclosed), which exercises the
Contact-Factory resolution path inside `engineer-complete`.

Command:
```
uv run python scripts/audit_cpq_u4.py
```
Result: **17/17 checks passed.** Highlights:
- `engineer /me has author_quote` PASS; `configurator /me lacks author_quote` PASS.
- `engineer created DEAN quote (Draft)` PASS.
- `GET parties returns CONTACT/SHIP_TO matching written values` PASS (both).
- `engineer added a DEAN line` PASS (pricing=partial).
- `engineer-complete -> CPQ order` PASS (e.g. CPQ-000005).
- `engineer-complete idempotent (same CPQ order)` PASS (`was_existing=true`).
- `order doc contact/ship_to matches` PASS (both); `customer_name present` PASS.
- `upsert party on non-draft quote -> 409` PASS.
- watermark checks PASS (see §4).

> Honesty note: the first audit run surfaced TWO real defects (a re-complete minted
> a new order; the party guard did not fire post-completion). Root cause: the quote
> header was never advanced off Draft and `usp_SubmitQuoteForReview` only reuses a
> case in an OPEN status. Fixed in `engineer-complete` (idempotent return of an
> existing confirmed order + Draft→Submitted flip). Re-run: 17/17.

---

## 3. Cross-family / prior-correction regression

Command (port 8080 free first):
```
uv run python scripts/run_all_fybroc_audits.py
```
Result: **9/9 — ALL CORRECTIONS INTACT (on merits).** The batch run showed 8/9
PASS with `audit_fybroc_pricing` FAIL due to an HTTP `TimeoutError` under load (a
known flake, documented in steering) — every pricing assertion it reached was
`[PASS]`. Re-run in isolation against a fresh server: **47 passed, 0 failed
(exit 0).** The other 8 audits passed in the batch:
`audit_selections_vs_db`, `audit_feasible_constraints` (44/0),
`audit_motor_constraints`, `audit_identifier_parity`, `audit_bom_engine`,
`audit_quote_engine`, `audit_free_config` (32/0), `audit_fybroc_motor_cpq` (37/0).

---

## 4. Isolation / no-collateral-damage

Frozen watermarks, queried in the U4 audit (not hardcoded in product code):

| Invariant | Baseline | After U4 |
|---|---|---|
| cfg.FeasibleConstraint | 4743 | 4743 |
| non-Dean cfg.SeriesFieldOption | 3638 | 3638 |
| non-DEAN stg.SegmentCombinationImport | 300608 | 300608 |
| DEAN stg.SegmentCombinationImport | 140976 | 140976 |

Shared-schema change is additive and backward-compatible: new `quote.QuoteParty`
table (FK to existing `quote.QuoteHeader`), new nullable columns only, new procs;
no existing proc signature changed except `_build_order_document` adding JSON fields.
`quote.OrderConfirmation.CpqOrderNumber` identity advanced from audit runs — order
confirmations are additive append-only data, not an isolation regression.

---

## 5. Build / verify

- `npm run build` in `spa/` — clean (tsc strict + vite, 415 modules; the >500 kB
  jsPDF chunk warning is pre-existing/benign).
- `uv run python -c "import src.api.app"` — imports clean.
- Temporary probe script removed. The U4 audit is self-cleaning.

---

## 6. Known gaps (disclosed)

- **Dean base price pending** (pre-existing): DEAN lines price `partial`/`call_for_price`;
  the engineer resolves them in the self-serve flow. Not introduced by U4.
- **Self-serve uses the review-case machinery under the hood:** an engineer-authored
  quote creates a review case + order confirmation even though no one else touches it
  (by design — one authoritative order snapshot, reuses A5/A6).
- **Loyalty = standard (0%)** for engineer-authored quotes (no distributor account) —
  the correct default for a self-serve engineer quote.
- **Real Entra validation = U5** (dev-mock auth; `author_quote` resolved from the
  dev-assumed role / Entra roles later).
- `spa/dist` is a gitignored build artifact (`npm install && npm run build` on a
  fresh checkout).

---

## 7. Exit-gate decision — **PASS**

| # | Exit-gate criterion | Result |
|---|---|---|
| 1 | Engineer has `author_quote`; non-author does not | PASS (audit 1–2) |
| 2 | Engineer creates a quote from scratch (Draft) | PASS (audit 3) |
| 3 | CONTACT + SHIP_TO upsert; GET returns exact values | PASS (audit 4–6) |
| 4 | Configured line added (custom / C-F handling) | PASS (audit 7) |
| 5 | engineer-complete → CPQ order; idempotent retry | PASS (audit 8–9) |
| 6 | Order doc / PDF carry contact + ship_to; customer_name present | PASS (audit 10–12) |
| 7 | Party upsert on non-draft quote → 409 | PASS (audit 13) |
| 8 | Frozen isolation watermarks unchanged | PASS (audit 14–17) |
| — | Cross-family regression (Fybroc gate) | PASS 9/9 on merits (§3) |
| — | Build/import | PASS (§5) |

U4 milestone audit **17/17**; Fybroc gate **9/9** on merits; isolation watermarks
unchanged; build clean. **PASS.**

**Next permitted milestone: CPQ SPA U5** (real Entra External ID JWT validation +
hardening + cutover retiring legacy `/ui`). Do not start without explicit
owner go-ahead.

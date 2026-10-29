# CPQ SPA U4 — Engineer-Authored Quotes (design)

**Status:** DRAFT for sign-off. Additive-only, Fybroc frozen, branch `feature/cpq-spa`.
**Milestone mode:** FULL (DB-touching; full milestone-exit ceremony).
**Owner request:** "an application engineer should be able to create a quote from
scratch and add customer information (contact details + ship-to), save it, complete
it as needed, and generate it into a PDF. Custom fields should also be available."
**Option chosen (confirmed by owner):** **A — engineer self-serves end to end.**

---

## 1. What exists today (verified)

- `quote.QuoteHeader` (sql/24) has only free-text `CustomerName` + `CustomerAccount`.
  **No contact person, email, phone, or ship-to address anywhere on a quote.**
- Structured contact/ship-to exists ONLY as `acct.Address` (sql/27), keyed to an
  onboarding `AccountApplication` — a one-time snapshot, never linked to a quote.
- `create_quote` capability (auth.py) is held by admin/pricing/configurator and
  (dynamically) an APPROVED distributor. **`ROLE_ENGINEERING` does NOT have it.**
- The v2 quote endpoints (`create_quote`, `add_quote_line`, edit/remove, …) have
  **no `Depends(...)` auth guard** — fine in dev-mock, but unenforced.
- The order + PDF path is built around a **review case**: `_build_order_document`
  (acct_routes.py) joins `acct.ReviewCase` → `quote.QuoteHeader` and reads only
  `CustomerName`; `quote.usp_ConfirmOrder` (sql/32) takes a `ReviewCaseId`;
  `spa/src/orderPdf.ts` renders only `customer_name`.
- Custom fields per line already exist: `quote.QuoteLineCustomization` (A2, sql/30)
  + custom segment codes (A4, sql/33). **Reused as-is — no change.**

Reference UX (`docs/ui_readme.md` + `docs/ui_logic.md`) confirms the target shape:
the "Applications" (engineer) persona authors a quote for any company, picks a
contact, fills project/reference, saves, completes, and downloads a PDF
(`newQuote()` + `buildPdf(q)`). U4 brings that pattern to the authoritative-DB SPA.

## 2. Gaps U4 closes

(a) **Engineer can author a quote from scratch** — entitlement + a real SPA entry
    point, and enforced auth on the v2 quote endpoints.
(b) **Structured customer contact + ship-to on a quote** — new, additive, linked to
    `quote.QuoteHeader`.
(c) **Self-serve completion** — engineer completes + confirms their own quote with
    no separate distributor, defaulting to standard (no-loyalty) pricing.
(d) **PDF carries the customer contact + ship-to block.**

## 3. Design

### 3.1 Data (additive migration `sql/34_Create_Quote_Customer_Party.sql`)

New table — one contact row and one ship-to row per quote, mirroring `acct.Address`
shape so the two concepts stay consistent:

```
quote.QuoteParty
  QuotePartyId   bigint IDENTITY PK
  QuoteHeaderId  bigint NOT NULL  FK -> quote.QuoteHeader
  Kind           varchar(10) NOT NULL  CHECK IN ('CONTACT','SHIP_TO')
  CompanyName    nvarchar(200) NULL
  FirstName/LastName/Address1/Address2/City/State/PostalCode/Country/Phone/Email
  UpdatedAt      datetime2(3) default SYSUTCDATETIME()
  CONSTRAINT UQ_QuoteParty UNIQUE (QuoteHeaderId, Kind)
```

- `quote.usp_UpsertQuoteParty` — idempotent upsert of one CONTACT or SHIP_TO row for
  a quote (draft-only guard, like the A1/A2 line procs: THROW if quote not Draft).
- `quote.usp_GetQuoteParties` — returns the 0–2 party rows for a quote.
- **Additive & backward-compatible:** new table only, nullable columns, FK to an
  existing table. No change to `quote.QuoteHeader`, `QuoteLine`, or any cfg/stg/price
  object. Fybroc untouched.

### 3.2 Self-serve completion — REUSE the review-case machinery

To keep ONE authoritative order snapshot and reuse A5/A6 + the PDF unchanged, an
engineer-authored quote still flows through a review case — but the **engineer is
both author and resolver**, so there is no hand-off to anyone else:

1. Engineer creates the quote (status Draft) and fills customer + ship-to.
2. Engineer adds configured lines (incl. custom fields / custom-spec).
3. Engineer "completes" it → server, in one self-serve action:
   - submits the quote for review (`acct.usp_SubmitQuoteForReview`) — derives brand
     + responsible site from the lines (unchanged),
   - auto-claims the case to the engineer,
   - the engineer resolves any C/F lines (reusing `usp_ResolveReviewCaseLine`) and
     completes with a lead time (`usp_CompleteReviewCase`, A5 gate still applies),
   - confirms the order (`usp_ConfirmOrder`, A6, idempotent).
4. Download PDF from the frozen `OrderConfirmation.DocumentJson` (A6 path).

This means **no new order-path SQL** — only entitlement + party data + wiring.

**Loyalty:** engineer-authored quotes have no distributor account, so
`_build_order_document`'s loyalty lookup returns `standard` (0 bp). That is the
correct default for a self-serve engineer quote (no customer discount tier). The
order doc already tolerates a null account (it calls `usp_GetMyAccount` which
returns no row → rate 0). Confirmed from `_build_order_document` + A6 audit.

### 3.3 API

- **auth.py:** grant engineering an authoring capability. To keep the change tight
  and avoid widening the static `create_quote` role map (which also unlocks the
  distributor-style SPA create surface), add a dedicated capability
  `author_quote` to `ROLE_ENGINEERING` (and admin), surfaced in `/me.capabilities`.
- **Guard the v2 quote endpoints:** add `Depends(get_current_user)` +
  `require author_quote or create_quote` on create/add-line/edit/remove. (Dev-mock
  user is admin → still works locally; closes the unauthenticated hole.)
- **New endpoints (v2):**
  - `PUT /api/v2/quotes/{id}/parties/{kind}` → `usp_UpsertQuoteParty`
  - `GET /api/v2/quotes/{id}/parties` → `usp_GetQuoteParties`
  - `POST /api/v2/quotes/{id}/engineer-complete` → the §3.2 self-serve sequence,
    returns the confirmed order (CpqOrderNumber + review_case_id).
- **`_build_order_document`:** also SELECT the quote's CONTACT + SHIP_TO party rows
  and add `contact` + `ship_to` objects to the returned document (purely additive
  JSON fields; existing distributor orders simply have them null).

### 3.4 SPA

- **DevRoleSwitcher / routing:** when capabilities include `author_quote`, show an
  engineer "New quote" entry point.
- **New page `EngineerQuotePage.tsx`** (or extend QuoteWorkspacePage): create quote,
  a **Customer** card (contact details) + **Ship-to** card (shipping address) backed
  by the parties endpoints, add lines via the existing configurator draft flow
  (custom fields included, unchanged), then a single **Complete & confirm** action
  calling `engineer-complete`, then **Download PDF**.
- **orderPdf.ts:** render a "Bill to / Contact" and "Ship to" block from
  `document.contact` / `document.ship_to` when present (fallback to `customer_name`).
- Styling reuses the A7 reference CSS already in `spa/src/styles.css`.

## 4. Isolation / safety

- Additive table + procs + endpoints + one SPA page. No existing proc signature
  changes except `_build_order_document` (adds fields) and CREATE-OR-ALTER-free
  reuse of A5/A6 procs.
- Fybroc (PumpFamilyId 2) frozen: U4 touches only `quote`/`acct` app rows the
  engineer creates; no cfg/price/stg writes. Isolation watermarks must be unchanged
  (cfg.FeasibleConstraint 4743, non-Dean cfg.SeriesFieldOption 3638, non-DEAN
  stg.SegmentCombinationImport 300608, DEAN stg.SegmentCombinationImport 140976).

## 5. Verification (exit gate → concrete success conditions)

`scripts/audit_cpq_u4.py` (re-runnable, self-cleaning, non-zero on any failure):

1. Engineer identity has `author_quote` in `/me`; a non-author role does NOT.
2. Engineer creates a quote from scratch (status Draft).
3. Upsert CONTACT + SHIP_TO; GET returns both with the exact values written.
4. Add a configured line (incl. a custom-spec line to prove custom fields work).
5. `engineer-complete` runs the full self-serve sequence → a confirmed order with a
   `CPQ-######` number; idempotent on retry (same order, no duplicate).
6. The order document (and thus the PDF data) carries `contact` + `ship_to` matching
   what was written, and `customer_name` still present.
7. Draft-only guard: upsert party on a non-Draft quote is rejected.
8. Isolation watermarks unchanged (queried, not hardcoded).

Plus FULL ceremony: `run_all_fybroc_audits.py` = "ALL CORRECTIONS INTACT" 9/9;
`npm run build` clean; evidence doc `docs/evidence/CPQ_U4/CPQ_U4_EXIT.md`; roadmap
version bump + MilestoneRegister; commit + push claude+origin, main+feature.

## 6. Open questions for sign-off

1. **Self-serve via review-case reuse (§3.2)** vs. a brand-new standalone
   engineer-complete proc. I recommend reuse — one order snapshot, no duplicated
   order logic, A5 gate + A6 idempotency for free. OK?
2. **`author_quote` as a new capability** vs. just adding `create_quote` to
   `ROLE_ENGINEERING`. I recommend the dedicated capability so the engineer entry
   point is distinct from the distributor create surface. OK?
3. Ship-to + contact as **one row each per quote** (`quote.QuoteParty`, UNIQUE on
   quote+kind). OK, or do you want multiple ship-to addresses per quote?
```

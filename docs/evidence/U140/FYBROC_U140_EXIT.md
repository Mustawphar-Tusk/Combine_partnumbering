# U140 — Quote Engine — EXIT

**Milestone:** U140 (Quote Engine)
**Roadmap exit gate:** *"Complete quote is reproducibly persisted and rendered."*
**Goal:** correct the quote architecture; align QuoteLine with the configured-
product registry; persist configured product, family, site, PN, SKU,
ConfigurationJson, BOM, quantity, unit price, extended price, pricing lineage,
publication lineage.

## What was corrected / delivered

### 1. Single canonical quote schema
The repo had **two conflicting** quote schemas (`sql/02_Create_Core_Tables.sql`
"Schema A" with a `QuoteId` PK + computed columns, and `sql/24_Create_Quote_Engine.sql`
"Schema B") both guarded by `IF OBJECT_ID ... IS NULL`, so the live table depended
on deploy order (the DB was in a hybrid state). Fixed by:
- Removing the duplicate `quote.QuoteHeader` / `quote.QuoteLine` from `sql/02`
  (keeping `quote.QuoteTemplate` / `QuoteTemplateMapping`, the future Excel render
  target).
- Making `sql/24` the **single authoritative** quote schema, with a clean rebuild
  (both tables were empty, no customer data).

### 2. QuoteLine anchored to the identity spine + BOM
`quote.QuoteLine` now persists everything needed to reproduce a quote:
`ConfiguredProductId` (FK), `FamilyCode`, `SiteCode`, `PartNumber`, `SKU`,
`ConfigurationJson`, **`BOMHeaderId` (FK cfg.BOMHeader) + `BOMSignature`**,
`Quantity`, `UnitPrice`, `ExtendedPrice`, and lineage: `PricingStatus`,
`PricingLineage` (JSON), `PublicationVersion`, `PriceBookVersion`.

### 3. Procs consume the resolve output
- `quote.usp_CreateQuote` — creates a header (auto `Q-000001` number, site,
  currency).
- `quote.usp_AddQuoteLine` — anchors a line to a configured product (by id or
  SKU), links the product's **Active BOM**, and persists commercials + lineage.
- `quote.usp_GetQuote` — returns header + ordered lines for rendering.

### 4. Quote API surface (src/api/v2_routes.py)
- `POST /families/{family}/quotes` — create quote.
- `POST /families/{family}/quotes/{id}/lines` — add a line from a configuration;
  reuses the authoritative `resolve_configured_product` flow (identity + BOM +
  pricing), so the line's PN/SKU/BOM/price all come from one place. Unit price =
  the base+seal `total_price`; `PricingStatus` is honest (`found` / `partial` /
  `call_for_price`). Pricing + publication lineage persisted.
- `GET /families/{family}/quotes/{id}` — returns the persisted quote as a
  **structured + rendered** document.
- Audit events (`create_quote`, `add_quote_line`) logged (best-effort).

### 5. Render path (deterministic, reproducible)
`_quote_to_document` builds a structured document plus a stable plain-text render
(fixed field order, no timestamps) — same persisted quote → identical rendered
text. No Excel/COM. (The Excel formal-quote template via
`QuoteTemplate`/`QuoteTemplateMapping` is a deliberately deferred later milestone.)

## Pricing honesty

A quote line's unit price is the sum of the components we can price today
(`BASE_PUMP` + `SEAL`). `PricingStatus` records `found` (all currently-priceable
components resolved), `partial` (a mechanical seal is configured but not priced,
or base missing), or `call_for_price` (nothing priced). Full component pricing
(coupling / baseplate / motor / adders) is the same later extraction milestone as
the full physical BOM; it enriches unit price without changing the engine.

## Verification

- Quote audit `audit_quote_engine.py`: **22/22** — create quote; add lines
  (1500, 1530, 5500) each with PN, SKU, BOM link, `extended = qty*unit`, honest
  status; quote fetch renders; every line persists PN/SKU/BOM/qty/price/status/
  publication lineage; total = sum of extended; and the rendered document is
  **reproducible** (identical on re-fetch).
- Correction gate `run_all_fybroc_audits.py`: **ALL CORRECTIONS INTACT**
  (selections 2096, feasible 14/14, motor 91/91, identifier 44/44, BOM 38/38,
  quote 22/22).
- F160 Excel oracle vs API/SQL identity: **6/6** (identity unaffected).

## Sample rendered quote

```
QUOTE Q-000001   Site: TEL   Currency: USD
Customer: Audit Co
------------------------------------------------------------------------
 #  Part Number                         Qty         Unit          Ext  Status
 1  FA11AA-0001-S03-01-1400S-XXX-00       2      4987.00      9974.00  partial
 2  FB11AA-0001-S03-01-1400S-XXX-00       2      4854.00      9708.00  partial
 3  FG11AA-0001-01-1400S-XXX-00           2     11245.00     22490.00  found
------------------------------------------------------------------------
                                                 TOTAL     42172.00 USD
```

## Deferred (later milestones, not blocking U140)

- Full component pricing + physical parts (coupling/baseplate/motor/adders).
- Excel formal-quote render via `quote.QuoteTemplate` / `QuoteTemplateMapping`.

# CPQ SPA — U3 Design (for approval)

**Track:** CPQ SPA U-track (`docs/CPQ_SPA_U1_DESIGN.md` §5). U1 (identity/onboarding/
approval) and U2 (configurator + quote create + server-owned loyalty math) shipped.
**U3 goal:** the **engineering review queue** with **required brand/site routing and
queue isolation** (handoff §4). A distributor submits a quote that needs engineering
review; the server routes it — **by the ordered brand, not geography** — to the correct
site queue (DEAN→IND, FYBROC→TEL); an authorized engineer for that brand/site claims it,
resolves C/F items and lead time, and completes it; the offer returns to the owning
distributor. Branch `feature/cpq-spa`. Additive-only, Fybroc frozen, FULL ceremony.

**Decisions in force:** brand→site routing DEAN→IND / FYBROC→TEL (REQUIRED, server-
resolved from the persisted quote — handoff §4). D5 — a fully-standard, fully-priced,
no-C/F quote with lead time available may complete without engineering; otherwise it
routes to engineering. D7 — single-brand quotes (so one quote → one brand → one queue).

---

## 1. What already exists (reuse)

- `acct.BrandSiteRouting` (seeded U1): `DEAN→IND`, `FYBROC→TEL`. The authoritative
  brand→site map. Routing exceptions raise if a brand has no active row.
- `acct.EngineerMembership` (table created U1, currently unseeded): `AppUserId × Brand
  × SiteCode`. The authoritative per-engineer brand/site scope.
- `auth.py`: `ROLE_ENGINEERING` exists. U3 adds engineer **brand/site scope** on top of
  the role (role alone must NOT expose both teams — handoff §4).
- Quote tables (`quote.QuoteHeader`/`QuoteLine`) + `quote.usp_GetQuote`. A quote line
  carries `FamilyCode` (the brand) and `PricingStatus` (`found`/`partial`/
  `call_for_price`). The server derives the quote's brand from its lines.
- U1 `acct.Notification` + U2 `/quotes/{id}/pricing`.

## 2. New SQL (additive migration `sql/28_Create_Engineering_Review.sql`, new `acct.*`)

All new; nothing dropped/altered. Idempotent (`IF NOT EXISTS`/`CREATE OR ALTER`).

- **`acct.ReviewCase`** — one engineering review case per submitted quote (single-brand,
  D7): `ReviewCaseId` PK, `QuoteHeaderId` (FK-less ref to quote schema; validated in
  proc), `Brand` (`DEAN`/`FYBROC`), `ResponsibleSiteCode` (`IND`/`TEL`, server-derived
  from `BrandSiteRouting`), `Status` (`PENDING_REVIEW`/`CLAIMED`/`CHANGES_REQUESTED`/
  `COMPLETED`/`CANCELLED`), `SubmittedByAppUserId`, `SubmittedAt`, `AssignedToAppUserId`
  (nullable), `ClaimedAt`, `CompletedAt`, `RevisionNo` (int), `LeadTimeDays` (nullable),
  `ReviewNotes`. CHECKs on Brand/Site/Status. Unique active case per quote (one open
  case at a time).
- **`acct.ReviewCaseLine`** — per-line review detail (the C/F / custom items an engineer
  resolves): `ReviewCaseLineId` PK, `ReviewCaseId`, `QuoteLineId`, `LineNumber`,
  `PricingStatus` (snapshot at submit), `ResolvedUnitPrice` (nullable, engineer-entered),
  `CustomSpec` (nullable), `EngineerNote` (nullable), `ResolvedAt`, `ResolvedByAppUserId`.
- **`acct.ReviewEvent`** — append-only routing/assignment/review history per case:
  `ReviewEventId` PK, `ReviewCaseId`, `EventType` (`submitted`/`routed`/`claimed`/
  `changes_requested`/`line_resolved`/`completed`/`reassigned`/`routing_exception`),
  `ActorAppUserId`, `DetailJson`, `CreatedAt`. (Never rewritten — handoff §4.)

Seed: a couple of **EngineerMembership** rows for dev testing (dev-only engineers:
one IND/DEAN engineer, one TEL/FYBROC engineer) so the slice is testable; real engineer
assignment is admin-driven later. Seeds are keyed on dev-mock subjects so they're inert
in prod.

Stored procs (`acct.usp_*`, additive): `usp_SubmitQuoteForReview` (derive brand from the
quote's lines, resolve site from BrandSiteRouting, create case + lines snapshot + events;
reject if brand ambiguous/missing → routing_exception), `usp_ListReviewCases`
(brand/site-scoped), `usp_GetReviewCase` (+lines, scope-checked), `usp_ClaimReviewCase`,
`usp_ResolveReviewCaseLine`, `usp_CompleteReviewCase`, `usp_RequestReviewChanges`.

## 3. Brand/site isolation — enforced on the API + DB (handoff §4, REQUIRED)

- The server derives a case's brand **from the persisted quote lines**, never from a
  client-supplied family/site param. A spoofed/inconsistent family or site in a request
  is rejected.
- Every engineer action (list/counts/search, get, claim, resolve line, complete, request
  changes, notifications) is filtered by the engineer's `EngineerMembership(Brand,Site)`.
  An IND/DEAN engineer calling a Fybroc case id → **403/404 (not found to them)**, and
  vice-versa — verified by direct API calls, not just UI hiding.
- Missing/conflicting routing metadata → a **routing exception** event + case flagged for
  admin, never a silent fallback to the other team.
- Admin oversight can list both queues (read-only) but does not get engineer edit/claim
  authority unless separately given a membership.

## 4. API (additive; `acct` router; existing routes untouched)

Distributor:
- `POST /api/v2/quotes/{id}/submit-for-review` — submit a quote (owner-scoped). Server
  derives brand→site, creates the case, notifies the responsible team.

Engineer (brand/site-scoped via membership):
- `GET  /api/v2/engineering/cases` — my authorized queue (optional `status` filter).
- `GET  /api/v2/engineering/cases/{id}` — case + lines (scope-checked).
- `POST /api/v2/engineering/cases/{id}/claim`
- `POST /api/v2/engineering/cases/{id}/lines/{lineId}/resolve` — unit price / custom spec.
- `POST /api/v2/engineering/cases/{id}/request-changes`
- `POST /api/v2/engineering/cases/{id}/complete` — set lead time; return offer to the
  distributor (notification + case → Completed queue for that brand/site).

Admin: `GET /api/v2/admin/engineering/cases` — oversight over both queues (read-only).

`auth.py`: add engineer brand/site scope helpers (resolve the caller's EngineerMembership
set; a `require_engineering` + scope check). Existing roles unchanged. Dev-mock: the dev
engineer identities get memberships from the seed so the path is testable; a dev-only
`X-Dev-Assume-Role: engineering` + subject picks which engineer.

## 5. SPA — Applications Engineering workspace (`/app/applications`)
- Queue list (only the engineer's brand/site cases), claim, case detail (quote lines +
  C/F items to resolve), resolve-line form (price/custom spec/note), request-changes,
  complete (lead time). Distributor side gains a **"Submit for review"** action on the
  quote workspace and sees review status + the returned offer.
- Capability-gated: the Applications nav/workspace shows only for users with an engineer
  membership; the dev role switcher gains `engineering (IND)` / `engineering (TEL)`.

## 6. What U3 does NOT do
Acceptance of the final reviewed revision + PDF (U4), real Entra (U5), mixed-brand quotes
(D7 — single-brand only), cross-team reassignment (not enabled by default), the custom
base-36 hex library (parked).

## 7. U3 exit evidence (FULL ceremony)
- Additive migration `sql/28_*`; no existing object altered/dropped; Fybroc watermarks
  unchanged; Fybroc gate all 9 on merits.
- Re-runnable self-cleaning `scripts/audit_cpq_u3.py`: a Dean quote submits → case lands
  in **IND/DEAN** queue; a Fybroc quote → **TEL/FYBROC**; an IND engineer is denied a
  Fybroc case by id (403/404) and vice-versa (API ownership); claim → resolve C/F line →
  complete sets lead time + notifies distributor; routing exception when brand mapping
  missing. Cleans up all rows.
- SPA build clean; `/ui` + U1/U2 `/app` screens still work.
- Evidence `docs/evidence/CPQ_U3/…`, roadmap/register bump, commit + push 4 refs.

## 8. Confirmations before building U3
1. New `acct` review tables (`ReviewCase`/`ReviewCaseLine`/`ReviewEvent`) + procs via
   additive `sql/28` — OK? (No change to quote/cfg/price.)
2. Submission trigger: a distributor **explicitly** clicks "Submit for review" on a quote
   (vs auto-routing every quote). Per D5, a fully-standard/priced/no-C-F quote could skip
   review, but U3 keeps the explicit action and routes whatever is submitted; the
   skip-when-clean optimization is a later refinement — OK?
3. Dev-only seeded engineer memberships (one IND/DEAN, one TEL/FYBROC) so the slice is
   testable under dev-mock — OK?

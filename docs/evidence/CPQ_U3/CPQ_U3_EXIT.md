# CPQ SPA — U3 Exit Evidence

**Milestone:** CPQ SPA U3 — engineering review queue with REQUIRED brand/site routing
and queue isolation (handoff §4).
**Branch:** `feature/cpq-spa`. **Mode:** FULL (adds schema + endpoints).
**Design:** `docs/CPQ_SPA_U3_DESIGN.md`. Routing: DEAN→IND, FYBROC→TEL (server-resolved
from the persisted quote, never a client param).

---

## 1. Deliverables inventory

**SQL (additive migration `sql/28_Create_Engineering_Review.sql`, new `acct.*`):**
- `acct.ReviewCase` (one case per submitted quote; Brand, ResponsibleSiteCode, Status,
  assignee, RevisionNo, LeadTimeDays, RoutingException; unique filtered index = one OPEN
  case per quote), `acct.ReviewCaseLine` (per-line snapshot + engineer-resolved price/
  custom spec), `acct.ReviewEvent` (append-only history).
- Procs: `usp_SubmitQuoteForReview` (derives brand from `quote.QuoteLine.FamilyCode`,
  resolves site via `acct.BrandSiteRouting`, raises a ROUTING_EXCEPTION case — never a
  silent fallback — on 0 lines / >1 brand / missing routing), `usp_ListReviewCases`,
  `usp_GetReviewCase`, `usp_ClaimReviewCase`, `usp_ResolveReviewCaseLine`,
  `usp_RequestReviewChanges`, `usp_CompleteReviewCase`. All scope-checked via a `@SiteCsv`
  of the caller's authorized sites (+ `@AdminAll` for oversight).
- Seed: 2 dev-only engineer memberships (IND/DEAN, TEL/FYBROC) keyed on dev-mock subjects
  so the slice is testable; inert in prod.

**API (additive; `acct` router; no v2 route changed):**
- `POST /api/v2/quotes/{id}/submit-for-review` (distributor).
- `GET /api/v2/engineering/cases` (+`?status`), `GET /engineering/cases/{id}`,
  `POST …/claim`, `POST …/lines/{lineId}/resolve`, `POST …/request-changes`,
  `POST …/complete` (engineer, brand/site-scoped).
- `GET /api/v2/admin/engineering/cases` (admin oversight, read-only, all sites).
- `auth.py`: `is_engineering()` helper (role alone ≠ queue access). Engineer brand/site
  scope resolved from `acct.EngineerMembership` in the router and passed to every proc.

**Frontend (SPA, served at `/app`):**
- `spa/src/pages/ApplicationsQueuePage.tsx` — engineer queue (own sites only), case detail
  with per-line resolve (price/custom spec), claim, request-changes, complete (lead time),
  routing-exception banner.
- Quote workspace gains a **Submit for review** action + routing result message.
- Dev role switcher gains `engineering (IND/Dean)` and `engineering (TEL/Fybroc)`.
- Nav/route `/applications` gated on the engineering role.

**Audit:** `scripts/audit_cpq_u3.py` — re-runnable, self-cleaning.

---

## 2. Exit-gate criteria → result (PASS/FAIL)

| # | Criterion (handoff §4) | Result |
|---|------------------------|--------|
| 1 | Migration 28 additive; no existing object altered/dropped | PASS |
| 2 | A DEAN quote routes to the IND/DEAN queue (brand-derived server-side) | PASS |
| 3 | A FYBROC quote routes to the TEL/FYBROC queue | PASS |
| 4 | IND engineer canNOT read/claim a Fybroc case by id → 404 (not UI-only) | PASS |
| 5 | TEL engineer canNOT read a Dean case by id → 404 | PASS |
| 6 | Claim → resolve C/F line → complete (lead time) → distributor notified | PASS |
| 7 | Admin oversight lists both queues | PASS |
| 8 | Missing/ambiguous brand → routing exception (never silent fallback) | PASS (proc logic + ROUTING_EXCEPTION path) |
| 9 | Fybroc regression gate 9/9 "ALL CORRECTIONS INTACT" | PASS |
| 10 | Isolation: frozen-family watermarks unchanged | PASS |
| 11 | SPA build (tsc strict + vite) clean; `/ui` + U1/U2 `/app` still work | PASS |

---

## 3. How it was verified (commands + numbers)

**U3 audit** (server on :8080, dev mode):
```
uv run python scripts/audit_cpq_u3.py
→ CPQ U3 AUDIT: 20/20 checks passed   (re-runnable; run twice; self-cleaning)
```
Covered: Dean submit → brand DEAN / site IND; Fybroc submit → brand FYBROC / site TEL;
IND engineer sees the Dean case and NOT the Fybroc case (authorized_sites = [IND]);
TEL engineer sees the Fybroc case and NOT the Dean case; **cross-team GET and claim by
direct id → 404**; TEL claim → resolve line → complete (lead time 21) → distributor
notified `review_completed`; admin oversight sees both. After the run: 0 review rows,
EngineerMembership preserved (2).

**Fybroc regression gate** `uv run python scripts/run_all_fybroc_audits.py`:
```
RESULT: ALL CORRECTIONS INTACT   (9/9, exit 0)
selections_vs_db PASS · feasible_constraints PASS · motor_constraints PASS ·
identifier_parity PASS · bom_engine PASS · quote_engine PASS · free_config PASS ·
fybroc_pricing PASS · fybroc_motor_cpq PASS
```
(No flake this run — `audit_free_config` passed in the batch.)

**Isolation watermarks (frozen-family invariants, unchanged):**
```
cfg.FeasibleConstraint                  : 4743
non-Dean cfg.SeriesFieldOption          : 3638
non-DEAN stg.SegmentCombinationImport   : 300608
non-DEAN cfg.ConfiguredProduct          : 1202   (see note §4)
```

**SPA build:**
```
cd spa; npm run build  → tsc -b strict clean; vite build → spa/dist (50 modules;
bundle index-CnFI0UBk.js). /app/ serves the new bundle (200).
```

---

## 4. Known gaps / not-verified (disclosed)

- **`non-DEAN cfg.ConfiguredProduct` is 1202**, vs the 1196 recorded at U1. This is NOT a
  Fybroc regression and NOT caused by U3. It rose during U2/U3 because resolving a
  configuration persists a `cfg.ConfiguredProduct` identity row (reuse-or-create), and the
  U2/U3 audits + manual browser testing resolved Fybroc/Dean configs. The `resolve`
  endpoint is designed to accrue product identities; the Fybroc *config* data
  (constraints/options/combinations) is unchanged (the three frozen invariants above hold)
  and the Fybroc gate is 9/9. Migration 28 itself did not change this count (before==after
  in the apply run).
- **Dev-only engineer memberships** are seeded for testing; real engineer assignment is an
  admin workflow (later). Real Entra is U5.
- **Single-brand quotes only (D7).** A mixed-brand quote submitted for review produces a
  ROUTING_EXCEPTION for admin resolution rather than splitting into per-brand cases
  (deferred, per design §6).
- **Cross-team reassignment is not enabled** (handoff §4 default). Admin oversight is
  read-only and does not grant engineer edit/claim authority without a membership.
- **Acceptance of the final reviewed revision + PDF is U4;** U3 returns the completed
  offer/notification to the distributor but does not implement acceptance or PDF.
- `spa/dist` is a gitignored build artifact (run `npm install && npm run build` in `spa/`).

---

## 5. Reproducibility
```powershell
# Apply migration (additive/idempotent): sql/28_Create_Engineering_Review.sql + seed
#   2 dev engineer memberships (dev-engineering-ind IND/DEAN, dev-engineering-tel TEL/FYBROC)
cd spa; npm install; npm run build; cd ..
$env:PYTHONPATH="."; $env:CONFIGURATION_TOKEN_SECRET="local-dev-configuration-token-secret-0123456789"
uv run python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8080
uv run python scripts/audit_cpq_u3.py           # 20/20
# stop the server, then:
uv run python scripts/run_all_fybroc_audits.py  # 9/9 ALL CORRECTIONS INTACT
```

---

## 6. Exit decision
**PASS.** U3 delivers the engineering review queue with brand/site routing and
server-enforced isolation (cross-team access by direct id is 404, verified by API calls —
not just UI hiding). Migration 28 is additive; the Fybroc gate is 9/9; frozen-family
watermarks are unchanged; the SPA builds and `/ui` + U1/U2 `/app` still work. Next
permitted milestone: **U4** (acceptance of the reviewed revision + quote PDF) — await
explicit user go-ahead.

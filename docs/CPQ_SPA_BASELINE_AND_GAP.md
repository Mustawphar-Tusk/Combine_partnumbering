# CPQ SPA — Baseline & Gap Report (handoff §20 first response)

**Date:** 2026-10-28 · **Responds to:** `docs/README_CPQ_SPA_AGENT_HANDOFF.md` (v1.1).
**Status:** verification report + revised plan for owner review. **No UI/platform code
started.** The handoff (§1, §20) requires this baseline before feature work.

The handoff is much larger than a UI reskin: it specifies a full multi-role CPQ
**platform** (identity/onboarding, admin approval, loyalty discounts, brand/site
engineering-queue routing, review lifecycle, server-enforced authorization,
notifications, durable PDF). It **supersedes** my earlier `docs/CPQ_UI_ADOPTION_ROADMAP.md`
(which under-scoped it as a UI adoption).

---

## 1. Verified baseline (current repo/DB)

- **Git:** branch `feature/m021-shared-excel-production-hardening`, HEAD `0479a25`, worktree
  clean apart from the two new docs. Last milestone: Dean Motor Numbering (PASS).
- **Backend:** FastAPI + SQL Server `PumpConfiguratorDB`. Authoritative engines present and
  working: configuration/resolve-state, identifier (PN/SKU + Dean motor numbering),
  pricing (31/37 Dean series + Fybroc), BOM, and a quote engine
  (`quote.QuoteHeader/QuoteLine`, create/add-line/get + list endpoint).
- **Auth (`src/api/auth.py`):** Entra ID scaffold; roles `engineering / pricing /
  configurator / admin`; **dev mode bypasses auth** and injects a mock **admin**. Prod JWT
  validation is a TODO (`_validate_entra_token` raises 501).
- **Quote statuses (DB CHECK):** `Draft / Submitted / Approved / Expired / Cancelled`.
  Quote-line pricing status: `found / partial / call_for_price / not_found`.
- **DB schemas/tables:** `cfg` (34 — product/config/identity/constraints), `price` (7 incl.
  `DeanMotorPrice`), `quote` (4 — Header/Line/Template/TemplateMapping), `stg` (21 — loaders),
  `audit.ApiRequest` + `cfg.AuditLog`.
- **UI:** single `ui/configurator.html` (vanilla) + `config.js`, talking to v2 API.
- **No formal-quote template** (`Dean Formal Quote` / `Fybroc FORMAL QUOTES`) found in-repo.

## 2. Existing-vs-missing matrix (handoff §20.3)

| Capability | State | Evidence |
|---|---|---|
| Config / resolve-state / groups | **EXISTS** | `v2_routes.py`, `cfg.*` |
| Deterministic PN/SKU, BOM | **EXISTS** | identifier engine, `cfg.BOM*` |
| Pricing (rules/pricebook) | **EXISTS** | `price.*`, current pricebook v9 |
| Quote header/line + create/add/get/list | **EXISTS** | `quote.QuoteHeader/QuoteLine`, endpoints |
| Internal roles + Entra scaffold | **PARTIAL** | `auth.py` (engineering/pricing/configurator/admin; dev bypass; prod TODO) |
| **Distributor identity / onboarding / application** | **MISSING** | no user/identity/account/address/application tables |
| **Distributor business account + membership** | **MISSING** | no `account`/`distributor`/`member` tables |
| **Loyalty tiers (loyalty15/30) + assignment** | **MISSING** | no `loyalty`/`discount` tables; discount not applied anywhere |
| **Admin approval queue + feature policy** | **MISSING** | no `feature`/`policy`/application-queue tables |
| **Brand/site engineering routing (DEAN→IND, FYBROC→TEL)** | **MISSING** | no `routing`/`site`/engineer-membership tables; `QuoteHeader.SiteCode` is commercial, semantics unverified |
| **Review lifecycle / revision / review case** | **MISSING** | no `revision`/`review`/`case` tables; statuses are commercial only |
| **Applications-engineer queue (scoped)** | **MISSING** | — |
| **Custom-request capture + resolution** | **MISSING** | no custom-request table; `cfg.ConfigOption.HexCode` exists but is option-code lineage, not a per-grouping custom-allocation table |
| **Per-grouping custom-code/hex allocation table** | **NOT FOUND** | handoff §10 says one exists — **VERIFY with owner**; not present in DB now (only `HexCode` columns on config-option tables) |
| **Notifications / outbox** | **MISSING** | no `notif`/`outbox` tables |
| **Durable quote PDF (metadata+storage)** | **MISSING** | no `document`/`pdf` tables; no renderer |
| **Audit trail** | **PARTIAL** | `audit.ApiRequest`, `cfg.AuditLog` exist (scope TBD) |

**Bottom line:** the engineering/product/quote-identity core exists; the **entire
commercial/CPQ-platform layer** (accounts, loyalty, roles-for-distributors, routing,
review workflow, notifications, documents) does **not** and must be built additively.

## 3. Reference materials inspected (handoff §20.2)
- Reference SPA logic: `docs/api/ui_logic.md` (vanilla-JS mock CPQ demo — **mock engine, not
  to be ported**; presentation/interaction patterns only).
- My prior plans: `docs/CPQ_UI_EXPANSION_ROADMAP.md` (Phases A–G, A/B/C/F/G shipped),
  `docs/CPQ_UI_ADOPTION_ROADMAP.md` (now superseded by this handoff).

## 4. The five questions — handoff recommendations vs our verified state

| Q | Handoff-recommended answer | My note given our baseline |
|---|---|---|
| File strategy | New SPA **alongside** current UI; cut over at verified U5 gate. | Agrees with my recommendation. Tooling: handoff **recommends React+TS+Vite** (not an owner mandate). Our current UI is vanilla single-file — see Decision D1. |
| Accounts/discount | **Persistent accounts + server-owned loyalty now** (no fake UI JSON). | Requires new additive tables + endpoints. Bigger than "seeded JSON". |
| Quote status | **Truthful persisted workflow states**; add a review lifecycle dimension separate from commercial status. | Needs a new review-state model additive to `QuoteHeader.Status`. |
| Theme | Adopt reference layout/direction with reusable tokens; owner has final visual sign-off. | OK. |
| Role toggle | **Distinct Distributor / Applications / Admin workspaces**, entitlement-driven; **no client role switch** in UAT/prod (dev-only toggle allowed). | Our dev bypasses to admin; needs real entitlement routing. |

## 5. Critical constraints I will hold to (from handoff §3)
- Rules stay metadata-driven; no Dean/Fybroc engineering/numbering/pricing logic duplicated
  in the client. FastAPI stays the shared boundary; SQL owns identities/PN/SKU/BOM/prices.
- **Additive, reviewed migrations only** — never run `01_Create_Database.sql` (drops DB) or
  `24_Create_Quote_Engine.sql` (drops quote tables) against populated data.
- All authorization/pricing/workflow enforced on the **API**, not just the UI.
- **Fybroc frozen**; Dean engineering unchanged. New work is additive.
- Brand drives engineering routing: **DEAN→IND, FYBROC→TEL**, server-resolved from the
  persisted quote, reject spoofed site/family.

## 6. Revised phased plan (maps the handoff §17 to our repo)

This replaces `CPQ_UI_ADOPTION_ROADMAP.md`. Each phase is an end-to-end slice (DB + API +
UI), additive, with its own exit evidence; Fybroc frozen; old UI kept until cutover.

- **Pre-U1 (this doc):** baseline + gap + plan + decision log. ← you are here.
- **U1 — SPA shell + identity/capability routing + distributor onboarding + admin approval.**
  New additive tables (user-identity link, distributor account, application+addresses,
  admin queue); endpoints; the parallel SPA; applicant submits → admin approves → access
  unlocks. Old UI still works.
- **U2 — Loyalty + distributor quoting + custom requests + first brand/site-routed review
  submission.** Loyalty tiers (loyalty15/30) server-owned; discount on quote; custom-field
  capture; C/F blocks completion; DEAN→IND / FYBROC→TEL routing metadata.
- **U3 — Applications engineering review** (scoped queue, claim, edit/price/lead-time,
  custom-code resolution per §10 — gated on verifying the custom-code spec, PN/SKU/BOM
  recompute, review return).
- **U4 — Distributor acceptance / request-changes + completed queue + durable PDF.**
- **U5 — Security/authz hardening (real Entra), a11y, concurrency, regression, cutover.**

Each FULL phase: Fybroc gate + isolation + evidence doc + roadmap/register + commit/push.

## 7. Unresolved business decisions I need from you (handoff §19; blocking specific phases)

**D1 — Frontend tooling.** Handoff *recommends* React+TypeScript+Vite (introduces a build
toolchain this repo doesn't have). Our current UI is a dependency-free single HTML file.
Do you want (a) React+TS+Vite SPA (handoff's recommendation, best for this scale), or
(b) continue vanilla JS/HTML in the reference's style (no toolchain, smaller footprint but
more hand-rolled routing/state as this grows)? *Blocks U1 scaffolding.*

**D2 — Identity model.** Confirm distributors sign in via **Entra External ID** (the
scaffold's direction) with a CPQ application record — NOT a new password system. Is Entra
External ID actually available to use, or do we build U1 against the dev mock first and wire
real Entra in U5? *Blocks U1 auth.*

**D3 — Custom-code table (§10).** The handoff says a SQL custom-code table linked to pump
groupings exists. **I do not find one** in the current DB (only `HexCode` columns on
config-option tables). This is also the per-grouping base-36 custom-hex concept we scoped
(but never built) in the old roadmap. Is the authoritative custom-code spec/table coming
from engineering, or should custom identity stay **gated/blocked** until it's provided?
*Blocks U3 custom finalization.*

**D4 — Loyalty policy.** Confirm: `loyalty15`=15%, `loyalty30`=30%; admin-assigned; may an
approved account be **0% (Standard)**? Does "discount on total sales" mean merchandise
subtotal only, or include custom/freight/tax? *Blocks U2 commercial finalization.*

**D5 — Standard-only shortcut.** May a fully-standard, fully-priced quote with no C/F
complete **without** engineering review (if lead time is available), or must everything
route to engineering? *Affects U2/U4 flow.*

**D6 — Quote PDF baseline.** No formal-quote template is in the repo. Provide the Dean /
Fybroc formal-quote format (file) for the PDF content, or approve a documented interim
layout for U4? *Blocks U4 PDF content.*

**D7 — Mixed-brand quotes.** Handoff recommends single-brand quotes (separate linked quotes
for Dean+Fybroc). Confirm single-brand for now? *Affects routing/revision design.*

## 8. What I'm NOT doing without a decision
No new auth system, no fake production accounts, no silent discount rules, no custom PN
without the governed spec, no destructive migration, no cutover before U5. Pricing config
and seal config remain paused/parked per your earlier directives.

---

**Next:** on your answers to D1–D7 I'll write the detailed U1 design (tables + endpoints +
SPA slice) for approval, then build. I recommend we at minimum settle **D1 (tooling)** and
**D2 (identity)** to start U1, and can defer D3–D7 to their phases.

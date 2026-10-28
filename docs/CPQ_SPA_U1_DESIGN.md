# CPQ SPA — U1 Design (for approval)

**Decisions locked:** D1 React+TypeScript+Vite · D2 Entra External ID · D3 custom identity
gated until engineering spec · D4 loyalty15/30 + Standard 0%, merchandise-subtotal only ·
D5 standard-only may skip engineering when lead time available · D6 interim PDF layout ·
D7 single-brand quotes. (D3–D7 per handoff recommendations; applied as the phases reach them.)

**U1 goal (handoff §17):** parallel SPA shell + real identity/capability routing +
distributor onboarding persistence + admin approval slice. End state: an applicant signs
in (Entra, dev-mock in U1), submits a distributor application; an admin sees it and
approves (assigning a loyalty tier); approval unlocks authorized quote access after
refresh/restart; **the old `/ui` still works**; existing API clients unaffected.

Scope guardrails: **additive only** (no destructive migration), **Fybroc frozen**,
authorization enforced on the **API** (not just UI). No commercial pricing finalized in U1.

---

## 1. New SQL (additive migration `sql/27_Create_Account_Identity.sql`)

New schema **`acct`** (keeps it cleanly separate from `cfg`/`quote`/`price`). All tables new;
nothing dropped or altered.

- **`acct.AppUser`** — identity link: `AppUserId` PK, `IdpIssuer`, `IdpSubject` (unique
  together), `Email`, `DisplayName`, `IsActive`, `CreatedAt`. (No passwords — Entra owns auth.)
- **`acct.DistributorAccount`** — `DistributorAccountId` PK, `CompanyName`, `Status`
  (`DRAFT/PENDING_APPROVAL/APPROVED/CHANGES_REQUESTED/REJECTED/SUSPENDED`), `LoyaltyTierCode`
  (nullable FK), `CreatedAt`, audit columns. CHECK on Status.
- **`acct.AccountMembership`** — `AppUserId` × `DistributorAccountId` (+ member role within
  the org), so >1 user per distributor.
- **`acct.AccountApplication`** — submission snapshot + review trail: `ApplicationId` PK,
  `DistributorAccountId`, `SubmittedByAppUserId`, `Status`, `SubmittedAt`, `ReviewedByAppUserId`,
  `ReviewOutcome`, `ReviewReason`, `ReviewedAt`, idempotency key (unique) to make submit retry-safe.
- **`acct.Address`** — `AddressId` PK, `ApplicationId` (or AccountId), `Kind` (`CONTACT`/`SHIP_TO`),
  first/last name, address1/2, city, state, postal, phone, country. "ship-to same as contact"
  persisted as an explicit snapshot (two rows).
- **`acct.LoyaltyTier`** — `LoyaltyTierCode` PK (`standard`,`loyalty15`,`loyalty30`), `Ratebp`
  (basis points: 0, 1500, 3000), `IsActive`. Seeded with the three tiers (D4).
- **`acct.LoyaltyAssignment`** — audited tier assignment history: account, tier, assigned-by,
  effective-at (the *authoritative* discount source; UI never owns the rate).
- **`acct.Notification`** — `NotificationId` PK, recipient scope (AppUser/Account + role),
  `EventType`, `ResourceType/ResourceId`, `Message`, `CreatedAt`, `ReadAt`. (Admin app-submitted
  + applicant approved/changes/rejected events in U1.)
- **`acct.AuditEvent`** — who/what/when for application + approval + loyalty actions
  (or reuse `cfg.AuditLog` if its shape fits — VERIFY at build time; prefer reuse).

Stored procs (additive, `acct.usp_*`): submit application (idempotent), list applications
(admin), review application (approve/reject/changes + assign loyalty), get my account/status,
list/mark notifications. All transactional; duplicate submit → one application/account.

**Brand/site routing seed (for later phases, created now as governed metadata):**
`acct.BrandSiteRouting` (`DEAN→IND`, `FYBROC→TEL`) + `acct.EngineerMembership`
(AppUser × brand/site) — tables created + seeded in U1 so U3 routing is ready, but the
engineering queue itself is U3.

## 2. API (additive; FastAPI, under a new `acct` router; existing routes untouched)

- `GET  /api/v2/me` — current identity + capabilities + account status (drives SPA routing).
- `POST /api/v2/distributor/applications` — submit application (idempotent; validates server-side).
- `GET  /api/v2/distributor/account` — my distributor account + application status.
- `GET  /api/v2/admin/applications` — admin: list/filter applications (admin-only).
- `POST /api/v2/admin/applications/{id}/review` — admin: approve(+loyalty)/reject/changes.
- `GET  /api/v2/notifications` / `POST /api/v2/notifications/{id}/read`.

Authorization: enforced in the endpoints via the existing `auth.py` dependency pattern,
extended with a **`distributor`** role and account-scope checks. **Account A cannot read
B's application/account/notifications** — enforced on the API by ownership, not UI (handoff
REQUIRED). In U1 dev mode the mock user is admin; I'll add a dev-only way to exercise the
distributor path (explicitly dev-only, off in UAT/prod — handoff §4).

Pending applicant: can read own application status; **quote/config endpoints remain denied**
until `APPROVED` (server entitlement, not a UI flag).

## 3. `auth.py` extension (additive)
- Add `ROLE_DISTRIBUTOR` + capability set (`submit_application`, `view_own_account`, and —
  only when account APPROVED — `configure`/`create_quote`). Add account-scope helpers.
- Keep existing roles/permissions unchanged. Dev mock stays admin; add a documented
  dev-only header/param to assume a distributor identity for local testing.
- Real Entra External ID JWT validation is wired in **U5** (the `_validate_entra_token`
  TODO); U1 builds against dev mode so the slice is end-to-end testable now.

## 4. Frontend — new React+TS+Vite SPA (parallel to `/ui`)
- New `spa/` project (Vite + React + TypeScript). Build output served by FastAPI at **`/app`**
  (new static mount in `app.py`, additive — `/ui` legacy mount untouched).
- U1 screens: sign-in bootstrap (dev mock), **distributor onboarding form** (contact +
  ship-to, "same as contact" toggle, client+server validation), **application status** page,
  and an **admin applications queue** (list → review → approve/assign loyalty/reject/changes).
- Shared typed **API client** (generated or hand-written against the new endpoints).
- Capability-driven routing: `/app/distributor`, `/app/admin` shown per `/me` entitlements;
  no client-controlled role switch in UAT/prod (dev-only toggle, clearly labelled).
- Reference visual direction (tokens/accessible controls); no mock engine, no pricing logic.

## 5. What U1 deliberately does NOT do
Quote configuring/creating UI (U2), loyalty math on quotes (U2), engineering review/queue
(U3), acceptance/PDF (U4), real Entra validation + full hardening/cutover (U5). The
configurator stays on the old `/ui` until later phases port it into the SPA.

## 6. U1 exit evidence (FULL milestone ceremony)
- Migration `sql/27_*` applied additively; **no existing table altered/dropped**; Fybroc
  watermarks + `audit_selections_vs_db` CLEAN; Fybroc gate 9/9.
- New `acct.*` tables + procs created; seed tiers (standard/loyalty15/loyalty30) + routing
  (DEAN→IND, FYBROC→TEL) present.
- Acceptance (subset of handoff §18): (1) applicant submits both address sets; duplicate
  submit → one application; admin sees it; pending user denied config/quote via **API** and
  UI. (2) admin approves with loyalty15 → applicant notified + access unlocked after
  refresh. (3) account A cannot read B's application/notification by guessed id (API test).
- Old `/ui` still serves; existing v2 endpoints unchanged (regression).
- Evidence doc `docs/evidence/CPQ_U1/…`, roadmap/register bump, commit + push all 4 refs.

## 7. Confirmations before I build U1
1. **New `acct` schema + `spa/` project** (vs. folding into existing schemas/`ui/`) — OK?
2. **SPA served at `/app`** by FastAPI static mount, `/ui` kept until cutover — OK?
3. **U1 against dev-mock auth**, real Entra wired in U5 — OK? (Lets us build/test the whole
   onboarding→approval slice now without blocking on Entra tenant config.)
4. Anything to add/trim from the U1 table/endpoint set above before I scaffold.

# CPQ SPA — U1 Exit Evidence

**Milestone:** CPQ SPA U1 — SPA shell + identity/capability routing + distributor
onboarding + admin approval slice (dev-mock auth).
**Branch:** `feature/cpq-spa`
**Mode:** FULL (milestone-exit ceremony).
**Design:** `docs/CPQ_SPA_U1_DESIGN.md`. Decisions D1–D7 locked (see design header).

---

## 1. Deliverables inventory

**SQL (additive):**
- `sql/27_Create_Account_Identity.sql` — new `acct` schema. Tables: `LoyaltyTier`,
  `AppUser`, `DistributorAccount`, `AccountMembership`, `AccountApplication`,
  `Address`, `LoyaltyAssignment`, `Notification`, `BrandSiteRouting`,
  `EngineerMembership`. Procs: `usp_UpsertAppUser`, `usp_GetMyAccount`,
  `usp_SubmitApplication` (idempotent), `usp_ListApplications`, `usp_GetApplication`,
  `usp_ReviewApplication`, `usp_ListNotifications`, `usp_MarkNotificationRead`.
  Seeds: loyalty tiers `standard`/`loyalty15`/`loyalty30` (0/1500/3000 bp) and
  brand routing `DEAN→IND`, `FYBROC→TEL`. Audit reuses `cfg.AuditLog` (no new audit
  table). Fully idempotent (`IF NOT EXISTS` / `CREATE OR ALTER`) — safe to re-run.

**API (additive):**
- `src/api/auth.py` — added `ROLE_DISTRIBUTOR` (+ base caps
  `submit_application`, `view_own_account`); `configure`/`create_quote` are NOT in
  the role map — they are server-gated on APPROVED account status. Added dev-only
  identity assumption (`X-Dev-Assume-Role` header, honored only in dev mode),
  `idp_identity()` helper, and `require_admin`/`require_distributor` deps. Existing
  roles unchanged.
- `src/api/acct_routes.py` — new `router_acct` (prefix `/api/v2`): `GET /me`,
  `POST /distributor/applications`, `GET /distributor/account`,
  `GET /admin/applications`, `GET /admin/applications/{id}`,
  `POST /admin/applications/{id}/review`, `GET /notifications`,
  `POST /notifications/{id}/read`. Authorization + account-ownership enforced in
  the endpoints (not just UI).
- `src/api/app.py` — included `router_acct`; added conditional static mount of the
  SPA at `/app` (serves `spa/dist` when present). Legacy `/ui` mount untouched.

**Frontend (new):**
- `spa/` — Vite + React + TypeScript project (base `/app/`). Screens: home/bootstrap,
  distributor onboarding (contact + ship-to with "same as contact", client+server
  validation, idempotency key), application status, admin applications queue +
  review (approve/assign loyalty/request-changes/reject), notifications. Capability-
  driven routing from `/me`. Dev-only role switcher (labelled DEV).

**Audit:**
- `scripts/audit_cpq_u1.py` — re-runnable, SELF-CLEANING U1 acceptance audit.

---

## 2. Exit-gate criteria → result (PASS/FAIL)

| # | Criterion (U1 design §6 / handoff §18 subset) | Result |
|---|-----------------------------------------------|--------|
| 1 | Migration 27 applied additively; no existing table altered/dropped | PASS |
| 2 | `acct.*` tables + procs created; tiers + routing seeded | PASS |
| 3 | `/me` returns identity + capabilities (admin & distributor) | PASS |
| 4 | Pending distributor DENIED configure/create_quote via API | PASS |
| 5 | Submit application (both addresses); duplicate submit → one application | PASS |
| 6 | Admin lists application + sees both address snapshots | PASS |
| 7 | Admin approves w/ loyalty15 → APPROVED, applicant notified, access unlocked | PASS |
| 8 | Account A cannot read B's notification by id (API ownership) | PASS |
| 9 | Second review of approved application rejected (409) | PASS |
| 10 | Fybroc regression gate `run_all_fybroc_audits.py` 9/9 "ALL CORRECTIONS INTACT" | PASS |
| 11 | Isolation: Fybroc/non-Dean watermarks unchanged | PASS |
| 12 | SPA build passes (tsc strict + vite build); served at `/app`; `/ui` intact | PASS |

---

## 3. How it was verified (commands + numbers)

**U1 acceptance audit** (server running on :8080, dev mode):
```
.\.venv\Scripts\python.exe scripts\audit_cpq_u1.py
→ CPQ U1 AUDIT: 22/22 checks passed   (incl. "self-clean: no residue - residue=0")
```
Run twice back-to-back — 22/22 both times, residue=0 (re-runnable, self-cleaning;
each run uses a unique run tag and deletes all rows it created).

**Fybroc cross-family regression gate:**
```
.\.venv\Scripts\python.exe scripts\run_all_fybroc_audits.py
→ RESULT: ALL CORRECTIONS INTACT   (9/9 PASS, exit 0)
  audit_selections_vs_db, audit_feasible_constraints, audit_motor_constraints,
  audit_identifier_parity, audit_bom_engine, audit_quote_engine, audit_free_config,
  audit_fybroc_pricing, audit_fybroc_motor_cpq
```

**Isolation watermarks (pre-migration baseline → post-U1, identical):**
```
cfg.FeasibleConstraint (total)            : 4743  → 4743
non-Dean cfg.SeriesFieldOption            : 3638  → 3638
non-DEAN stg.SegmentCombinationImport     : 300608 → 300608
non-DEAN cfg.ConfiguredProduct            : 1196  → 1196
```
U1 writes only to the new `acct` schema; no cfg/price/quote/stg config row changed.

**SPA build:**
```
cd spa; npm install; npm run build
→ tsc -b (strict, noUnusedLocals/Parameters) clean; vite build → spa/dist
  (43 modules; dist/index.html references /app/assets/*)
```

**Serving (live):**
```
/app/                      → 200 (SPA; index.html references /app/assets/*)
/api/v2/me                 → 200
/ui/configurator.html      → 200 (legacy UI intact)
```

---

## 4. Known gaps / not-verified (disclosed)

- **Real Entra validation is NOT wired** (deferred to U5). U1 runs against dev-mock
  auth. `_validate_entra_token` still raises 501 in production mode. The dev-only
  `X-Dev-Assume-Role` header is honored ONLY when `APP_ENVIRONMENT=development`.
- **`/ui/` root returns 404** — this is pre-existing (there is no `ui/index.html`;
  the legacy entry point is `ui/configurator.html`, which serves 200). NOT a
  regression introduced by the `/app` mount.
- **`spa/dist` is a build artifact.** `spa/dist` and `spa/node_modules` are
  gitignored; the `/app` mount is conditional, so a fresh checkout must run
  `npm install && npm run build` in `spa/` before `/app` serves. API startup is
  unaffected when the build is absent.
- **Out of U1 scope (later phases):** quote configuring/creating UI (U2), loyalty
  math on quotes (U2), engineering review queue (U3), acceptance/PDF (U4), real
  Entra + hardening/cutover (U5). The configurator stays on legacy `/ui` until
  ported.
- **`BrandSiteRouting` + `EngineerMembership`** are seeded/created now as governed
  metadata for U3 but are not yet exercised by any routing logic in U1.
- The dev-mock admin `acct.AppUser` row (`dev-mock` / `dev-user-001`) is created on
  first `/me`; this is expected identity resolution, not test residue.

---

## 5. Reproducibility

```powershell
# 1. Apply migration (idempotent/additive)
#    (applied via sqlcmd or the batch-splitting helper; file: sql/27_Create_Account_Identity.sql)

# 2. Build SPA
cd spa; npm install; npm run build; cd ..

# 3. Start API (dev mode)
$env:PYTHONPATH="."; $env:CONFIGURATION_TOKEN_SECRET="local-dev-configuration-token-secret-0123456789"
.\.venv\Scripts\python.exe -m uvicorn src.api.app:app --host 127.0.0.1 --port 8080

# 4. U1 acceptance audit (separate terminal)
.\.venv\Scripts\python.exe scripts\audit_cpq_u1.py

# 5. Fybroc regression gate (stop the server first so :8080 is free)
.\.venv\Scripts\python.exe scripts\run_all_fybroc_audits.py
```

---

## 6. Exit decision

**PASS on all 12 criteria.** U1 is additive, Fybroc is intact (9/9), isolation
watermarks unchanged, and the onboarding→approval slice works end-to-end against
dev-mock auth with API-enforced authorization and ownership. Next permitted
milestone: **U2** (quote configuring/creating UI + loyalty math) — await explicit
user go-ahead before starting.

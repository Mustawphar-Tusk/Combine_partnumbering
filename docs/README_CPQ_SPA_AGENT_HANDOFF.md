# Pump CPQ SPA — implementation-agent handoff

Version: 1.1 · Updated 28 October 2026
Change: required brand/site routing — DEAN → IND; FYBROC → TEL.
Owner: Mustapha · Product families: Dean and Fybroc
Purpose: extend the real CPQ platform through development, UAT and production.

## 1. Read this before starting U1

This document translates the owner's requested SPA/account/quote workflow into implementation requirements and recommended decisions. It is a handoff for the agent working in the CURRENT repository, not a claim that the older uploaded snapshot is the current implementation.

The owner is using another AI agent to develop this project and wants the following capabilities introduced **where they do not already exist**. Inspect the latest code, SQL schema, logs and roadmap before changing anything. Reuse established services, identities, tables and metadata wherever they meet the requirement. Report a real gap with evidence before replacing a component or inventing a second implementation.

Status of guidance:

- **REQUIRED:** explicitly requested behavior or existing project architecture constraints.
- **RECOMMENDED:** the author's proposed solution; do not report it as an owner-approved decision.
- **VERIFY:** current repository/database evidence is needed.
- **DECISION:** an unresolved business policy that affects behavior; expose it clearly and do not silently invent commercial rules.

This handoff authorizes no cloud deployment, production data change or destructive migration. It specifies the requested features and suggests how to implement them. The receiving agent should present its verified baseline and concise implementation plan before beginning the feature work.

### Current evidence and limits

The previous review used `Combine_partnumbering - Claude (2).zip` with SHA-256 `9e0990a799bfd458a3703044bf2ae865a86bf019edeb4d353585f8c042fe8df2`. That snapshot contained FastAPI, SQL-backed configuration/numbering/pricing/BOM/quotes, `ui/configurator.html`, `src/api/v2_routes.py`, and SQL quote procedures. It is a baseline to compare, not authority over newer code.

Its quote statuses were `Draft`, `Submitted`, `Approved`, `Expired`, `Cancelled`. Quote-line pricing states included `found`, `partial`, `call_for_price`, `not_found`. The current agent's reference SPA, its §7, and its U1–U5 plan were not provided to this author. Inspect those materials locally; do not pretend their detailed layouts or milestones were reviewed here.

The earlier roadmap recorded D155 Dean codependency certification and outstanding D150 exhaustive Dean regression. Verify current status. A SPA rewrite does not certify unresolved engineering rules or close missing pricing/numbering data.

## 2. Recommended answers to the five questions

These recommendations incorporate the owner's newly expanded requirements and supersede assumptions that this is a UI-only refresh.

| Question | Recommended answer | Implementation consequence |
|---|---|---|
| File strategy: new `app.html` or replace `configurator.html`? | Build the new SPA alongside the current UI; cut over only at the verified U5/release gate. | Keep the existing URL usable during development and parity testing. `app.html` may be the trial entry URL, but do not force the entire app into one file. Use the current frontend toolchain if adequate. |
| Accounts and discounts: seeded UI JSON, list-only, or defer accounts table? | None meets the full requirement. Implement persistent distributor accounts and a server-owned loyalty policy now. | No production-like fake accounts in UI JSON. A temporary list-only shell is acceptable while building, clearly labelled incomplete; account/discount workflows must work before feature acceptance. Reuse or extend the actual account schema after inspection. |
| Quote status mapping without DB changes? | Use truthful, persisted workflow states. Extend schema/services if the current model cannot represent them. | Do not label a backend Draft or Approved as a materially different workflow status. Existing commercial quote status and new engineering-review status may be separate dimensions. Maintain one authoritative transition model. |
| Theme: reference versus sky blue? | Adopt the reference's layout and visual direction as the default recommendation, using reusable design tokens and accessible controls. | Inspect the actual reference first; preserve brand elements where appropriate. Do not let a theme rewrite change engineering behavior. Final visual approval remains with the owner. |
| Distributor/Applications toggle? | Yes to distinct Distributor, Applications Engineering and Admin workspaces. No to a client-controlled role switch. | Navigate only between workspaces the authenticated user is entitled to use. A local demonstration toggle must be explicitly development-only and unavailable in UAT/production. |

Frontend recommendation: React + TypeScript + Vite fits the established target architecture and the growing account/queue/revision workflows. If the latest repository already has a suitable SPA foundation, extend it. HTML/CSS/JavaScript remain the browser output; Bootstrap is optional styling, not a mandatory second framework. Do not add Bootstrap on top of an established component system without a reason.

A vanilla JavaScript SPA can provide the behavior but increases the amount of routing/state/form infrastructure to maintain as this workflow grows. An in-place rewrite has a smaller temporary footprint but makes parity and rollback harder. The parallel React/TypeScript approach is recommended, not yet an owner-selected tooling mandate.

## 3. Non-negotiable architecture

1. Rules remain metadata-driven. Do not duplicate Dean/Fybroc engineering, numbering or pricing rules in React components.
2. FastAPI remains the shared application/API boundary for the SPA, Excel, D365 and other consuming tools. A browser is one client of the platform.
3. SQL and existing canonical services own approved metadata, persisted configurations, deterministic PN/SKU, BOM and prices. Preserve current authoritative responsibilities after verifying them.
4. Identical valid canonical configurations must reuse established identities according to the existing signature/publication rules. Discounts, contact details and quote lead time must not alter product identity.
5. Keep source workbooks read-only. Preserve source lineage, golden cases and publication versioning.
6. Use additive, reviewed, versioned migrations. The older `sql/01_Create_Database.sql` dropped a database and `sql/24_Create_Quote_Engine.sql` dropped quote tables; these are not upgrade procedures for populated UAT.
7. All business authorization, pricing and workflow transitions are enforced by the API, including direct calls that bypass the UI.
8. Preserve stable API behavior for existing clients. Version or add endpoints for breaking changes, rather than making the SPA the only usable client.
9. Keep DEV/UAT/PROD targeting explicit. Use separate identities, secrets and database targets.
10. Register this work as an approved roadmap extension and reconcile dependencies with the current milestone. Do not silently declare existing engineering milestones complete.

## 4. Three workspaces, one shared platform

“Domain” means a role-specific functional workspace unless the owner explicitly requests separate DNS domains. Recommended routes: `/app/distributor`, `/app/applications`, `/app/admin`. A single deployment can serve all three; separate websites/databases are not required solely because there are three roles.

| Capability | Distributor | Applications engineer | Admin |
|---|---|---|---|
| Submit/update own onboarding information | Yes | Not normally | Review/manage |
| Approve or reject distributor application | No | No by default | Yes |
| Assign/change loyalty | No | No by default | Yes, audited |
| Configure and create quotes | Own approved account only | Authorized engineering scope | Only with explicit configure permission |
| Request customization/review | Own quote | Authorized quote | If separately permitted |
| Resolve C/F, enter custom specs and prices | No | Yes, authorized review | Only if separately given engineering/pricing permission |
| Accept final reviewed revision | Own approved account | No on distributor's behalf by default | No impersonation by default |
| Download completed quote PDF | Own account | Authorized completed work | Authorized oversight |
| Feature controls and account suspension | No | No | Yes, audited |

Admin account oversight does not automatically grant engineering certification authority. Resolve role inheritance explicitly; use least privilege. Applications engineers require the family/site scope defined below, in addition to any assigned-case scope. Organization membership is distinct from global role.

**REQUIRED:** distributor/customer data isolation. Account A cannot access account B's application, contact data, quote, messages or PDF by guessing an identifier. Global reusable product identities may remain shared if existing policy allows, but private custom descriptions, prices and customer context require separate visibility rules.

### Required brand/site routing and engineering queue isolation

The owner has confirmed the engineering responsibility mapping:

| Pump brand / family | Engineering location | Site code | Responsible review queue |
|---|---|---|---|
| Dean / `DEAN` | Indianapolis | `IND` | Dean applications engineering — Indianapolis |
| Fybroc / `FYBROC` | Telford | `TEL` | Fybroc applications engineering — Telford |

**REQUIRED:** a Dean distributor quote needing engineering review must enter the IND/DEAN queue. A Fybroc quote must enter the TEL/FYBROC queue. The distributor's address, ship-to location, browser workspace, and geographic location do not determine the engineering team. The ordered brand does.

Implement the mapping as governed routing metadata in the shared backend/SQL model, reusing existing family/site entities. Assign engineers explicit authorized brand/site memberships. A global applications-engineer role alone must not expose both teams' work. For normal users, IND engineers see/claim/edit Dean cases only; TEL engineers see/claim/edit Fybroc cases only. Missing or conflicting routing metadata must produce a visible routing exception for authorized admin resolution, never fall back to the other team's queue.

Apply the same scope to queue lists/counts/search, direct case/quote reads, assignment/claim, custom-code resolution, pricing/lead-time edits, review submission, notifications/deep links, completed queues and PDF downloads. Enforce it on the API and database-access path, not merely a frontend filter. An IND-only engineer must not access a Fybroc case by changing a URL, request family/site parameter or quote ID, and vice versa. The server resolves family from the persisted quote/line and derives the authorized engineering site; it must reject spoofed or inconsistent routing values.

Persist brand, responsible engineering site, submitted revision, assignee and routing/history evidence on each review case. Existing quote `SiteCode` may represent a commercial/originating site; verify its semantics before reusing it for engineering routing. Distributor ownership remains separate from engineering site. On completion, return the case and notification to its responsible brand/site team's Completed queue. Returned offers and approval notifications continue to go to the owning distributor account, regardless of location.

Admin may oversee both queues with explicit oversight permission; oversight does not grant engineering edit/approval authority. Cross-team access or reassignment is **not** enabled by default. Any future cross-trained coverage requires explicit approved brand/site entitlements and an audited policy; do not infer it from an admin flag or workspace switch. Reassignment within a team retains routing and revision history. Validate memberships when the action occurs, not only when a case was initially claimed.

**RECOMMENDED initial mixed-brand policy:** keep each quote single-brand and offer separate linked quotes when a distributor needs both Dean and Fybroc. Verify current multi-line behavior before implementing this restriction. If mixed-brand quotes must be supported, obtain an explicit policy and create brand/site-scoped review cases per line group, exposing only each team's authorized data. Final distributor acceptance must wait for every required team review; never route the entire mixed quote to whichever brand appears first. A brand change before submission recomputes routing; after submission it requires a controlled new revision/review route and invalidates obsolete offers/assignments/notifications as appropriate, without rewriting history. Scope this work before enabling mixed-brand finalization.

## 5. Distributor identity and onboarding

### Identity versus business account

Use the established Entra/External ID sign-in design after verifying its actual state. Recommended: the user signs in through the identity provider, then completes a CPQ distributor application. The CPQ database stores the business profile and identity linkage, not raw passwords. Do not implement a parallel password system merely because the user said “create a user account.”

A pending signed-in applicant must be able to access their own application status even though quotation access is denied. Account approval is a server-side entitlement distinct from successful login and identity-provider group assignment.

Recommended persistent separation: authenticated user, distributor business account, user-account membership, addresses, application/review history, loyalty assignment. This supports more than one user per distributor without making one person's name the company identity. Verify whether these entities already exist.

### Required application fields

Collect both sets below. Labels must distinguish contact from ship-to recipient.

| Contact information | Ship-to information |
|---|---|
| First name | First name |
| Last name | Last name |
| Address | Address |
| City | City |
| State | State |
| Postal code | Postal code |
| Phone number | Phone number |

Recommended additions: distributor/company name, country, verified email from identity provider, optional address line 2 and optional contact email override subject to verification. Country is useful for address/phone validation and later D365 mapping. These are proposed additions, not owner-stated mandatory fields. Support “ship-to same as contact”; persist the resulting snapshot explicitly. Validate address/phone/postal formats without assuming all users have US addresses.

### Account application workflow

Recommended states:

`DRAFT → PENDING_APPROVAL → APPROVED`

Alternative review outcomes: `PENDING_APPROVAL → CHANGES_REQUESTED → PENDING_APPROVAL`, or `PENDING_APPROVAL → REJECTED`. An approved account may later become `SUSPENDED` under an explicit audited admin action. Reapplication and reinstatement rules must be documented.

On Submit:

- Validate required fields on client and server.
- Persist the application, profile, addresses, authenticated applicant identity and submitted timestamp.
- Create the admin queue item and in-app notification durably; duplicate submissions must not create duplicate accounts/queue entries.
- Show: **“Your application has been submitted. The quotation tool will be available once an administrator approves your account.”**

On admin review:

- Open submitted contact/ship-to information and review history.
- Request corrections, reject with a reason, or approve.
- Assign the applicable loyalty policy as part of approval; approval without a tier requires the explicitly approved no-discount policy.
- Persist reviewer identity, outcome, reason, timestamps and loyalty effective policy.
- On approval, notify the applicant: **“Your distributor account has been approved. You can now access the quotation tool.”**
- Refresh server-derived permissions so an already open SPA gains approved access without relying on a locally edited flag. Suspension must revoke access consistently, including open sessions.

## 6. Admin controls and feature settings

Provide an admin account directory and application queue with filtering, status, date, account, assigned reviewer and outcome history. Admin can inspect user memberships, application history, loyalty and quotes within approved scope.

Feature settings must use a typed allowlist of known capabilities, for example quote creation, custom requests, PDF download or SKU lookup. Support user/account restrictions where appropriate, an audit reason and effective dates if useful. UI availability comes from a server capability response, while endpoints enforce the same decision. Define precedence; recommendation: global disable and explicit account/user deny override broader grants.

“Developer settings” must not become arbitrary SQL execution, code injection, browser-set roles, authentication disablement or permission bypass. Admin cannot enable a feature that bypasses required approval, engineering validity or distributor isolation. Changes should be attributable, reversible and testable. Protect against removing the last legitimate administrator.

## 7. Loyalty and quote calculation

**REQUIRED tiers:** `loyalty15` = 15% discount; `loyalty30` = 30% discount. Admin assigns the tier; distributors cannot submit their own authoritative discount rate.

Store tiers/rates and assignments in governed SQL metadata with account linkage and audit/effective information. UI JSON may contain labels for rendering but is not the discount authority.

Recommended calculation, pending business confirmation:

- Resolve all approved standard/custom selling prices on the server.
- Gross merchandise subtotal = sum of quantity × approved unit selling price.
- Loyalty discount = currency-rounded eligible subtotal × assigned rate.
- Net merchandise subtotal = gross subtotal minus loyalty discount.
- Add separately defined freight/tax/other charges according to an approved policy. Do not invent tax/freight calculations.

The owner said “discount on total sales.” Confirm whether that includes custom engineering charges, freight and tax before enabling commercial finalization. Until confirmed, show the proposed merchandise-subtotal policy as a proposal and keep finalization gated if the amount is ambiguous. Use decimal money types and documented currency rounding; never floating-point arithmetic as financial authority.

Snapshot account ID, tier, rate, eligible basis, source price versions, gross, discount and net at each reviewed quote revision. Recommended policy for owner confirmation: recalculate drafts and engineering work-in-progress under the documented current policy, then freeze the loyalty rate and commercial terms when engineering submits the offered revision to the distributor, through that offer's acceptance validity. An earlier distributor submission for engineering review does not itself freeze commercial terms. A permitted standard-only offer needs the equivalent server-side offer/freeze step. A later loyalty change must not silently rewrite a completed quote. Tier changes on an open review require an explicit repricing/review policy.

An unresolved C/F amount is unknown, not a genuine zero. If an existing API returns zero for missing price, preserve compatibility while exposing explicit completeness state. Do not discount an unknown total into an apparently valid final price.

Example acceptance checks: eligible subtotal 10,000.00 produces 1,500.00 discount/8,500.00 net for loyalty15; 3,000.00/7,000.00 for loyalty30. Prices are test figures, not project catalog assertions.

## 8. Quote creation and customization requests

### Standard configuration

Reuse configuration dictionary, resolve-state, validation, canonical product resolution, pricing and BOM services. Preserve selections when navigating within the SPA. Cancel or ignore stale requests so an older API response cannot overwrite the user's latest edit. Render product groupings from authoritative metadata; do not duplicate Dean groups or fabricate Fybroc groupings in multiple components.

### Custom button per product grouping

Every applicable rendered product section needs a **Custom** action. It opens an accessible modal collecting at minimum the grouping, affected field(s), requested value/specification and explanatory notes. Prepopulate current standard values/context. Recommended additions: units, quantity impact and supporting text; attachments are optional future scope unless already supported.

Persist custom requests against a quote line, group and revision. A free-text request is a request for engineering review, not an automatically accepted new configuration option. Preserve the original standard selections beside requested custom changes. Use stable metadata group identifiers, not display-label matching.

**REQUIRED:** any unresolved C/F means the distributor quote is incomplete and must offer **Send to Applications for Review**. Treat unresolved configuration/specification, custom code, pricing, BOM or required engineering decisions as explicit reasons for incompleteness. Do not mark complete simply because every dropdown contains a string.

On send: save the submitted revision/snapshot, derive the responsible team from the persisted brand (DEAN → IND; FYBROC → TEL), create durable review queue work and notify only the authorized brand/site engineering group. Make submission retry-safe. Distributor editing of that submitted revision must stop; changes require a new revision or an explicit return-to-draft transition.

## 9. Applications engineering review

The engineer sees only their authorized brand/site queue (DEAN/IND or FYBROC/TEL), with unassigned/assigned cases, account, family/series, responsible engineering site, submitted revision, unresolved items, age and state. Provide claim/assign and visible ownership to reduce simultaneous work; use optimistic concurrency or equivalent even when a case is assigned.

The engineer can edit all business configuration/specification fields needed to satisfy the request, resolve custom descriptions, enter authorized custom selling prices, and provide quote lead time. “All quote fields editable” does not permit editing immutable IDs, audit identities, customer ownership, publication history or calculated PN/SKU by hand. Correcting contact/ship-to snapshots can be an explicit permitted action with history; changing the owning distributor requires a separate privileged operation.

For each engineering change:

1. Record original and revised values with a reason and reviewer identity.
2. Re-evaluate dependent options and engineering constraints through the shared services.
3. Resolve the appropriate existing custom SQL code/hex mapping.
4. Rebuild the canonical configuration and authoritative grouped specifications, then recompute PN/SKU/signature and BOM as required.
5. Recalculate authorized prices and loyalty totals on the server.
6. Return the complete revised state to the SPA and retain revision lineage.

Pricing overrides must be clearly quote-specific unless approved for publication. An engineer resolving one quote must not overwrite the master catalog's price or standard metadata for every user. Record currency, basis/units, source, reason and whether the input is list or net selling price. Default recommendation: enter gross/list custom selling price, then apply loyalty once. Do not double-discount a manually entered net price.

Lead time needs a structured value: duration/range, unit, basis such as “after order approval,” and notes if applicable. Define whether it applies to the entire quote or individual lines; do not leave a bare number whose unit/basis is unknown. Permit an explicit engineering-approved N/A only where the business permits it.

Before **Submit Review**, require all custom requests resolved or explicitly declined with reasons, all mandatory specifications valid, authoritative custom identity resolved, required BOM consistency, complete/approved price inputs, lead time and an unchanged revision/concurrency token. Rejected custom requests must leave an acceptable proposed configuration; no silent omission.

## 10. Custom codes and deterministic product identity

The owner states there is a SQL custom-code table linked to pump configuration groupings. **VERIFY the exact schema/table, columns, rules, authoritative workbook/specification and existing compiler/runtime service before implementing.** This table was not confirmed in the older reviewed SQL files; do not invent its name, assume it is absent in the latest code, or create a duplicate.

Produce a mapping report showing family, group/segment, supported field, standard/custom indicator, code format/width, code allocation rule and publication lineage. If the table/spec is missing or ambiguous, record the gap and gate final custom identity until engineering supplies the rule.

Never concatenate arbitrary free text into PN, assign random hex, reuse a reserved custom code incorrectly, or allow a browser/engineer to type the final PN/SKU as an override. New engineering values must use the governed mapping/allocation process and collision rules. Code allocation must be atomic under concurrent requests and auditable where it is supported.

**Critical identity case:** a generic custom marker may be reused for different designs. Prove how distinct approved custom specifications become distinct deterministic identities under the existing PN/SKU uniqueness rules. If two different custom designs would produce the same PN, stop finalization and resolve the numbering specification; do not weaken unique constraints or silently reuse the wrong product. Equivalent normalized custom designs should reuse identities where policy permits.

Preserve standard engines. Custom specifications must become canonical structured data through approved extension metadata, not a parallel family engine inside the SPA. Distinguish engineering design identity from quote-specific price, lead time and customer discount. Recompute impacted BOM/specification outputs through existing services and retain the original quote revision.

## 11. Review return, distributor acceptance and completion

When engineering submits a complete review:

- Persist an immutable offered revision with resolved specifications, PN/SKU/BOM, price/discount breakdown and lead time.
- Return work to the distributor's application/review queue and create an in-app notification.
- Show a comparison of requested versus offered changes and the current revision number.
- Offer **Complete / Accept Quote** and **Request Changes**. Request Changes is a recommended companion action so the distributor is not forced to accept; capture the reason and return a new review revision to engineering.

Acceptance must name the exact reviewed revision and occur on the server under the owning approved distributor identity. Recheck capability, account status, expiry and version. A stale browser cannot accept an earlier or modified offer. Capture acceptance identity/time and freeze the accepted document snapshot. Completion is quote acceptance, not automatic sales-order placement or D365 production creation.

After acceptance, the quote appears in Applications Engineering's **Completed** queue, with notification and access to the same final document. Both distributor and engineer can retrieve the accepted quote record/PDF within their authorized scope.

Recommended standard-only path: a fully validated, fully priced quote with no custom/C/F items can be completed without engineering review if required lead time can be supplied from approved metadata and business policy permits it. Otherwise route to engineering. This policy is not settled by the owner's custom-flow description and must be confirmed before activating that shortcut.

## 12. Status model and queue behavior

Use explicit persisted workflow state; queue visibility is a projection of that state and authorization. Do not maintain disconnected queue copies that can disagree with the quote. Preserve existing commercial quote status if used by other API clients, and add a dedicated review lifecycle if necessary.

Proposed review lifecycle (names are recommendations):

| From | Action / actor | To | Required condition |
|---|---|---|---|
| Draft | Send for review / distributor | SubmittedForEngineering | Saved owned revision and valid review request. |
| SubmittedForEngineering | Claim / engineer | EngineeringInProgress | Authorized role/scope; claim is concurrency-safe. |
| EngineeringInProgress | Ask distributor for details / engineer | AwaitingDistributorInformation | Question recorded; customer notified. |
| AwaitingDistributorInformation | Reply/resubmit / distributor | SubmittedForEngineering | New information retained with revision history. |
| EngineeringInProgress | Submit review / engineer | AwaitingDistributorAcceptance | No unresolved completion blockers; lead time recorded. |
| AwaitingDistributorAcceptance | Request changes / distributor | SubmittedForEngineering | Reason and new review revision retained. |
| AwaitingDistributorAcceptance | Complete / distributor | Completed | Exact offered revision accepted and frozen. |
| Eligible open state | Cancel / authorized user | Cancelled | Explicit permission/policy and reason. |

Offer expiry and reopening need a defined policy. Completed records are immutable; reuse creates a linked new draft/revision and reevaluates current availability/pricing, never overwrites the original. Internal event names and display labels may differ if their meaning stays consistent and documented.

Use SQL transactions for related state/history/queue changes and a durable outbox/event mechanism or equivalent for notification/document jobs. Repeated submit/accept requests must not create duplicate approvals, completions or notifications. Use idempotency keys plus server uniqueness/transaction controls and optimistic version tokens for updates.

## 13. In-app notifications

Provide notifications for application submission (admin), approval/change request/rejection (distributor), review submission (engineer), engineering information requests and review return (distributor), and final completion (engineer).

Persist recipient scope, event/resource/revision, message, created time and read state. Deep links must still enforce API authorization. Polling is acceptable initially; WebSockets are not required for correctness. Queue state must survive refresh/restart regardless of notification delivery. No email/SMS is requested in this feature; treat these as separate scope.

## 14. PDF generation and durable documents

On distributor Complete, initiate server-side PDF creation for the accepted revision. Use an existing PDF service if available; otherwise add a controlled renderer. A browser print dialog alone does not satisfy tracked, reproducible quote PDF generation.

PDF content should include quote number/revision, date/validity, distributor/contact/ship-to snapshot, family/model/configuration and approved custom specifications, PN/SKU, quantities, approved price presentation, loyalty discount/net totals, currency, lead time, terms and any approved limitations. Use the authoritative customer quote format for the family as the content baseline; inspect Dean Formal Quote and Fybroc FORMAL QUOTES requirements. The agent must not assume it has seen a reference template that is not present.

Recommended persistence: SQL document metadata plus durable private object storage for the bytes. A suitable existing SQL document strategy is also possible. Record quote/revision, storage identity, content hash, renderer/template version, created time, generating actor/job and document status. Do not use container-local filesystem as the durable quote archive.

Separate accepted quote state from document job state: `Pending`, `Ready`, `Failed`. If rendering fails after acceptance, display **“Quote completed; PDF generation pending/failed”**, allow an authorized retry and alert support. Do not silently mark the quote fully delivered or create a second acceptance on retry. Generate from the immutable accepted snapshot, not today's account address/loyalty or current catalog data.

Both parties download the same stored document subject to access checks. Short-lived signed links, if used, are issued only after authorization. Completed quote PDFs must remain reproducible or retrievable after metadata updates; retain old document hashes/templates or archived bytes accordingly.

## 15. Suggested data model — reuse before adding

The following are conceptual entities, NOT prescribed SQL table names:

| Entity | Minimum purpose |
|---|---|
| User / identity link | Issuer/tenant + subject/object ID, display/contact profile and active state. |
| Distributor account / membership | Organization identity, users, approved/suspended access and ownership scope. |
| Account application / history / addresses | Contact/ship-to submission snapshots and admin review trail. |
| Loyalty tier / assignment | Rates, effective rules, assigning admin and audit history. |
| Feature policy | Allowlisted global/account/user capability restrictions and change history. |
| Quote header / line | Existing quote identity and items, account ownership, monetary terms. |
| Quote revision / review case | Immutable submission/offer/acceptance lineage, brand, responsible engineering site, assignee, routing history, version and state. |
| Brand/site routing / engineer membership | Governed DEAN→IND and FYBROC→TEL routing with explicit authorized engineer memberships. |
| Custom request / resolution | Group/field request, normalized approved specification, code mapping and price provenance. |
| Quote commercial snapshot | Account/address, pricing/loyalty/lead-time and publication versions accepted. |
| Audit / notification / outbox | Who changed what, durable delivery intent and user read state. |
| Quote document | Accepted revision's PDF location/hash/version/status. |

Use appropriate keys, foreign keys, uniqueness, check constraints, decimal precision and indexes after inspecting the live schema. Protect PII in logs, retention and role access. Do not store whole identities or secrets in client-side persistence. Treat untrusted free text safely in HTML/PDF output.

## 16. API contracts to design

Inventory existing endpoints first. Extend shared application services and publish typed OpenAPI contracts for capabilities currently missing. Candidate API areas:

- Current identity/capabilities; own distributor application and status.
- Admin application list/review, account management, loyalty and feature policy.
- Owned quote creation/read/revision, custom requests and submission.
- Engineering review queue, claim/assignment, edit/validate/price/submit, all scoped to persisted brand/site and current engineer entitlements.
- Distributor reviewed revision, request changes and acceptance.
- Notifications/list/read, final document status/download/retry.

Endpoint names are for the receiving agent to propose consistently with the current API. Do not create browser-only SQL bypasses. Validate authority, account scope, transition and revision on every operation. Errors should identify actionable business problems without leaking another customer's data. Define 401/403, validation, conflict/stale revision and pricing-unavailable behavior.

API consumers include the SPA, future D365 integration and other tools. Support separate delegated user and app-only access where required; application permissions must not automatically grant distributor impersonation or engineering approval. Do not put client secrets in the SPA. Preserve request correlation and actor/client identity in audit records. Changes to workflow must not break existing configuration endpoints without a migration/version plan.

## 17. Proposed U1–U5 delivery sequence

Reconcile this with the other agent's actual U1–U5 document. The following is a proposed mapping, not a quotation of its existing plan. Deliver small end-to-end slices; do not build every screen using fake data and postpone the backend indefinitely.

| Phase | Deliverable | Exit evidence |
|---|---|---|
| Pre-U1 | Baseline and gap report; verified schema/custom-code/reference inventory; revised plan and decision log. | Existing work mapped to requirements; migration/API/identity risks explicit; owner can review approach. |
| U1 | Parallel SPA shell, shared typed API client, real identity/capability routing, account/application persistence and admin approval slice. | Applicant submits; admin sees it; approval unlocks authorized quote access after refresh/restart; old UI still works. |
| U2 | Distributor account history, loyalty calculation and quote drafts/custom requests; first durable brand/site-routed engineering queue submission. | Server-owned discounts tested; owned quotes isolated; C/F blocks completion; grouping requests persist. |
| U3 | Engineering editing, verified custom code integration, PN/SKU/BOM recalculation, custom pricing/lead time and review return. | Standard parity preserved; approved custom identities deterministic/collision-safe; exact offered revision available to owner. |
| U4 | Distributor acceptance/change requests, completed engineering queue, durable PDF and document retry; reuse/revision history. | Full cross-role workflow works with immutable accepted terms and the same stored PDF. |
| U5 | Security, accessibility, concurrency, performance, regression, deployment/rollback and controlled cutover. | UAT entry gates pass; old UI retirement or continued support explicitly decided; API clients remain compatible. |

Account tables, status workflow, real authorization and document persistence are backend scope, not optional post-SPA polish. Feature flags may hide unfinished paths until their slice is complete. Existing shared UAT security and migration prerequisites still apply regardless of how polished the SPA looks.

## 18. Acceptance tests that prove the feature

1. Applicant completes both required address/contact sets; duplicate submission creates one application; admin sees it; pending user cannot configure/quote through UI or direct API.
2. Admin approves with loyalty15; applicant receives persisted notification and gains access. Repeat for loyalty30. Rejection/change requests/suspension behave as explicitly defined.
3. Account A cannot read/update B's quote, application, notification or PDF by guessed IDs. Feature disablement blocks endpoint behavior as well as UI controls.
4. Discounts match decimal calculation/rounding and server policy. Tampered request rates, account IDs and totals are ignored/rejected. Unpriced C/F never becomes an accepted zero-valued price.
5. Standard Dean/Fybroc golden cases retain PN/SKU/BOM/price behavior across old and new UI clients. Editing roles/UI theme does not change engineering results.
6. Custom request in each applicable group persists correct group/field/revision. Unsupported custom identity remains blocked with a clear engineering gap.
7. Engineer resolves C/F, changes dependent specification, obtains the governed custom code, recomputes PN/SKU/BOM and enters price/lead time. Raw PN override and unauthorized catalog-price mutation are rejected.
8. Different approved custom designs cannot collide under PN/SKU uniqueness rules. Equivalent canonical custom designs reuse identity under the approved policy. Concurrency cannot allocate duplicate reserved codes.
9. Distributor sees the returned exact revision, can request changes or accept. Stale acceptance/edit returns a conflict. Double-click/timeout retry creates one completion and one logical final document.
10. Completed quote appears in engineering's completed queue; both parties download the same correct PDF. PDF failure is visible and retryable without losing accepted terms.
11. Changing loyalty/address/catalog publications later does not change the accepted snapshot/PDF. Reusing a completed quote creates a new draft that reprices under the defined policy.
12. Queue/notifications/quote state survives browser reload and application restart. Simultaneous engineer edits produce a conflict rather than silent data loss.
13. Direct API tests prove roles, ownership and approval gates, including old mounted routes; a role dropdown or forged headers cannot elevate privileges.
14. Keyboard navigation, modal focus, validation errors, long custom text, print layout and supported screen sizes are verified. Deep links/history refresh work without intercepting API routes.
15. Dean submissions appear only in IND/DEAN and Fybroc only in TEL/FYBROC, including notifications, counts, search, assignments, completed queues and PDFs. Cross-team direct API access, forged site/family values and globally role-authorized but unassigned engineers are denied. Distributor and ship-to location do not change routing.
16. Missing/conflicting routing is surfaced without wrong-team fallback; retries do not create duplicate review cases. Brand changes/new revisions and the approved single-brand/mixed-brand policy preserve routing history and prevent premature finalization.
17. Existing automated tests, SQL-backed audits and required workbook parity checks pass against explicit disposable/UAT targets. Do not reuse historic PASS counts or run destructive/bootstrap scripts on a populated database.

## 19. Open business decisions and safe implementation boundaries

Before dependent commercial behavior is enabled, resolve and record:

- Is an approved distributor required to have loyalty15/loyalty30, or may admin approve a no-discount account? Recommendation: explicit “Standard / 0%” option only if business approves; never silently assign 15%.
- Does “total sales” mean merchandise, all custom charges, freight, tax or a specific eligible subset? What price basis does engineering enter? What happens when tier changes before acceptance?
- Can fully standard/priced quotes complete without engineering? What lead-time authority applies?
- What exactly is the SQL custom-code table/spec, and how are distinct custom designs distinguished in PN/SKU?
- Which identity/onboarding model already exists for external distributors? Which current roles may approve accounts versus certify engineering/pricing?
- What are quote validity, resubmission/reopening and suspension effects on previously offered quotes?
- Which reference UI/file and current U1–U5 document govern visual implementation? The author has not seen them.

These are targeted policy questions, not reasons to stall baseline inspection, API inventory or the agreed SPA shell. Keep unresolved financial/numbering/authorization behavior disabled until a defensible decision exists. Present a recommendation with its impact whenever asking the owner to choose.

## 20. First response expected from the implementation agent

Before changing UI code, return:

1. Current branch/commit and worktree status; current milestone/log checkpoint.
2. Exact reference SPA and U1–U5 documents inspected.
3. Existing-versus-missing matrix for accounts, identity, roles, loyalty, custom codes, quote workflow, brand/site routing (DEAN→IND; FYBROC→TEL), engineer memberships, queues, PDF and audit.
4. Verified table/procedure/service names and any destructive migration risks.
5. Recommended answers to the five original questions, identifying which are proposals versus already authorized decisions.
6. A revised phased plan preserving metadata engines and API compatibility, with tests and migration/deployment requirements.
7. Only the unresolved business questions that cannot be answered from current code/logs/source evidence.

As each phase finishes, update the roadmap, implementation log and acceptance evidence: files/migrations/API contracts changed, schema/publication versions, tests actually executed, known limitations and the next exact task. Do not claim a screen is complete while its persistence, authorization or cross-role workflow is simulated.

## 21. Reference guidance

- Project architecture and authoritative source workbooks take precedence for engineering semantics.
- Previous companion assessment: `Pump_CPQ_UAT_Readiness_and_Deployment_Guide.md`; reconcile its findings with newer changes.
- React build options: https://react.dev/learn/build-a-react-app-from-scratch
- React TypeScript guidance: https://react.dev/learn/typescript
- Vite build tooling: https://vite.dev/guide/
- Entra application roles: https://learn.microsoft.com/en-us/entra/identity-platform/howto-add-app-roles-in-apps

These sources guide implementation mechanisms. They do not establish missing business policies or certify the current project.

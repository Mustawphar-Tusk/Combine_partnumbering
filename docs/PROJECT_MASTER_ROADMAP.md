# Pump Configurator Master Roadmap

**Roadmap Version:** 1.26  
**Roadmap Date:** 2026-08-26  
**Project:** Dean + Fybroc Pump Configurator  
**Status:** ACTIVE  
**Current Milestone:** D155 — Dean Codependencies Certification COMPLETE (PCL v0.1 `Codependencies` sheet B1:BA171 enforced: 256 non-seal tuples = 251 two-leg + 5 three-leg in cfg.FeasibleConstraint, matches the authoritative workbook; 519 seal tuples deferred per A1 crosswalk gap; fail-closed, no dead ends; FYBROC 4487 unchanged; audit_dean_codependencies 13/0, audit_dean_config 28/0, Fybroc gate 9/9). Prior: D145 — Dean UI Selection-Hierarchy Rearrangement COMPLETE; D140 — Dean Excel Oracle COMPLETE. Next permitted: D150 — Exhaustive Dean Regression — do NOT start without explicit go-ahead.  

---

# 1. Purpose

This document is the authoritative development roadmap for the Pump Configurator project.

It exists to prevent development drift, preserve project trajectory, define milestone exit gates, and provide a stable checkpoint that can be used to resume work after interruptions or unrelated investigations.

Development should follow this roadmap unless the roadmap itself is explicitly revised and versioned.

When work becomes distracted or uncertain, the recovery question is:

> What is the next unfinished exit criterion of the current roadmap milestone?

A new feature, experiment, bug, deployment idea, or architectural discussion does not automatically change the current milestone.

---

# 2. Final Project Objective

Deliver one centrally governed Dean and Fybroc pump configuration platform supporting:

- Dean pump configuration
- Fybroc pump configuration
- Engineering constraints
- Configuration dependencies
- Part Number generation
- SKU generation
- Pricing
- Adders
- Motors
- Seals
- Baseplates
- Couplings
- Testing/documentation selections
- Reusable BOMs
- Quotes
- Excel clients
- React web client
- SQL persistence
- FastAPI application services
- Microsoft Entra authentication
- Central Azure deployment
- Telford and Indianapolis access
- Auditing
- Versioned engineering metadata
- Automated regression testing

The final architecture is:

```text
Engineering Excel Sources
          |
          v
Versioned Metadata Compilers
          |
          v
Published SQL Metadata
          |
          v
SQL Configuration / Identifier / Pricing Engines
          |
          v
FastAPI
      /         \
     v           v
 Excel          React
      \         /
       v       v
Configured Product
       |
       +-- Part Number
       +-- SKU
       +-- BOM
       +-- Pricing

# 3. Project Governance Rules

The following rules apply throughout the project.

- No milestone is skipped.
- A milestone is complete only after its exit gate passes.
- New Excel workbooks are candidate sources until reconciled and explicitly promoted.
- Newer filenames do not automatically supersede older workbooks.
- Excel engineering logic remains authoritative during migration until SQL/API parity is proven.
- Dean/Fybroc behavior must be metadata-driven.
- Do not hardcode family-specific engineering rules inside FastAPI routes.
- SQL Server will become authoritative for final configured-product identity.
- Final production Part Number generation will occur in SQL.
- Final production SKU generation will occur in SQL.
- Excel and React must receive identical engineering results.
- Real Microsoft Excel will be used as a regression oracle where formulas or VBA materially determine expected behavior.
- Authoritative workbooks must never be modified by automated regression tests.
- Excel regression tests must operate on disposable workbook copies.
- No destructive database cleanup occurs until replacement functionality has proven parity.
- Correctness precedes UI development.
- Configuration correctness precedes BOM and quote development.
- Each milestone ends with:
- targeted tests
- full regression
- evidence artifacts
- explicit exit-gate decision
- Git checkpoint
- Failed exit gates keep the project in the same milestone.
- The mandatory per-milestone exit audit is defined in
  `.kiro/steering/milestone-exit-audit.md` (always-on process rule): deliverables
  inventory, milestone-specific audit, cross-family regression gate, isolation
  check, build/verify, evidence doc, roadmap+register update, git checkpoint,
  explicit PASS/FAIL decision, then wait for user go-ahead. Run it before
  declaring any milestone done and before starting the next.
- Every configured engineering result must retain source/version lineage.
- CORRECTIONS ARE PERMANENT AND MUST NOT REGRESS. Every correction made in a
  milestone is guarded by a re-runnable audit. The consolidated regression
  runner `scripts/run_all_fybroc_audits.py` must pass (exit 0, "ALL CORRECTIONS
  INTACT") before any milestone is declared done and before starting the next
  milestone. If a later change makes it fail, that change conflicts with an
  established correction and must be reconciled — never override the correction.
  Current guarded corrections: Selections X/STD applicability + V6 flange
  authority (audit_selections_vs_db.py); Feasible Constraint fail-closed +
  allow-list ordering (audit_feasible_constraints.py); all four Motor Constraint
  relationships (audit_motor_constraints.py).



# 4. Completed Foundation
Historical Fybroc Foundation

- Existing Fybroc work established:

- configuration metadata extraction
- constraints
- nomenclature
- identifier generation
- FastAPI V1
- state/option token workflow
- Excel VBA API bridge
- configured-product persistence
- configuration signature
- Part Number persistence/reuse
- SKU persistence/reuse
- pricing architecture
- seal pricing
- combined pricing publication
- Price Check Q80/Q81 bridge


# 5. Standard Milestone Execution Method

Every milestone follows this lifecycle.

1. CHECKPOINT
        |
        v
2. INVENTORY
        |
        v
3. ANALYZE
        |
        v
4. DESIGN
        |
        v
5. IMPLEMENT
        |
        v
6. TARGETED TEST
        |
        v
7. FULL REGRESSION
        |
        v
8. EVIDENCE
        |
        v
9. EXIT GATE
        |
        +---- FAIL ---> remain in milestone
        |
       PASS
        |
        v
10. GIT CHECKPOINT
        |
        v
11. ROADMAP UPDATE
        |
        v
NEXT MILESTONE

Every milestone must identify:

Objective
Inputs
Deliverables
Tests
Evidence
Exit gate
Git checkpoint
Next permitted milestone


# 6. PHASE F — FYBROC COMPLETION

Fybroc will be completed before Dean implementation continues.

The complete Fybroc source set is:

- Fybroc Attributes and Constraints.xlsx
- Fybroc Nomenclature_V5.xlsm
- Price Estimator-Fybroc.xlsm
- Fybroc Configuration Rev0.3.xlsx
- Nomenclature_V6.xlsm

Legacy files remain regression/reference sources until F180.


# F100 — Fybroc Source Inventory & Reconciliation

Status: CURRENT

Objective

Fully inventory all five Fybroc engineering workbooks before modifying the current runtime.

Required inspection

Extract and classify:

worksheets
hidden worksheets
Excel tables
named ranges
formulas
data validation
lookup ranges
external links
VBA modules
VBA procedures/functions
configuration fields
option domains
constraints
dependencies
hierarchy
combination logic
feasible constraints
motor constraints
nomenclature rules
identifier mappings
pricing tables
pricing formulas
adders
testing rules
quote/specification mappings
Deliverables
FYBROC_SOURCE_INVENTORY
FYBROC_SOURCE_LINEAGE
FYBROC_SOURCE_CONFLICT_REGISTER
FYBROC_FIELD_INVENTORY
FYBROC_PRICING_SOURCE_INVENTORY
Exit Gate

PASS only when every relevant engineering object in all five workbooks has been classified and no workbook remains structurally unexplained.

Next

F110

F110 — V5 to V6 Nomenclature Reconciliation
Objective

Determine exactly how Nomenclature V6 differs from V5.

Required analysis

Compare:

Smart Number
Attributes
Pump Options
Pump Options - Horizontal
Pump Options - Vertical
Seal Assembly
Seal Assembly - Horizontal
Setting-Length-Vertical
Options
Options - Horizontal
Options - Vertical
Motor Assy
Testing
identifier segment sequence
identifier codes
combination rules
source fields
orientation behavior
Classification

Each difference must be classified:

UNCHANGED
NEW
CHANGED
DEPRECATED
CONFLICT
NEEDS_ENGINEERING_REVIEW
Deliverables
FYBROC_V5_V6_DIFF
FYBROC_IDENTIFIER_SEGMENT_DIFF
FYBROC_HORIZONTAL_VERTICAL_RULES
FYBROC_TESTING_RULE_DIFF
Exit Gate

No unexplained V5/V6 nomenclature difference.

Next

F120

F120 — Fybroc Rev0.3 Configuration Model
Objective

Compile the newer configuration intelligence into a normalized engineering model.

Required sources

From Fybroc Configuration Rev0.3:

Items
Constraints
Hierarchy
Combine Variables
Selections
Constraint Index
Feasible Constraints
Motor Constraints
Compare against current SQL metadata
cfg.AttributeValue
cfg.SeriesFieldOption
cfg.FieldOptionDependency
current compiler outputs
Deliverables
FYBROC_CONFIGURATION_MODEL
FYBROC_CONSTRAINT_DIFF
FYBROC_DEPENDENCY_DIFF
FYBROC_MOTOR_CONSTRAINT_DIFF
FYBROC_COMBINATION_DIFF
Exit Gate

Every new rule is either:

represented in current metadata
added to the new model
explicitly marked deprecated
explicitly placed in engineering review

No selectable value may bypass an established constraint.

Next

F130

F130 — Fybroc Pricing & Adders Reconciliation
Objective

Establish a complete and traceable Fybroc pricing truth.

New-source review

Fybroc Configuration Rev0.3:

Pricing Index
1500 Pricing
5500 Pricing
Existing-source review

Price Estimator-Fybroc:

Price Check
Pricebook
Adders
motor pricing
seal pricing
coupling pricing
baseplate pricing
relevant horizontal pricing
relevant vertical pricing
remaining formula-driven adders
Deliverables
FYBROC_PRICING_DIFF
FYBROC_ADDER_REGISTER
FYBROC_PRICE_PRECEDENCE
FYBROC_PRICE_FORMULA_REGISTER
FYBROC_PRICE_SOURCE_LINEAGE

Every price/add-on must identify:

source workbook
worksheet
source range/cell/table
applicability
condition
precedence
amount/formula
publication version
Exit Gate

No price or adder used by the business remains unexplained.

Next

F140

F140 — Fybroc Metadata Corrections & Publication
Objective

Correct the configuration metadata based on F100-F130.

Supported series
1500
1530
1600
1630
2530
3000
5500
Required corrections

Include where applicable:

orientation
size
material
impeller
pump options
seal assembly
general options
vertical setting length
motor assembly
motor modifications
testing
pricing
adders
Exit Gate

For every supported series:

valid options project correctly
invalid options fail closed
dependency transitions work
no unexplained empty-option state exists
Next

F150

F150 — SQL Fybroc Identifier Authority
Objective

Move configured-product identity authority into SQL Server.

SQL responsibilities

SQL will generate:

canonical configuration identity
configuration signature
Part Number
SKU V2
configured-product reuse decision
Part Number

Must remain engineering-readable and match approved workbook nomenclature.

SKU V2

Target format:

<BaseIdentifier>-V<Version>-<8-character deterministic token>

Example:

F1530-V1-4F8X2N7C

The full SHA-256 signature remains the authoritative identity key.

Migration rule

Keep the existing Python identifier engine as a parity oracle until SQL passes regression.

Exit Gate

For all approved Fybroc regression cases:

SQL Part Number = approved legacy/workbook Part Number.

SKU V2 must be deterministic and collision protected.

Next

F160

F160 — Excel Oracle Harness
Objective

Use actual Microsoft Excel calculation and approved VBA as an automated engineering oracle.

Process

For each test:

copy authoritative workbook to disposable location
open through Excel COM
populate configuration
recalculate
invoke only inspected safe macros where required
capture outputs
compare against SQL/API
close without modifying source workbook
Capture
valid options
Part Number
identifier segments
base price
seal price
motor price
adders
total price
specifications
quote-relevant results
Exit Gate

Repeatable Excel-oracle tests operate safely against disposable workbook copies.

Next

F170

F170 — Exhaustive Fybroc Regression
Objective

Prove Fybroc configuration completeness.

Test dimensions
every supported series
horizontal
vertical
all sizes
material families
standard configurations
optional configurations
seals
motors
motor modifications
coupling
baseplate
testing
pricing
adders
invalid combinations
boundary cases
configuration reuse
Part Number
SKU
API response
performance
Exit Gate

Zero unexplained engineering failures.

All accepted deviations must be formally documented.

Next

F180

F180 — Fybroc Signoff & Freeze
Objective

Establish a production-grade Fybroc engineering publication.

Deliverables
approved metadata publication
approved pricing publication
regression package
source lineage
known limitations
engineering signoff
Git checkpoint
Exit Gate

Fybroc declared configuration-complete.

Next

D100



# 7. PHASE D — DEAN COMPLETION

Dean begins only after F180.

Dean authoritative source candidates:

Dean Data Sheet Rev 2.xlsm
PumpConfiguration_Logic.xlsm
Copy of Motor Numbering.xlsm
Dean Pricing Matrix.xlsx
D100 — Dean Source Reconciliation

Deep-inventory and reconcile all four workbooks.

Deliverables:

DEAN_SOURCE_INVENTORY
DEAN_SOURCE_LINEAGE
DEAN_FIELD_DIFF
DEAN_PRICING_SOURCE_INVENTORY
DEAN_CONFLICT_REGISTER

Exit gate:

All Dean engineering sources classified and reconciled.

D110 — Dean Configuration & Dependency Completion

Complete the Dean configuration model.

Revisit the five unresolved M023.3 dependency groups only after analyzing the newly added Dean sources.

Include:

applicability
dependencies
motor
seal
flush
barrier
cooling
throttle bushing
bearing-frame cooling
couplings
baseplate
shaft configuration
testing/documentation
additional options

Exit gate:

No unexplained dependency remains.

D120 — Dean Pricing & Adders

Compile:

standard options
motor pricing
coupling pricing
baseplate pricing
shaft configuration pricing
seal pricing
engineering adders
workbook formula-derived pricing

Exit gate:

Complete traceable pricing publication.

D130 — SQL Dean Identifier Authority

SQL must generate:

Series + Size
      |
      v
Authoritative A-number
      |
      v
A### -> D###
      |
      v
Remaining engineering segments
      |
      v
Dean Part Number
      |
      v
SKU V2

Exit gate:

SQL output matches approved Dean workbook output.

D140 — Dean Excel Oracle

Implement Dean workbook COM regression parity.

Exit gate:

SQL/API results consistently match approved Excel results.

D150 — Exhaustive Dean Regression

Test all supported Dean configuration domains.

Exit gate:

Zero unexplained engineering failures.

D160 — Dean Signoff & Freeze

Freeze approved Dean configuration and pricing publication.

Exit gate:

Dean declared configuration-complete.

Next

U100


# 8. PHASE U — UNIFIED APPLICATION

Begins only after F180 and D160.

U100 — Canonical Product Model

Implement:

canonical configuration JSON
manufacturing sites
TEL = Telford
IND = Indianapolis
active configured-product schema consolidation
historical lineage
selection-row deprecation plan

Exit gate:

Both families persist through one product model.

U110 — Unified Configuration Dictionary

Compile complete Dean/Fybroc runtime dictionaries.

Exit gate:

Both families load completely from published metadata.

U120 — FastAPI V2

Target endpoints:

GET /api/v2/families/{family}/configuration-dictionary
POST /api/v2/families/{family}/configurations/evaluate
POST /api/v2/families/{family}/configurations/validate
POST /api/v2/families/{family}/configured-products/resolve

Keep V1 temporarily for compatibility.

Exit gate:

Both families operate successfully through V2.

U130 — Reusable BOM Engine

Implement:

BOMHeader
BOMLine
configured-product BOM relationship
BOM versioning
BOM reuse

Exit gate:

Repeated identical configured products reuse the appropriate BOM.

U140 — Quote Engine

Correct the current quote architecture.

Align QuoteLine with the active configured-product registry.

Persist:

configured product
family
site
Part Number
SKU
ConfigurationJson
BOM
quantity
unit price
extended price
pricing lineage
publication lineage

Exit gate:

Complete quote is reproducibly persisted and rendered.

U150 — Excel Runtime V2

Replace slow chained V1 navigation.

Target flow:

Excel change
    |
    v
Current configuration JSON
    |
    v
ONE evaluate request
    |
    v
FastAPI cached metadata
    |
    v
Updated allowable options

Exit gate:

Excel configuration interaction meets agreed responsiveness target.

U160 — React Configurator

Build one React UI consuming the same V2 API as Excel.

Exit gate:

Equivalent configuration in React and Excel produces identical results.

U170 — Security & Audit

Implement:

Microsoft Entra ID
application roles
authorization
secure secrets
audit
engineering publication roles
pricing roles
sales/configurator roles

Exit gate:

Security model approved.

# 9. PHASE T — CENTRAL TESTING & UAT
T100 — CI/CD

Automate:

uv sync --locked
tests
SQL migration validation
application build
deployment
Git/version traceability
T110 — Azure TEST Environment

Deploy:

central TEST FastAPI/React
Azure SQL TEST
Entra authentication
shared Telford/Indianapolis access
T120 — Telford UAT

Fybroc plant acceptance.

T130 — Indianapolis UAT

Dean plant acceptance.

T140 — Cross-Family UAT

Confirm centralized operation and family/site behavior.

T150 — UAT Correction Cycle

Correct documented UAT defects only.

Do not introduce uncontrolled new features.

Exit gate:

UAT release threshold achieved.

T105 — UAT-Readiness Hardening (prep for T110+)
----------------------------------------------
Architecture-review follow-ups (2026-08-26). The core design is UAT-aligned
(env-driven config, versioned+reversible data publications, family isolation,
executable regression gate). These close the gaps that make DEV -> UAT promotion
and redeploy safe and repeatable. None change the core approach.

  T105.1  Guard the dev auth bypass — fail-closed. The Entra-ID auth bypass must
          engage ONLY when APP_ENVIRONMENT == 'development'; any other/unset value
          must require real token validation (never silently bypass in UAT/PROD).
          Add a startup assertion + a test.
  T105.2  Schema migration tooling. Replace manual application of sql/*.sql with a
          versioned migrator (sqlpackage/DACPAC or Alembic) so any environment's
          schema can be brought to a known version by ONE command, matching the
          already-versioned data publications. (CI only checks files are non-empty
          today — it does not verify SQL parses or applies.)
  T105.3  Wire the regression gate into CI as a required pre-UAT check. CI today
          runs: uv sync, pytest, a non-empty SQL file check, and an import check —
          it does NOT run run_all_fybroc_audits.py (needs live SQL Server + API).
          Add a CI job (service container or ephemeral DB) that runs the audit gate
          and requires "ALL CORRECTIONS INTACT" before promotion.
  T105.4  Secrets management. Move CONFIGURATION_TOKEN_SECRET + DB credentials to a
          secret store (Azure Key Vault) for UAT/PROD; .env for local only.
  T105.5  Promotion + rollback runbook. Document the DEV -> UAT promotion: deploy
          code -> apply schema migration -> run compiler/publisher against the UAT
          DB -> run run_all_fybroc_audits.py -> sign off. Rollback = flip the prior
          PriceBookVersion/publication IsCurrent back (old versions are retained).
  T105.6  Price-adjustment reapply policy. Decide whether a manual
          price.usp_ApplyPriceAdjustment should auto-reapply after a republish, so a
          UAT price tweak is not silently lost on the next publish. The audit log
          (price.PriceAdjustment / PriceAdjustmentRow) already preserves what was
          applied; wiring auto-reapply into the publish flow is the open decision.

Exit gate (T105): auth bypass fail-closed + migration command exists + CI runs the
audit gate + secrets externalized + promotion/rollback runbook written.

10. PHASE P — PRODUCTION
P100 — Performance & Concurrency
Validate:

configuration latency
identifier generation
pricing
quote creation
concurrent users
Excel interaction
web interaction
P110 — Resilience & Recovery

Implement and test:

backups
restore
migration rollback
application rollback
failure recovery
P120 — Monitoring

Implement:

Application Insights
API errors
SQL monitoring
audit monitoring
operational dashboards
P130 — Security Review

Final security validation.

P140 — Production Infrastructure

Provision central Azure production environment.

P150 — Production Metadata Publication

Publish approved Dean and Fybroc metadata/pricing versions.

P160 — Production Cutover

Release centrally to:

Telford
Indianapolis
P170 — Training & Documentation

Deliver:

user guide
engineering guide
pricing administration guide
support guide
deployment guide
recovery guide
architecture documentation
P180 — Stabilization

Resolve controlled post-launch defects.

P190 — Project Closeout

Final deliverables:

architecture
source lineage
database documentation
API documentation
regression suites
engineering publications
deployment documentation
operational ownership
final Git release/tag

Project status:

COMPLETE


# 11. Roadmap Milestone Summary

Milestone	Description	Status

M024.1	uv migration	COMPLETE
M024.2	architecture baseline	COMPLETE
F100	Fybroc source inventory	COMPLETE
F110	V5/V6 nomenclature reconciliation	COMPLETE
F120	Rev0.3 configuration model	COMPLETE
F130	Fybroc pricing/adders	COMPLETE
F140	Fybroc metadata corrections	COMPLETE (exited 2026-08-28)
F150	SQL Fybroc identifier	COMPLETE — SQL-authoritative PN/SKU, python parity 44/44
F160	Fybroc Excel Oracle	COMPLETE — fybroc_oracle_compare.py 6/6 (Excel==API)
F170	Fybroc exhaustive regression	COMPLETE — gate ALL CORRECTIONS INTACT + 10-series batch 0 errors
F180	Fybroc signoff	SIGNOFF PREPARED — awaiting engineering signature (CURRENT)
D100	Dean source reconciliation	COMPLETE — 5 workbooks classified; PumpConfiguration_Logic authority (docs/evidence/D100/DEAN_D100_EXIT.md)
D110	Dean configuration completion	COMPLETE — model published to SQL (family 1), audit 45/45, Fybroc gate intact (docs/evidence/D110/DEAN_D110_EXIT.md)
D120	Dean pricing/adders	COMPLETE — Dean Pricing Matrix published to SQL (DEAN_STANDARD, 9874 rules), pricing audit 22/22, Fybroc gate intact (docs/evidence/D120/DEAN_D120_EXIT.md)
D130	SQL Dean identifier	COMPLETE — SQL generates the Dean Part Number (additive @FamilyCode='DEAN' branch in cfg.usp_AssembleConfiguredProduct); A#->D# + segment codes loaded family-scoped (204 model refs + 428,742 seg rows), identifier audit 8/8, pricing 22/22, config 29/29, Fybroc gate 7/7 intact. Seal excluded (external accdb); some models blocked by external STD Standard Confs accdb (disclosed). (docs/evidence/D130/DEAN_D130_EXIT.md)
D140	Dean Excel Oracle	COMPLETE (2026-08-26) — Re-based onto the NEW authority PumpConfiguration_Logic_0.1.xlsm (supersedes prior Dean numbering/config sources). Identifier numbering re-loaded (206 model refs + 106,892 seg rows in one DEAN batch; old 428,742-row batch removed) and resolver re-based (new field orders, table-backed flush + motor-frame, unbuilt-segment placeholders). Excel COM numbering-table oracle proves SQL/API codes == workbook live codes (dean_oracle_compare 15/15 seg matched, 0 failed). identifier 8/8, config 28/28, pricing 22/22, Fybroc gate ALL CORRECTIONS INTACT 7/7, Fybroc rows unchanged (isolation). Disclosed gaps: seal omitted-not-discarded + 519 skipped seal codependencies (A1); external Standard Confs STD gap (A2); Cooling/Barrier un-built + Motor main code inert (F1/F2/F3). (docs/evidence/D140/DEAN_D140_EXIT.md)
D145	Dean UI selection-hierarchy rearrangement	COMPLETE — presentation-only; authoritative Dean Data Sheet Rev 2 order + 10-group render via additive field_groups; C/F for unbuilt authoritative fields; bundle-excluded components omitted; identity fields owned by Series/Size selectors; Fybroc flat/byte-unchanged; PN/parity unchanged. Milestone audit scripts/audit_dean_ui_rearrange.py 40/40; Fybroc gate ALL CORRECTIONS INTACT 9/9; Dean baselines unchanged (48063/256/206/37). (docs/evidence/D145/DEAN_D145_UI_REARRANGE_EXIT.md)
D155	Dean Codependencies Certification	COMPLETE (2026-08-26) — PCL v0.1 Codependencies sheet (B1:BA171, 775 tuples) certified enforced: 256 non-seal tuples (251 two-leg + 5 three-leg) in cfg.FeasibleConstraint, matches the authoritative workbook exactly; 519 seal tuples deferred (A1 seal-vocab crosswalk, engineering-blocked, disclosed); fail-closed + no dead ends; FYBROC 4487 unchanged. New re-runnable audit scripts/audit_dean_codependencies.py 13/0 (expectations derived from re-parsing the workbook); audit_dean_config 28/0; Fybroc gate ALL CORRECTIONS INTACT 9/9. Verify-only (no data/schema/code change). (docs/evidence/D155/DEAN_D155_CODEPENDENCIES_EXIT.md)
D150	Dean exhaustive regression	NOT STARTED
D160	Dean signoff	NOT STARTED
U100	canonical product model	PARTIAL — needs re-verification
U110	unified configuration dictionary	PARTIAL — needs re-verification
U120	FastAPI V2	OPERATIONAL (V2 endpoints live)
U130	reusable BOM	NEEDS RE-VERIFICATION
U140	quote engine	NEEDS RE-VERIFICATION
U150	Excel V2	NEEDS RE-VERIFICATION
U160	React UI	NOT BUILT (HTML configurator serves as UI)
U170	security/audit	NOT COMPLETE (no Entra auth yet)
T100	CI/CD	PARTIAL (CI runs: uv sync, pytest, non-empty SQL check, import check; does NOT run run_all_fybroc_audits — see T105.3)
T105	UAT-readiness hardening	NOT STARTED (6 items: auth-bypass guard, schema migrations, CI audit gate, secrets, promotion/rollback runbook, adjustment-reapply policy)
T110	Azure TEST	NOT STARTED (preview env on Render/Vercel/ngrok instead)
T120	Telford UAT	NOT STARTED
T130	Indianapolis UAT	NOT STARTED
T140	cross-family UAT	NOT STARTED
T150	UAT corrections	NOT STARTED
P100	performance	PENDING
P110	recovery	PENDING
P120	monitoring	PENDING
P130	security review	PENDING
P140	production infrastructure	PENDING
P150	production publication	PENDING
P160	cutover	PENDING
P170	documentation/training	PENDING
P180	stabilization	PENDING
P190	closeout	PENDING


# 12. Current Project Checkpoint

MASTER ROADMAP
Version:            1.28

Current Phase:      D — Dean Completion
Current Milestone:  D110 config FIELD-ACCURACY AUDIT + Custom->C/F relabel
                    COMPLETE. D110 config RE-EXTRACT CERTIFICATION COMPLETE
                    (verify-only).
                    D155 (Dean Codependencies Certification) COMPLETE
                    (verify-only). D145 (Dean UI Selection-Hierarchy
                    Rearrangement) COMPLETE. D140 (Dean Excel Oracle) COMPLETE.
                    Next permitted: D150 (Exhaustive Dean Regression) — do NOT
                    start without explicit go-ahead.
                    (v1.15 is a Fybroc constraint-authority maintenance change,
                    not a Dean milestone advance — see CHANGE v1.15.)
Status:             D100 + D110 + D120 + D130 + D140 + D145 + D155 complete
                    (2026-08-26). F180 signoff remains prepared, awaiting
                    engineering signature (parallel; Dean is net-new work that
                    does not modify frozen Fybroc data).

CHANGE (v1.28): Dean CONFIG FIELD-ACCURACY AUDIT (all fields) + Custom->C/F
relabel (D110; Dean-only data change, Fybroc frozen). Proved the DB
cfg.SeriesFieldOption (DEAN) is a BYTE-EXACT image of the authoritative
PumpConfiguration_Logic_0.1.xlsm "Pump Constraints" sheet across EVERY
(series,size,field): new scripts/audit_dean_config_accuracy.py independently
re-parses the sheet as oracle (shares only the norm_label/_norm_value
canonicalization contract) and diffs cell-for-cell -> 8/0, 0 MISSING, 0 EXTRA,
0 STD/marker mismatch, 0 field-presence diffs (206 models, 37 series, 68 mapped
fields, 48,157 raw STD/X cells -> 48,063 distinct rows, STD 11,786==11,786; 94
duplicate value-header columns collapse). Per user clarification, sheet value
"Custom" (customer-request option outside the standard offering) is relabeled to
C/F (Contact Factory) in loader _norm_value() -> applies to BOTH per-model option
rows AND codependency legs: 2,329 'Custom' SFO rows across 20 fields (all X, never
STD) became 'C/F', and 4 non-seal codep legs (CASING_TAPS/CASING_GASKET/
IMPELLER_TRIM) became 'C/F'; totals unchanged (SFO 48,063; FeasibleConstraint 256).
DB==sheet audit still 8/0 after relabel. New scripts/audit_dean_config_accuracy_live.py
proves the API projects the data (6/6 models incl. row-167+ RM5140; 286 STD-exact
+ 326 no-leak checks, 0 fail). Regression: audit_dean_config 28/0,
audit_dean_codependencies 13/0, run_all_fybroc_audits ALL CORRECTIONS INTACT 9/9;
FYBROC watermarks unchanged (FeasibleConstraint 4487, ConstraintFieldMap 28,
SeriesFieldOption 3638). Pending-engineering (disclosed): C/F downstream
quote/numbering logic not yet built; BARRIER_PLAN has no per-model STD/X by design
(governed by deferred seal quad A1); 519 seal codep tuples still deferred. D150 not
started. See docs/evidence/D110/DEAN_D110_FIELD_ACCURACY_AUDIT.md.

CHANGE (v1.27): Dean CONFIGURATION RE-EXTRACT CERTIFICATION (D110, verify-only; no
schema/loader/data/runtime change). On user request ("re-extract Dean's
configuration ... STD and allowable ... datasheet: Pump Constraints" + explicit
67-group column map; row range "the full load: 4–209: full sheet"), re-ran the
authoritative loader scripts/d110_load_dean_config_v01.py against
PumpConfiguration_Logic_0.1.xlsm "Pump Constraints". Confirmed the loader already
implements the user's exact column map (A/B/C identity; 68 row-2 groups, 0 skipped
— e.g. Pump Config E–L, Pump Material N–V, Casing Material X–AF, Impeller Trim
CN–GH=99, Seal Type JX–LC=32, Frame Size RC–UH=84, Crating WA–WE) over the full
sheet (data rows 4–209 = 206 models). Dry-run 206 models / 37 series / 68 fields /
11,786 STD cells / 0 unmapped. Real Dean-only reload reproduced the published
baseline EXACTLY (cfg.SeriesFieldOption DEAN 48,063; FeasibleConstraint DEAN 256 =
251 2-leg + 5 3-leg; 519 seal tuples still DEFERRED pending A1 crosswalk) —
git status clean, ZERO file/DB diff. Live resolve-state verified for RA3146,
PH2110, DL200, R5140, and the row-167+ models RM5140 + Deanline (all valid, SIZE
present, STD seeded, no empty-option dead ends). audit_dean_config 28/0;
audit_dean_codependencies 13/0 (FYBROC FeasibleConstraint unchanged 4487);
run_all_fybroc_audits ALL CORRECTIONS INTACT 9/9; FYBROC row counts unchanged
(Feasible 4487, SFO 3638, CFM 28). Casing Heat Jacket + Shipping Gasket remain
offered options that do NOT drive the wet-end PN (unchanged, separate). D150 still
not started. See docs/evidence/D110/DEAN_D110_CONFIG_REEXTRACT_CERTIFICATION.md.

CHANGE (v1.26): Dean Codependencies CERTIFICATION (D155, verify-only; no
schema/loader/data/runtime change). Certified that the authoritative PCL v0.1
`Codependencies` sheet (PumpConfiguration_Logic_0.1.xlsm, B1:BA171, 775 allow-
tuples) is correctly enforced as Dean cross-constraint dependencies: 256 non-seal
tuples (251 two-leg + 5 three-leg) live in cfg.FeasibleConstraint and match the
workbook EXACTLY (count + leg distribution derived by re-parsing the sheet, not
hardcoded). The 519 seal-related tuples remain DEFERRED (held out of enforcement)
pending the A1 seal-vocabulary crosswalk — the Codependencies sheet uses long
descriptive seal names while Pump Constraints uses short canonical names (e.g.
`Type N`), so enforcing them would prune seal options to a dead end; seal stays
omitted-not-discarded. NO enforced row touches a seal field; the only 4-leg quad
(Seal Option × Gland Type × Flush Plan × Barrier Plan) is correctly not enforced.
New re-runnable audit scripts/audit_dean_codependencies.py (13/0): DB==workbook
non-seal enforced (256), leg dist {2:251,3:5}, 0 seal-field rows, 519 held-out
accounted, all legs mapped in ConstraintFieldMap, FYBROC FeasibleConstraint 4487
unchanged, live fail-closed (CASING_MATERIAL=none -> CASING_GASKET prunes 3/13),
no dead ends. audit_dean_config 28/0; run_all_fybroc_audits ALL CORRECTIONS INTACT
9/9. Dean phase advances D145 -> D155; D150 still not started. See
docs/evidence/D155/DEAN_D155_CODEPENDENCIES_EXIT.md.

CHANGE (v1.25): Dean configurator UI SELECTION-HIERARCHY REARRANGEMENT
(D145, presentation-only; no schema/loader/data change). Aligned the Dean UI field
ORDER + GROUPING to the authoritative Dean Data Sheet Rev 2 (Smart Number B3:AL26 +
Data Sheet B12:I71 + Dean Pump Specification Sheet): added a Dean-specific field
hierarchy + the authoritative 10 groups (Pump Information, Impeller, Power Frame,
Coupling, Pump Seal, Flush/Barrier/Cooling Plan, Motor, Baseplate, Testing &
Documentation, Additional Options), delivered as an ADDITIVE `field_groups`
response field on /configurations/evaluate + /configurations/resolve-state
(default [] -> back-compatible; empty for non-Dean). Ordering is family-aware
(_order_fields/_hierarchy_rank take family; Fybroc byte-unchanged). Empty/unbuilt
authoritative fields render as C/F placeholders (Motor beyond FRAME_SIZE, Testing &
Documentation, Barrier Plan); fields a PUMP_CONFIGURATION bundle excludes are
OMITTED (not C/F); identity fields (SERIES/SIZE/ALT_SIZE) are owned by the
Series/Size selectors, not the grid. UI (ui/configurator.html) renders group
headers + disabled C/F rows for Dean, flat (unchanged) for Fybroc. PN assembly /
parity / certified PCL v0.1 numbering UNCHANGED (presentation only). Verified:
milestone audit scripts/audit_dean_ui_rearrange.py 40/40 (PH2110/DL200/RA3146/
R5140); run_all_fybroc_audits ALL CORRECTIONS INTACT 9/9; Dean baselines unchanged
(SFO 48063 / Feasible 256 / 206 models / 37 series); imports OK; temp scripts
cleaned. Dean phase advances D140 -> D145; D150 still not started. See
docs/evidence/D145/DEAN_D145_UI_REARRANGE_EXIT.md.

CHANGE (v1.24): Dean PCL v0.1 numbering-authority CERTIFICATION (verify-only; no
data/schema/code change). Certified that PumpConfiguration_Logic_0.1.xlsm (its
Module1/Module2 numbering macros) is the authoritative, LOADED source for the Dean
configuration build-up — adoption was already implemented under the D140 re-base
(scripts/load_dean_identifier_to_sql.py loads the 6 numbering sheets via header-search
Module1/2 semantics; src/api/dean_identifier.py resolves segments with python==SQL
parity). DB-verified: stg.SegmentCombinationImport DEAN batch id=5 (hash
cc1fab74...706e, 106,892 rows) — WET_END 49987, POWER_FRAME 55452, BASEPLATE 1153,
FLUSH_PLAN 185, IMPELLER 24, MOTOR_FRAME 91; cfg.PumpModelReference DEAN 206 models /
37 series (A#->D#). Bounded live parity probe 12/12 PASS (base_identifier correct 12/12;
parity_ok 0 fails; segment codes from the loaded tables; only wet_end/power_frame '?'
= disclosed A2 Standard-Confs external-DB gap). Isolation: run_all_fybroc_audits ALL
CORRECTIONS INTACT 9/9; baselines unchanged (Dean SFO 48063 / Feasible 256; pricing
FYBROC 56355 / DEAN 9874). Documented engineering gaps (NOT dev defects): Cooling Plan
Numbering empty (F1), Barrier Plan 0 rows (F2), Motor main code inert 000 (F3), Standard
Confs (A2) + Seal code (A1) external Access DBs not provided. Full-stride
audit_dean_identifier is the D150 exhaustive step (run out-of-band; ~17s/model). Dean
phase status UNCHANGED (D140 current; D150 not started). See
docs/evidence/D100/DEAN_PCL_V01_NUMBERING_CERTIFICATION.md.

CHANGE (v1.23): Architecture review + UAT-readiness hardening backlog recorded
(docs only; no code/data/schema change). Confirmed the stack: FastAPI + Uvicorn +
Pydantic v2 API; SQL Server via raw pyodbc in the runtime hot path and SQLAlchemy
CORE (text()) in the repository layer — NO ORM (no mapped entities); logic lives in
SQL DDL + stored procs. SQL-injection posture verified: parameterized queries
everywhere (? / named binds), no string-interpolated SQL in v2_routes, param-bound
stored procs, Pydantic boundary validation. Evaluated and REJECTED a Tortoise-ORM
switch (Tortoise has no SQL Server support -> would force a Postgres migration +
rewrite of the stored-proc/set-based core the audits depend on; if an ORM is ever
wanted, SQLAlchemy ORM is the lower-risk path since it is already a dependency and
keeps MSSQL). Added Phase-T milestone T105 (UAT-Readiness Hardening) with 6 tracked
items: T105.1 fail-closed dev auth-bypass guard; T105.2 schema migration tooling
(sqlpackage/DACPAC or Alembic); T105.3 run run_all_fybroc_audits in CI as a required
pre-UAT gate (CI today = uv sync + pytest + non-empty-SQL check + import check only);
T105.4 secrets to Key Vault; T105.5 DEV->UAT promotion + rollback runbook; T105.6
decide price-adjustment auto-reapply-after-republish policy. Status table + T100 note
updated. No milestone objective redefined. Dean phase status UNCHANGED (D140 current;
D150 not started).

CHANGE (v1.22): Targeted price-adjustment procedure (both families). Added
sql/19_Create_Price_Adjustment.sql: price.usp_ApplyPriceAdjustment applies a PERCENT
change to price.PriceRule.Amount for the CURRENT (IsCurrent) price book version,
scoped @ScopeType=ALL_FAMILIES|FAMILY|SERIES (+ optional @ComponentCode child; NULL=all).
Model: a pump SERIES (Fybroc 1500, Dean PH2110, ...) is the parent, its priced
COMPONENTS are the children — a FAMILY/SERIES scope with no component cascades to all
child rows. @DryRun=1 (default) previews + writes nothing; @DryRun=0 updates in a txn and
audits every change in price.PriceAdjustment (header) + price.PriceAdjustmentRow (per-rule
old/new), so changes are traceable + reversible. FAMILY/SERIES are family-isolated;
ALL_FAMILIES is the only cross-family scope. Validation THROW 52001-52007 (incl pct<=-100
guard, empty-target guard). SeriesCode match handles '1530 (ANSI)'. Thin CLI
scripts/apply_price_adjustment.py (defaults to dry-run). VERIFIED: scope counts (ALL 66229
= FYBROC 56355 + DEAN 9874; FYBROC/1500 all=5193, +SHAFT=38), real +10% round-trip reverted
to byte-identical, DEAN untouched under FAMILY scope, CLI preview + validation. Gate ALL
CORRECTIONS INTACT 9/9; pricing UNCHANGED (mechanism only, 0 live adjustments; FYBROC 56355
/ DEAN 9874 at baseline). price.PriceRule is the table to update; this proc is the supported
entrypoint. Dean phase status UNCHANGED (D140 current; D150 not started). See
docs/evidence/PRICING/PRICE_ADJUSTMENT_PROCEDURE.md.

CHANGE (v1.21): FYBROC 1500 Pricing series-attribution correction (Vibration/Sound
Testing). The Rev0.4 '1500 Pricing' sheet is authoritative for the 1500 series (every
block stamps Series='1500'); the 5500 Pricing sheet legitimately has its own testing
blocks. The previously published pricing (FYBROC-REV04-MERGE-20260914-V1) was STALE:
VIBRATION_TESTING and SOUND_LEVEL_TESTING existed only under 5500, with the 1500 rows
MISSING (so 1500 vibration/sound resolved to C/F). Root cause: data staleness, not a
code bug — re-running the current compiler produces both 1500:57 + 5500:57 for each
(+114 candidates). FIX: recompile (compile_fybroc_rev04_pricing --all --found-only) +
re-merge (merge_rev04_over_price_estimator) + re-publish a NEW family-safe FYBROC version
FYBROC-REV04-MERGE-20260826-V2 (PriceBookVersionId 9, 56355 rules, supersede-not-delete;
old version retained IsCurrent=0). Verified: VIBRATION_TESTING & SOUND_LEVEL_TESTING now
[1500:57, 5500:57]; live 1500/1x1.5x6 witnessed vibration=\$3045 / sound=\$3045 (were
C/F), matching the sheet (DH-DK, DM-DP: 0/1395/3045); audit_fybroc_pricing extended +12
sheet-derived testing asserts (47/0, sheet read widened to col 126); gate ALL CORRECTIONS
INTACT 9/9; DEAN pricing 9874 UNCHANGED (publisher superseded only FYBROC); imports OK.
Dean phase status UNCHANGED (D140 current; D150 not started). See
docs/evidence/REV04_PRICING/REV04_1500_TESTING_SERIES_FIX_EXIT.md.

CHANGE (v1.20): FYBROC Suction Discharge Taps pricing bridge (V6 'Pump Options -
Horizontal' E3:E4 field -> Rev0.4 '1500 Pricing' CS-CV adder). The selected option
now resolves to the sheet price; unpriced series show C/F. ROOT CAUSE: the runtime
pricing lookup matched the SELECTABLE value ('no suction discharge taps' /
'suction discharge taps') against the PRICING value ('Not_Supplied_by_Fybroc' /
'Supplied_by_Fybroc') with only case/space/underscore normalization -> no match ->
silent C/F, even though the 38 priced rows ($0 / $1041 per 1500 size) existed and
were correct. FIX (src/api/v2_routes.py, runtime-only, no data reload): the pricing
lookup now consults config/runtime_profiles/fybroc_value_equivalences.json (the same
reconciliation the config engine uses) via a module-level _value_equivalence_map +
_EQUIV_FIELD_ALIAS (SUCTION_DISCHARGE_TAPS->SUCTION_DISCHARGE) + prefix-alias handling
for '*'-marked STD values; _price_component tries the raw selection value plus all
equivalence-group members. BONUS: Casing Drains now also resolves via the same bridge
(was silently C/F). Verified: 1500 not-supplied->$0 / supplied->$1041 across sizes;
2530 (no pricing) -> C/F placeholder; audit_fybroc_pricing extended with 8 sheet-derived
suction/discharge asserts (35/0, was 27/0); gate ALL CORRECTIONS INTACT 9/9; FYBROC
56241 / DEAN 9874 pricing rules unchanged (runtime-only, no republish); imports OK.
KNOWN GAP (disclosed): Cyclone Separator stays C/F (its priced label isn't in its
equivalence group - a data reconciliation item). Dean phase status UNCHANGED (D140
current; D150 not started). See
docs/evidence/REV04_PRICING/REV04_SUCTION_DISCHARGE_PRICING_EXIT.md.

CHANGE (v1.19): FYBROC Rev0.4 "1500 Motors" — CPQ Conversion2 motor display
descriptor implemented (motor pricing authority already published; no reload). A
read-only probe of the '1500 Motors' sheet (header row 2, data 3-144002 = 144000
rows, cols B-N incl L=CPQ Conversion2, M=HpRPM, N=Price; only 151 priced, rest C/F)
verified CPQ Conversion2 == "{Motor Enclosure}---{Motor Efficiency}---{Motor
Voltage}---{Motor Hertz}" for ALL 144000 rows (0 mismatches; 18 distinct values) -
a pure function of 4 fields, NOT Hp/RPM/etc. So it is DERIVED at runtime (no 144k
reload). Implemented in src/api/v2_routes.py resolve flow: _CPQ_DISPLAY sheet-cased
token map (enclosure tefc->TEFC/tefc sd->TEFC SD/ieee 841->IEEE 841; efficiency
pe->PE; voltage/hertz passthrough) + _cpq_conversion2(); surfaced as (a) pricing[]
Motor 'cpq_conversion', (b) component_pricing[] Motor 'selection' (so the existing
UI renderPricing shows it), (c) top-level resolve key 'motor_cpq_conversion'
(present even when the motor is C/F). Persisted in quote-line pricing lineage.
DEAN-safe (helper returns None absent the 4 Fybroc motor fields; no DB write, no
publication). New re-runnable guard scripts/audit_fybroc_motor_cpq.py (sheet-derived
expectations across all 18 combos incl TEFC SD/IEEE 841 casing) = 37/0, wired into
run_all_fybroc_audits.py as audit #9. Verified: gate ALL CORRECTIONS INTACT 9/9;
FYBROC pricing 56241 / DEAN 9874 unchanged (runtime-only); imports OK. KNOWN GAP
(disclosed): only 151/144000 motor combos are priced (rest C/F by source); CPQ is
derived not stored (guarded by the sheet-derived audit). Dean phase status UNCHANGED
(D140 current; D150 not started). See
docs/evidence/REV04_PRICING/REV04_1500_MOTORS_CPQ_EXIT.md.

CHANGE (v1.18): FYBROC Rev0.4 "1500 Pricing" authority VERIFIED + base-pump
pricing correction. The Rev0.4 1500 Pricing datasheet is confirmed authoritative
and correctly published: a read-only probe detected all 24 pricing blocks (base
price + VR-1 helper + 22 material/option adder/seal/coupling/baseplate tables)
via the compiler's own row-3-description block detector, reconciled against the
request spec (which had column transcription errors: Baseplate Hardware=BE-BH not
AY-BC; the only Flange Type block=BY-CB; Flush at CI-CL mislabeled). The G-I
"VR-1 Base Price" helper is byte-redundant with the main table's VR-1 (Standard)
rows and correctly not double-published. Data already lived in the current
publication FYBROC-REV04-MERGE-20260914-V1 (56241 rules); NO republish. CORRECTION
(runtime): src/api/v2_routes.py base-pump material matching aliased a plain 'vr-1'
selection onto the pricier VR-1A row (broad '%vr-1%' pattern tried first),
over-pricing every VR-1 pump (e.g. 1x1.5x6 returned 8666 instead of 4987). Fixed
with exact per-material anchored patterns (vr-1->'vr-1 (standard)', vr-1a->'vr-1a',
vr-1v->'vr-1v', ey-2, *bpo/dma exact; plain vr-1 fallback '%vr-1 (%' never bare
'%vr-1%'). Published DB rows were already correct; DEAN unaffected (own family
branch). New re-runnable guard scripts/audit_fybroc_pricing.py (expectations
derived from the sheet, not hardcoded) = 27/0 across 4 sizes x 6 materials + adders,
wired into run_all_fybroc_audits.py as audit #8. Verified: gate ALL CORRECTIONS
INTACT 8/8 (quote audit now shows 1500 unit=4987, was 8666 pre-fix); FYBROC pricing
rules 56241 and DEAN 9874 unchanged (runtime-only fix, no republish); imports OK.
KNOWN GAP (disclosed): adders don't gate pricing status (found/partial keyed on
base+seal only); SEAL often C/F for horizontal; only base+Shaft/Gland/Flange
adders cross-checked vs sheet so far. Dean phase status UNCHANGED (D140 current;
D150 not started). See docs/evidence/REV04_PRICING/REV04_1500_PRICING_EXIT.md.

CHANGE (v1.17): FYBROC Rev0.4 Motor Constraints authority + enforcement VERIFIED
(no code/data change needed). The Rev0.4 `Motor Constraints` datasheet is
confirmed authoritative and correctly enforced: the extractor
(compile_fybroc_motor_constraint_model.py) reproduces the real sheet layout
exactly — 19 blocks, per-series start columns from the row-2 banners
(1500/1600=B, 1530/1630=T, 2530=AH, 3000=AV, 5500=BJ, 5530=BX), each mini-table
3 cols (Dim1, Dim2, Allowed?) with dynamic row extents — totalling 3278 rows,
byte-identical to what is already in cfg.MotorConstraint (FYBROC=3278, DEAN=0,
active pub). Value semantics are pure ALLOW-LIST (each Allowed? column is a single
token — 'Allowed' or 'X' — with no deny rows; present row = allowed), and the
runtime index-builder + _apply_constraints enforce it as such. Two transcription
errors in the request spec were reconciled AGAINST the sheet (code was already
correct): 3000 is at AV not AH (AH–AR is 2530), and 1500/1600 Alt×HpRpm has an
Allowed? column at H (F–H, 3 cols). Verified: extractor re-run = byte-identical
model; audit_motor_constraints 91/0; 5530 targeted probe 0 leaks + walk complete;
run_all_fybroc_audits ALL CORRECTIONS INTACT 7/7; Dean isolated (Feasible 256, SFO
48063, MotorConstraint 0 unchanged); Fybroc MotorConstraint 3278 / FeasibleConstraint
4487 unchanged; imports OK. KNOWN GAP (disclosed, pending engineering): the
F_MotorHpRpm×F_Motor Type block (1500/1600, 170 rows) is loaded but INERT — the
configurator has no single MOTOR_TYPE field (motor type is decomposed), so that
allow-list is stored but not enforced. Standing audit does not yet sweep 5530
(verified this slice by targeted probe; recommend adding to SERIES list). Dean
phase status UNCHANGED (D140 current; D150 not started). This CHANGE also carries
the previously-unpushed effort-mode steering commit (e117b1d) to both remotes.
See docs/evidence/REV04_CONSTRAINTS/REV04_MOTOR_CONSTRAINTS_EXIT.md.

CHANGE (v1.16): FYBROC Rev0.4 29-ConstraintTable conformance verified + one
correction. Confirmed against the authoritative spec that all 29 ConstraintTables
in the Rev0.4 Feasible Constraints sheet are extracted, loaded into
cfg.FeasibleConstraint (family-scoped), and ENFORCED per their fields + allow-vs-
not-allowed semantics (deny tables prune; allow-list tables restrict target to
the listed set within the governed domain; 3-leg CT21 Alt Size×Pump Material×
Length; blank Allowed? = allowed for the real CT21/25/26 escape-hatch combos;
ConstraintFieldMap covers all 28 field labels). ONE gap found + fixed: CT24
(Tailpipe Option × Tailpipe Length) left TAILPIPE_LENGTH fully selectable when
TAILPIPE_OPTION='not supplied by fybroc' (no allowed length rows for that
context). Fix: TAILPIPE_LENGTH is now conditionally NOT-APPLICABLE unless
TAILPIPE_OPTION='supplied by fybroc' (src/api/v2_routes.py _applicable_fields,
mirroring the WETTED_HARDWARE_SELECTION gate; Fybroc-only, Dean has no
TAILPIPE_OPTION). audit_feasible_constraints.py extended to 44/44 with per-table
coverage + CT24 applicability + CT21 3-leg asserts (no prior assert weakened).
Verified: run_all_fybroc_audits ALL CORRECTIONS INTACT 7/7; Fybroc/Dean row
counts unchanged (enforcement-code-only change, no data reload); Dean isolated.
Dean phase status UNCHANGED (D140 current; D150 not started). See
docs/evidence/REV04_CONSTRAINTS/REV04_29_TABLES_CONFORMANCE.md.

CHANGE (v1.15): FYBROC constraint/config authority moved to
`Fybroc Configuration Rev0.4.xlsx` (supersedes Rev0.3). A full workbook-wide
cell-level diff proved the enforced constraint/config content is BYTE-IDENTICAL
between Rev0.3 and Rev0.4 (Constraints combination matrix, all 29 Feasible
ConstraintTables incl. CT24 Tailpipe Option×Length, Constraint Index, Motor
Constraints, Hierarchy, and the Selections X/STD grid rows 2-678). Rev0.4's real
differences are pricing (already adopted via price publication
FYBROC-REV04-MERGE-20260914-V1), notes, added pricing/motor/UI sheets, and a
Combine-Variables column reshuffle + a MotorType header rename - all handled so
the loaded data is unchanged. The constraint/selections/motor compilers were
repointed to Rev0.4 (compile_fybroc_motor_constraint_model.py made revision-robust
via header-name resolution for the MotorHpRpm mapping + a canonical MotorType
domain name); the regression guard (audit_selections_vs_db.py,
audit_feasible_constraints.py) now cites Rev0.4 with NO asserts weakened. Two
loaders were HARDENED family-safe (load_constraints_to_sql.py and load_all_series.py
previously had un-scoped DELETEs that would have wiped Dean's shared-table rows);
both now delete/insert scoped to PumpFamilyId=FYBROC with isolation assertions.
Publication: cfg.MetadataPublication is shared+not-family-scoped and the content
is identical, so NO new config publication was minted (would disrupt Dean for zero
change); the active publication's Description was annotated with the Rev0.4
authority (scripts/annotate_rev04_config_authority.py). Verified: run_all_fybroc_audits
ALL CORRECTIONS INTACT 7/7; Fybroc row counts unchanged (FeasibleConstraint 4487,
SFO 3638, CombineVariable 112, MotorConstraint 3278); Dean fully isolated
(Feasible 256, SFO 48063 unchanged). Also fixed (separate, same session): the
configuration-dictionary API endpoint leaked the other family's series (missing
PumpFamilyId filter). Dean phase status UNCHANGED (D140 remains the current
milestone; D150 not started). See docs/evidence/REV04_CONSTRAINTS/REV04_CONSTRAINT_SUPERSESSION.md.

CHANGE (v1.14): D140 (Dean Excel Oracle) complete, AND the Dean identifier
numbering + config were RE-BASED onto the new authoritative workbook
PumpConfiguration_Logic_0.1.xlsm (engineering delivered mid-D140; it supersedes
ALL prior Dean constraint/config/numbering sources except seal). The identifier
loader (scripts/load_dean_identifier_to_sql.py) now reads each PN segment's own
numbering sheet by header-search (Permutation..Alphanumeric Code) with literal
zero-padded codes; A#->D# identity from Pump Constraints A/B/C (206 model refs);
one DEAN batch of 106,892 segment rows (WET_END 49,987, POWER_FRAME 55,452,
BASEPLATE 1,153, FLUSH_PLAN 185 [now table-backed], IMPELLER 24, MOTOR_FRAME 91);
the old 428,742-row DEAN batch was removed. The resolver (src/api/dean_identifier.py)
was re-based to the v0.1 field orders, made flush + motor-frame table-backed,
removed the (now-absent) N/A collapse, and emits fixed placeholders for
retained-but-unbuilt segments (Barrier/Cooling/Testing/Documentation/Additional/
Motor-main) so the PN never errors. The SQL @FamilyCode='DEAN' CONCAT branch is
unchanged (width-agnostic). D140 oracle = an Excel COM numbering-table reader
(scripts/dean_excel_oracle.py DeanNumberingOracle) that reads segment codes LIVE
from the workbook and proves SQL/API == workbook (scripts/dean_oracle_compare.py:
15/15 comparable segments matched, 0 failed). Verified: audit_dean_identifier 8/8,
audit_dean_config 28/28, audit_dean_pricing 22/22, run_all_fybroc_audits ALL
CORRECTIONS INTACT 7/7, Fybroc/shared row counts unchanged (isolation). Disclosed
gaps: A1 seal (omitted-not-discarded; 519 seal codependencies skipped pending a
Codependencies<->Pump-Constraints seal-vocab crosswalk), A2 external Standard Confs
(wet_end/power_frame '?' on the STD-gap models only), F1 Cooling empty, F2 Barrier
un-built, F3 Motor main code inert. See docs/evidence/D140/DEAN_D140_EXIT.md.

CHANGE (v1.13): D130 (SQL Dean Identifier Authority) complete. SQL now generates
the Dean Part Number via an ADDITIVE @FamilyCode='DEAN' branch in
cfg.usp_AssembleConfiguredProduct (Fybroc branch byte-for-byte unchanged). Dean
A#->D# identity (204 rows in cfg.PumpModelReference) and the engineering segment
String->code maps (428,742 rows in stg.SegmentCombinationImport, DEAN batch) were
loaded family-scoped by reusing the existing Fybroc identifier infra (NO new
table, NO schema migration); the API resolves each segment code and SQL assembles
the authoritative PN + PN-derived SKU. Verified: audit_dean_identifier 8/8 (SQL==
python parity, SKU 1:1, A#->D#, determinism, segment discipline), audit_dean_pricing
22/22, audit_dean_config 29/29, run_all_fybroc_audits ALL CORRECTIONS INTACT 7/7,
Fybroc row counts unchanged (isolation). Dean PN excludes the seal segment (seal
code authored only in the external Seal Numbering.accdb, unavailable). Disclosed
gaps: some models' D110 STD carries option values the numbering table never
enumerated (authoritative STD "Standard Confs" lives in an external Access DB we
don't have), so those resolve every segment except a wet-end/power field; motor
frame gated 00 and motor options inert. See docs/evidence/D130/DEAN_D130_EXIT.md.

CHANGE (v1.12): D120 (Dean Pricing & Adders) complete. The authoritative Dean
Pricing Matrix is published to SQL for the DEAN family (DEAN_STANDARD version
DEAN-MATRIX-20260826-V1, 9874 rules: base pump, option adders, couplings,
baseplates, shaft config) reusing the existing pricing pipeline (no schema
migration; PriceBook.PumpFamilyId already family-scopes). A configured Dean pump
resolves to base + Σ|option adder| + coupling + baseplate + shaft, with baseplate
keyed by Type(Economy=Formed)+Drip Pan (lugs descriptive), quote math
List×(1−Discount)×Qty, and motor/seal honest C/F (not in the Matrix). The Dean
Data Sheet Rev 2 macros+formulas were adopted as authoritative over all Dean
configuration (docs/evidence/D100/DEAN_DATASHEET_VBA_LOGIC.md); this added a
Pump-Configuration applicability gate (Baseplate/Coupling/Motor presence) to the
config model — Dean-only, Fybroc unaffected. Verified: scripts/audit_dean_pricing.py
22/22, scripts/audit_dean_config.py 29/29, Fybroc gate ALL CORRECTIONS INTACT 7/7,
Fybroc pricing + config rows unchanged. Only gaps: motor/seal C/F + one flagged
Matrix source anomaly (RTA3146 326TS). See docs/evidence/D120/DEAN_D120_EXIT.md.

CHANGE (v1.11): D110 option applicability corrected to be size-aware and
STD/X-driven. Engineering flagged that most Dean configurations carry STD
(standard) / X (available) markers, which the first D110 load ignored (it offered
every option to every series with no standard default). The markers live on the
PumpConfiguration_Logic 'Pump Options' sheet (per model = series+size), and
applicability varies by size in 27/37 series. Fix: added a nullable SizeCode to
cfg.SeriesFieldOption (Fybroc rows NULL, unaffected), rebuilt the loader from
'Pump Options' (48,910 rows, 11,767 STD defaults), scoped the API option reads by
size, and rewrote the Dean audit (29/29: STD seed, per-size applicability, size
differentiation, fail-closed, quad, no dead ends). Also fixed SEAL_TYPE value
vocabulary (short 'Type N' to match the constraints) and loaded the real 10-value
BARRIER_PLAN domain. Fybroc gate ALL CORRECTIONS INTACT 7/7, Fybroc rows
unchanged. See docs/evidence/D110/DEAN_D110_EXIT.md §0.

CHANGE (v1.10): D100 and D110 marked complete against their exit gates.
- D100 (Dean source reconciliation): 5 workbooks classified;
  PumpConfiguration_Logic confirmed as codependency/option-domain authority
  (docs/evidence/D100/DEAN_D100_EXIT.md).
- D110 (Dean configuration completion): the authoritative model is published to
  SQL for the DEAN family (family 1) by reusing the Fybroc constraint tables made
  family-aware (PumpFamilyId on FeasibleConstraint + ConstraintFieldMap; composite
  ConstraintFieldMap PK; Option4 columns for the 4-leg Seal Option × Gland Type ×
  Flush Plan × Barrier Plan quad). Loaded: 46 field-map, 19,425 SeriesFieldOption
  (incl. a synthesized BARRIER_PLAN domain), 721 feasible-constraint rows.
  Verified: scripts/audit_dean_config.py 45/45 (options project, valid pass,
  invalid fail-closed, quad wired, no dead ends) and the Fybroc regression gate
  ALL CORRECTIONS INTACT 7/7 with Fybroc row counts unchanged (no regression).
  Only gap: 5 pending-engineering value tuples (Throttle Bushing "Required";
  Bearing Frame Cooling "NONE"), excluded and logged. See
  docs/evidence/D110/DEAN_D110_EXIT.md.

CHANGE (v1.9): F150-F170 verified against their own exit gates and marked
complete (they were "needs re-verification" under v1.8). Evidence:
- F150 SQL identifier authority: resolve is SQL-authoritative for PN/SKU/
  signature/reuse; Python parity oracle agrees (audit_identifier_parity 44/44).
- F160 Excel oracle: scripts/fybroc_oracle_compare.py 6/6 (Excel == API).
- F170 exhaustive regression: docs/evidence/F170/FYBROC_EXHAUSTIVE_REGRESSION.md
  — correction gate ALL CORRECTIONS INTACT (selections clean, feasible 14/14,
  motor 91/91, identifier 44/44, BOM 38/38, quote 22/22, free-config 32/32),
  oracle 6/6, and a 10-series free-edit batch with 0 errors (1,466 resolve-state
  + 1,466 resolve/pricing calls). Stale F170 0/10 Excel-COM artifacts removed.
The prior stale F180 signoff (2026-08-24) was regenerated with current
publication facts.

Current Objective (F180):
Freeze a production-grade Fybroc engineering publication: approved metadata
publication (id=2 F140-corrections-v1), approved pricing publication (id=7
FYBROC-REV04-MERGE-20260914-V1), regression package, source lineage, known
limitations, and engineering signoff.

Current Exit Gate (F180):
Fybroc declared configuration-complete with engineering signature on
docs/evidence/F180/FYBROC_SIGNOFF.md.

Next Permitted Milestone:
D150 — Exhaustive Dean Regression (D100–D140 complete; D140 re-based onto
PumpConfiguration_Logic_0.1.xlsm, see §12 CHANGE v1.14). Dean work proceeds in
parallel with awaiting the F180 signature, since Dean is net-new work that does
not modify frozen Fybroc data. Do NOT start D150 without explicit go-ahead.

Deployment note (parallel to roadmap, NOT milestone T110):
A PREVIEW test environment is live for engineering feedback — static UI on Vercel,
FastAPI backend on Render (Docker + ODBC 18), reaching the local SQL Server via an
ngrok TCP tunnel. This is a feedback surface for the current work, not the roadmap's
central Azure TEST environment (T110). See external_testing/ and
docs/evidence/DEPLOYMENT_MILESTONE.md. The environment-aware UI (ui/config.js) lets
the same build serve local testing (localhost) and engineering (Vercel/Render)
simultaneously.

F140 completion (2026-08-28) — what was actually fixed:
- Feasible Constraints were LOADED but NEVER ENFORCED (missing cfg.ConstraintFieldMap).
  Created + seeded the map (28); rewrote enforcement to handle NOT-ALLOWED,
  ALLOW-LIST, and MIXED tables (bidirectional, triples, series scope, exact match).
- Motor Constraints: only Alt_Size->Frame_Size was enforced; wired in Alt_Size->HP,
  Alt_Size+HP->RPM, and Frame<->HpRpm (bulk audit 91/91 across 7 series).
- Fixed testing part-number segment, V6 Motor Assy extraction, Combine Variables
  fabricated pairs, ConstraintTable21 triple loader, ALT_SIZE/IMPELLER_TRIM ordering.
- DB reflects all: cfg.ConstraintFieldMap=28, cfg.FeasibleConstraint=4487 (29 tables),
  cfg.MotorConstraint=3278. Re-runnable audits: scripts/audit_selections_vs_db.py,
  scripts/audit_motor_constraints.py.

Active work:
- Awaiting engineering UAT feedback on the deployed preview environment.
- F140 deferred items (see F140 exit record): allow-list "unmentioned context"
  semantics for conditional tables; MotorHpRpm->MotorType (assembly-stage, not a
  dropdown filter); series 6000/7530 (no config data); 7500/8500 (no pricing).

Key Technical State:
- FastAPI V2: 4 endpoints (dictionary, evaluate, validate, resolve)
- In-memory cache: 5-min TTL, keyed on (family, publication_id)
- Constraint enforcement: 4,440 FeasibleConstraint rules
- Pricing: Price Estimator-Fybroc.xlsm is AUTHORITATIVE
- SKU format: F<Series>-<8char><VersionLetter> (same for Dean with D prefix)
- Part Number: Unified segment sequence for both families
- Progressive UI: Fields locked until preceding hierarchy fields are selected

F130 Key Findings (preserved):
- 1500 base prices: 109 MATCH, 0 MISMATCH between Rev0.3 and Price Estimator
- Price Estimator has 19 additional prices (VR-1V, VR-1V BPO/DMA materials)
- Rev0.3 pricing is a faithful subset of Price Estimator - no conflicts
- Price Estimator is AUTHORITATIVE for all 33 production pricing rules
- Adders: 14 sections, 98 lines covering hardware, flush, bearings, elastomers, misc
- Components: Coupling (13 groups x 37 frames), Baseplate (85 rows x frames), Motor (13 blocks)

Known limitations carried forward:
- Vertical motor_assy: some SFO values don't match MOTOR_ASSEMBLY combo table (data gap, not architecture)
- Seal_assy: some horizontal combinations don't match SEAL_ASSEMBLY combo table (data gap)
- Series 6000 + 7530: require engineering to define configuration options
- Series 8500: config works but no pricing rules exist


13. Roadmap Change Control

This roadmap may change only when a genuine project requirement requires it.

When changed:

increment roadmap version
document the reason
preserve completed milestone history
identify impact on current milestone
identify reordered/new/deprecated milestones
commit the roadmap change separately when practical

Do not silently redefine milestone objectives while implementing them.



# 14. Completion Definition

The project is complete only when:

Fybroc configuration passes
Dean configuration passes
all authoritative workbook constraints are reconciled
SQL Part Number generation is authoritative
SQL SKU generation is authoritative
pricing/adders are reconciled
Excel regression parity passes
React parity passes
reusable BOM passes
quote persistence/output passes
Entra security passes
Telford UAT passes
Indianapolis UAT passes
production deployment is live
monitoring is operational
recovery is proven
documentation is complete
final regression suite is green
final production release is tagged

End of Pump Configurator Master Roadmap v1.0






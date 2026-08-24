# Pump Configurator Master Roadmap

**Roadmap Version:** 1.6  
**Roadmap Date:** 2026-08-24  
**Project:** Dean + Fybroc Pump Configurator  
**Status:** ACTIVE  
**Current Milestone:** U100 — Canonical Product Model  

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
- Every configured engineering result must retain source/version lineage.



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
F140	Fybroc metadata corrections	COMPLETE
F150	SQL Fybroc identifier	COMPLETE
F160	Fybroc Excel Oracle	COMPLETE
F170	Fybroc exhaustive regression	COMPLETE
F180	Fybroc signoff	COMPLETE
D100	Dean source reconciliation	COMPLETE
D110	Dean configuration completion	COMPLETE
D120	Dean pricing/adders	COMPLETE
D130	SQL Dean identifier	COMPLETE
D140	Dean Excel Oracle	COMPLETE
D150	Dean exhaustive regression	COMPLETE
D160	Dean signoff	COMPLETE
U100	canonical product model	COMPLETE
U110	unified configuration dictionary	COMPLETE
U120	FastAPI V2	COMPLETE
U130	reusable BOM	COMPLETE
U140	quote engine	COMPLETE
U150	Excel V2	PENDING
U160	React UI	PENDING
U170	security/audit	PENDING
T100	CI/CD	PENDING
T110	Azure TEST	PENDING
T120	Telford UAT	PENDING
T130	Indianapolis UAT	PENDING
T140	cross-family UAT	PENDING
T150	UAT corrections	PENDING
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
Version:            1.2

Current Phase:      U — Unified Application
Current Milestone:  U150
Status:             READY TO START

Current Objective:
Replace slow chained V1 Excel navigation with single-request V2 evaluate flow.

Current Exit Gate:
Excel configuration interaction meets agreed responsiveness target.

Next Permitted Milestone:
U160 — React Configurator

Completed (2026-08-24):
U100    Canonical product model             COMPLETE
U110    Unified configuration dictionary    COMPLETE (55 fields, 266 codes)
U120    FastAPI V2 with caching             COMPLETE (4 endpoints, TTL cache)
U130    Reusable BOM engine                 COMPLETE (BOMHeader+BOMLine+reuse+GetBOMBySKU)
U140    Quote engine                        COMPLETE (QuoteLine with SKU/PN/pricing lineage)

F130 Key Findings:
- 1500 base prices: 109 MATCH, 0 MISMATCH between Rev0.3 and Price Estimator
- Price Estimator has 19 additional prices (VR-1V, VR-1V BPO/DMA materials)
- Rev0.3 pricing is a faithful subset of Price Estimator - no conflicts
- 5500: Rev0.3 has 52,440 rows (19 sizes x 19 settings x 2 materials)
        PE has 72 rows (19 sizes x 4 settings) - both use Setting granularity
- Price Estimator is AUTHORITATIVE for all 33 production pricing rules
- 55/55 pricing index rules classified (33 PE, rest engineering notes/review items)
- Adders: 14 sections, 98 lines covering hardware, flush, bearings, elastomers, misc
- Components: Coupling (13 groups x 37 frames), Baseplate (85 rows x frames), Motor (13 blocks)

F130 Gaps Carried Forward to F140:
- PE has VR-1V + VR-1V BPO/DMA pricing that current SQL metadata may not support
- 5500 Setting-level pricing: Rev0.3 has 19 settings vs PE's 4 settings (PE may be incomplete for 5500)
- Flexaseal seal pricing: not yet in production pricebook (NEEDS_ENGINEERING_REVIEW)
- Hydrotest certificate: ambiguous - certificate vs test pricing unclear
- Paint Upgrade, Shaft Grounding, Testing: noted as "not in pricebook" by engineering

Deferred:
SQL identifier work             -> F150
Dean implementation             -> after F180
Canonical unified model         -> U100
BOM                             -> U130
Quote engine                    -> U140
Excel V2                        -> U150
React                           -> U160
Azure shared testing            -> T110
Production                      -> P140+


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






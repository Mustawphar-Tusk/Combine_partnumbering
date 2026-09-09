# Resume Point — 2026-08-27
# Resume Point — 2026-08-28

## Current State

**F140 (Fybroc Metadata Corrections) EXITED.** Constraint enforcement is now
genuinely working — this was the real gap (constraints were loaded but not
enforced). Next milestone: **F150 — SQL Fybroc Identifier Authority**. Currently
awaiting engineering UAT feedback on the deployed preview environment.

- F140 exit record: docs/evidence/F140/FYBROC_F140_EXIT.md
- Roadmap corrected to v1.8 (see docs/Project_master_roadmap.md §12): the prior
  checkpoint over-reported completion (T110, F/D/U all "COMPLETE"); true position
  was F140. Dean phase (D100-D160) is NOT built to Fybroc parity — NOT STARTED.

### F140 completion (2026-08-28)
- Feasible Constraints: were loaded but NEVER enforced (missing cfg.ConstraintFieldMap).
  Created+seeded the map (28); rewrote enforcement for NOT-ALLOWED / ALLOW-LIST /
  MIXED tables (bidirectional, triples, series scope, exact match). Fail-closed
  verified (6x8x13->no Non Sparking; 2x3x13->no DIN/ISO; 5500->no Internal Flush;
  VR-1V->no Casing Drains Supplied). ConstraintTable4 allow-list restricts Impeller
  Trim to per-size valid set.
- Motor Constraints: only Alt_Size->Frame was enforced; wired in Alt_Size->HP,
  Alt_Size+HP->RPM, Frame<->HpRpm. Bulk audit 91/91 across 7 series.
- Ordering: ALT_SIZE + IMPELLER_TRIM ascending numeric/dimensional.
- DB reflects all: cfg.ConstraintFieldMap=28, cfg.FeasibleConstraint=4487 (29 tables),
  cfg.MotorConstraint=3278. Audits: scripts/audit_selections_vs_db.py,
  scripts/audit_motor_constraints.py.
- Deferred (to UAT feedback): allow-list "unmentioned context" semantics for
  conditional tables; MotorHpRpm->MotorType (assembly-stage, not a filter);
  series 6000/7530 (no config); 7500/8500 (no pricing).

## Preview deployment (test surface, NOT roadmap T110)

**Live test environment deployed and verified end-to-end.** The configurator is
shareable via a Vercel URL, backed by a FastAPI service on Render (Docker +
ODBC Driver 18), connecting to the local SQL Server through an ngrok TCP tunnel.
Full chain verified: series list, constrained evaluate, and part-number resolve.
Environment-aware ui/config.js serves local testing (localhost) and engineering
(Vercel/Render) from the same build simultaneously.

- UI (Vercel):  https://combine-partnumbering-claude.vercel.app
- API (Render): https://pump-configurator-api.onrender.com
- Repo:         github.com/Mustawphar-Tusk/Combine_partnumbering_Claude
- Details:      docs/evidence/DEPLOYMENT_MILESTONE.md ; setup: external_testing/DEPLOYMENT.md (index: external_testing/README.md)

To run: SQL Server up + `ngrok tcp 1433` + Render `DB_SERVER` matching the current
ngrok host,port (free-tier address rotates each restart — see DEPLOYMENT.md).
The URL only works while these are live (coordinated test window, not 24/7). For
unattended access, move the DB to Azure SQL (removes ngrok + local-PC dependency).

## Deployment session (2026-08-27) — What Was Done

- Created deployment artifacts: `Dockerfile`, `.dockerignore`, `render.yaml`,
  `vercel.json`, `ui/config.js` (window.API_BASE), `DEPLOYMENT.md`.
- Parameterized the UI API base so the Vercel UI calls the Render API cross-origin
  (default `""` keeps local same-origin dev working).
- Bring-up fixes: guarded `pywin32` for Linux build; fixed Vercel root 404 (redirect
  to /configurator.html); per-request DB latency (one connection + 60s publication
  cache instead of two connections per request).
- Machine prep: confirmed SQL Server TCP/IP + mixed-mode auth; created
  least-privilege login `configurator_test`; registered ngrok authtoken.
- Pushed all work to the `Combine_partnumbering_Claude` repo (through commit for the
  ngrok restart docs).

## Prior State (feature work — still current)

**All 10 Fybroc series fully resolve Part Numbers at 100%.** Pricing hits 100% for 8 of 10 series (7500 and 8500 lack pricing rules in the Pricebook — engineering decision needed). Motor assembly, seal assembly, pump options, and all other segments resolved. Bulk testing confirms. Recent feature work also fixed the testing part-number segment, corrected the V6 Motor Assy 5-region extraction, added the Wetted Hardware conditional skip and ALT_SIZE ascending sort, and audited constraints (blank=not-allowed, V6 flange authority) — see docs/evidence/F120/FYBROC_CONSTRAINT_EXTRACTION_ALIGNMENT.md.

## What's Working

- ✅ All 10 Fybroc series: 100% Part Number resolution (automated bulk test confirmed)
- ✅ Pricing: 100% for series 1500, 1530, 1600, 1630, 2530, 3000, 5530
- ✅ Pricing: 90% for 5500 (some vertical setting/size combos outside pricebook)
- ✅ Motor Assembly: multi-field progressive matching (702-row table, all combos resolve)
- ✅ Seal Assembly: multi-field matching + noseal defaults for series without seals
- ✅ Vertical pump_options: dedicated field mapping (23K-row table)
- ✅ Constraint enforcement (4,440 rules from 20 feasible tables)
- ✅ Progressive hierarchy enforcement in UI
- ✅ SKU generation: `F<Series>-<8char><VersionLetter>` format
- ✅ Configuration signature (SHA-256) + reuse detection
- ✅ Material pricing synonym resolution (vr-1a → VR-1 Standard, etc.)
- ✅ Bulk test harness: `scripts/test_series_bulk.py`

## Known Remaining Items

1. **7500 pricing** — Only 1 pricing rule in Pricebook. Most sizes don't match. Engineering decision needed.
2. **8500 pricing** — Zero pricing rules exist. CONFIG ONLY status until engineering provides pricing.
3. **5500 pricing (10% gap)** — Some vertical setting/size combos are outside the 72 pricing rules in Pricebook.
4. **6000 + 7530** — No configuration data exists in Rev0.3 (engineering decision needed — are these active production series?).
5. **2630** — Appears in Pricebook but not in V6 or Rev0.3. Legacy or active? Engineering decision needed.

## Today's Session (2026-08-25) — What Was Fixed

1. **Motor Assembly** — Was failing 100% for all series. Root cause: only searching by MOTOR_OPTION (matching 550/702 rows randomly). Fix: multi-field progressive matching using all motor fields (HP, RPM, voltage, hertz, frame, enclosure, efficiency, manufacturer) with progressive fallback.
2. **Seal Assembly** — Was failing 10-20%. Fix: multi-field matching using all 5 seal fields. Added noseal defaults for series without seal configuration (e.g., 2530).
3. **Vertical pump_options** — Was failing 45% for 5500. Root cause: using horizontal field names for vertical combo table. Fix: dedicated vertical field mapping (WETTED_HARDWARE, FLUSH_OPTIONS, VAPOR_PROTECTION, STRAINER).
4. **No-fields defaults** — Series with minimal configuration (7500, 8500) now get sensible defaults instead of `???`.
5. **Pricing material matching** — Was failing 10-20% for 1500/1600/1630. Root cause: SFO `"vr-1a"` didn't LIKE-match pricing `"VR-1 (Standard)"`. Fix: multi-pattern matching with synonyms.

## Architecture

```
UI (progressive hierarchy, authoritative field order)
  → POST /evaluate (returns constrained allowable options per remaining field)
  → POST /resolve (generates PN + SKU + pricing)
      → Primary segment: fn_LookupIdentifierCode (AttributeValue table)
      → Composite segments: LIKE search on re-indexed SelectionsJson (direct SFO values)
      → Pricing: price.PriceRule LIKE search by series + size + material
      → Testing: TESTING combo table (60 rows, 'testing'→'test' normalization)
      → Motor Mods: VocabularyMap MOTOR_MOD codes (31 entries)
      → Constraints: cfg.FeasibleConstraint (4,440 rules)
```

## Key Design Decisions

| Decision | Outcome |
|----------|---------|
| SKU Format | `F<Series>-<8char><VersionLetter>` (A=v1, B=v2) |
| Part Number authority | SQL Server (fn_LookupIdentifierCode + combo tables) |
| Caching | In-memory, 5-min TTL, keyed on `(family, publication_id)` |
| Client agnostic | Same endpoint serves Excel VBA and React identically |
| Pricing authority | Price Estimator-Fybroc.xlsm (NOT Rev0.3) |
| Constraint source | Rev0.3 FeasibleConstraint + ConstraintTable3/6 (5500-only) |
| Progressive UI | Fields locked until all preceding hierarchy fields are selected |
| Vertical seal | Segment omitted from Part Number (vertical pumps have no seal assembly) |

## How to Run

```powershell
cd "c:\Users\makorede\Downloads\Combine_partnumbering - Claude"
.venv\Scripts\python.exe -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
```

Open: http://localhost:8000/ui/configurator.html

## Database

- **Server:** localhost
- **Database:** PumpConfiguratorDB
- **Auth:** Windows Authentication (Trusted_Connection)
- **Key schemas:** `cfg` (configuration), `price` (pricing), `dbo` (core)

## Git

- **Branch:** `feature/m021-shared-excel-production-hardening`
- **Tags:** `f180-fybroc-complete`, `d160-dean-complete`, `u170-unified-complete`

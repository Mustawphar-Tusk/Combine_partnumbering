# F140 — Fybroc Metadata Corrections & Publication — EXIT RECORD

Date: 2026-08-28
Milestone: F140 (Fybroc Metadata Corrections & Publication)
Decision: **EXIT — passed** (with documented deferred items; see section 5)

---

## 1. Objective (from roadmap)

Correct the Fybroc configuration metadata based on F100–F130 findings and make it
enforce correctly at runtime, for the supported series: 1500, 1530, 1600, 1630,
2530, 3000, 5500.

Exit gate, per series:
1. valid options project correctly
2. invalid options fail closed
3. dependency transitions work
4. no unexplained empty-option state exists

## 2. Why F140 was reopened

The roadmap table had marked F140–F180 complete, but hands-on testing (ours and
engineering's on the deployed preview) showed constraint enforcement was not
actually working. Per governance ("failed exit gates keep the project in the
same milestone"), the true position was F140. This record documents closing it.

## 3. Corrections implemented this cycle

Extraction / data:
- Combine Variables: removed fabricated MotorMfg->MotorOption and
  WettedHardware->ShaftMaterial "relationships" (they are independent value
  domains, not paired mappings); reclassified as value domains.
- V6 Testing: fixed the testing part-number segment (was stuck at "00"); the
  4-attribute combination now resolves to the correct base-36 hex.
- V6 Motor Assy: corrected the 5-region extraction (option domains incl. "-",
  Hertz->Voltage, Hertz->RPM, Frame+Hp+RPM->hex, combination->hex); prior
  version truncated domains.
- Feasible Constraints loader: fixed the ConstraintTable21 triple-table
  column-shift; field labels/values now derived from headers. Reloaded
  cfg.FeasibleConstraint = 4487 rows / 29 tables.

Runtime enforcement (evaluate endpoint, cfg.* as authority):
- Feasible Constraints: were LOADED but NEVER ENFORCED (the enforcement loop
  depended on cfg.ConstraintFieldMap, which did not exist). Created + seeded
  cfg.ConstraintFieldMap (28 label<->FieldCode mappings), then rewrote
  enforcement to handle all three table shapes data-driven:
    * NOT-ALLOWED tables -> remove listed combinations
    * ALLOW-LIST tables  -> keep only listed values for the context
    * MIXED tables        -> keep Allowed minus Not-Allowed
  Bidirectional (where hierarchy allows), triple-constraint (CT21), exact
  case-insensitive matching, SeriesApplicability scoping (e.g. 5500_ONLY).
- Motor Constraints: only Alt_Size->Frame_Size was enforced; wired in the rest:
    * Alt_Size -> MOTOR_HP (decompose F_MotorHpRpm composite)
    * Alt_Size + MOTOR_HP -> MOTOR_RPM
    * Frame_Size <-> F_MotorHpRpm
  Hardened series-scope matching for grouped scopes ("1500 and 1600").
- Wetted Hardware Selection conditional skip; ALT_SIZE and IMPELLER_TRIM
  ascending numeric/dimensional ordering; STD defaults; V6 flange authority;
  hierarchy gating + reset-on-upstream-change.

## 4. Verification / evidence

- Feasible-constraint fail-closed (hierarchy-aware): 6x8x13 blocks Non Sparking
  coupling guard; 2x3x13 blocks DIN/ISO flange; 5500 6x8x13 blocks Internal
  Flush; VR-1V blocks Casing Drains Supplied; small size still allows Non
  Sparking. Valid walks for 1500/1530/2530/5500 complete with no stalls.
- ConstraintTable4 allow-list: Alt Size 1x1.5x6 restricts Impeller Trim to its
  19 valid trims (from 97), ascending numeric order.
- Motor Constraints bulk audit (scripts/audit_motor_constraints.py): 91/91
  across 7 series — MOTOR_HP / MOTOR_RPM / FRAME_SIZE options are faithful
  subsets of the workbook allow-lists (no illegal leaks), and all 7 series
  complete a full valid walk (no over-blocking).
- DB reflects implementations: cfg.ConstraintFieldMap=28, cfg.FeasibleConstraint
  =4487 (29 tables; CT21 Option3='Length' 3477), cfg.MotorConstraint=3278
  (4 dimension pairs).
- Deployed to Render (backend) + Vercel (UI), verified end-to-end through the
  ngrok tunnel to the live DB.

Re-runnable audits: scripts/audit_selections_vs_db.py,
scripts/audit_motor_constraints.py.

## 5. Deferred / known items (carried into UAT feedback)

These do not block exit but are recorded honestly:
1. Allow-list "unmentioned context" semantics: for conditional-style allow-list
   tables (e.g. Tailpipe Option x Tailpipe Length, Setting/Length x Length /
   Setting) the intended behavior when the controlling value has NO rows
   (e.g. Tailpipe = Not Supplied) is not finalized — currently the dependent
   field is left open rather than skipped/blocked. To be confirmed with
   engineering (likely conditional-applicability, i.e. skip the dependent field
   like Wetted Hardware Selection).
2. MotorHpRpm -> Motor Type: enforced as a part-number-assembly constraint, not
   a dropdown filter (MotorType is a derived composite of Enclosure/Efficiency/
   Voltage/Hertz, not a single selectable field). Flagged in code.
3. Series 6000, 7530: no configuration data in Rev0.3 (engineering decision).
4. Series 7500, 8500: config works; pricing rules absent (F130 finding).

## 6. Exit decision

Exit gate criteria 1–4 are met for the supported series with the corrections
above; invalid combinations now fail closed (the central F140 gap). Remaining
items in section 5 are deferred to UAT feedback and do not represent unenforced
core constraints. Engineering testing continues on the deployed environment;
any reported defects will be handled as corrections within the appropriate
milestone.

Next milestone: F150 — SQL Fybroc Identifier Authority (per roadmap; note prior
identifier/SKU work exists and will be reconciled/verified against F150's exit
gate rather than assumed complete).

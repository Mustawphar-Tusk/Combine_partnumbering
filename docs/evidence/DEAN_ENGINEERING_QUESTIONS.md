# Dean Configuration — Open Engineering Questions

**Status:** LIVING DOCUMENT. Updated as items are resolved.
**Last updated:** 2026-08-26
**Owner (dev side):** Dean configurator development (D100–D140+).

> **2026-08-26 — NEW AUTHORITATIVE WORKBOOK.** Engineering delivered
> `workbooks/Dean/PumpConfiguration_Logic_0.1.xlsm`, which SUPERSEDES the prior
> `PumpConfiguration_Logic.xlsm` and `Dean Data Sheet Rev 2.xlsm` as the single
> source for ALL constraints + hex/numbering mapping. It puts the offered-option
> applicability (Pump Constraints), the field catalog (Config Options), the
> codependencies, the pricing overlay (Price Options), and the per-segment
> numbering tables in ONE workbook, cross-referenced by option-field NAME — which
> structurally CLOSES the config-vs-numbering divergence (B1–B4) and gives Flush
> and Barrier their own numbering (E3). Seal code is still being worked by
> engineering → **seal stays OMITTED from the PN but is NOT discarded** (its slot
> is retained). Structure map: `docs/evidence/D100/PCL_V01_STRUCTURE.md`.
> Statuses below updated accordingly; three NEW gaps in v0.1 added as §F.

## Purpose & guiding principle

The **Excel macros and formulas are the authority.** We reproduce the workbook's
logic faithfully and build a solid, efficient system that does NOT depend on the
workbook's runtime weaknesses (COM fragility, external Access DBs). We do **not**
invent our own filtering to make constraints "suitable." Where the authoritative
workbook is itself weak, incomplete, or internally inconsistent, we **preserve the
authoritative behavior, flag it here for engineering, and keep developing** against
everything else until we get feedback — then reconcile.

Legend: **OPEN** = awaiting engineering. **RESOLVED** = answered (record the
decision + date). **MEANWHILE** = what dev does until it's resolved.

---

## A. External data sources we don't have

### A1 — Seal Numbering Access DB (`Seal Numbering.accdb`) — OPEN
The Smart Number seal cell only ever emits a placeholder:
`O12 = IF('Data Sheet'!D49<>"Included","00000","TBD__")`. The real seal *code* is
authored by the VBA `getSealOptions` against an external Access DB ("Combined
Table"), keyed on ~14 seal attributes (Seal Type, Manufacturer, faces, elastomers,
hydropads, pumping ring, throttle/min-flo bushing, lantern ring, seal chamber
config, gland style/gasket, sleeve material).
- **Impact:** no source we have can produce a real seal code. Seal segment was
  removed from the Dean PN (it was only ever `00000`/`TBD__`).
- **MEANWHILE:** seal status tracked out-of-band (`included_external_db` / `none`);
  seal price is C/F (D120).
- **NEED:** Provide `Seal Numbering.accdb` (or an export of "Combined Table" + key
  columns). Confirm: should the seal code be part of the Dean Part Number, or is it
  correctly a separate/quoted item?
- **2026-08-26 UPDATE:** Engineering is actively working the seal configuration
  code (the new workbook addresses everything EXCEPT seal). Per direction, seal
  stays **OMITTED from the PN but NOT discarded** — its segment slot is retained so
  it can be dropped back in cleanly once engineering delivers the seal code.
  Remains **OPEN** (seal-only).
- **2026-08-26 SEAL-VOCAB MISMATCH (new, under A1):** When the authoritative
  `Codependencies` sheet was parsed row-aligned (D110 reload), **519 seal-related
  allow-tuples were SKIPPED** because their seal vocabulary does not reconcile with
  the `Pump Constraints` applicability matrix. The Codependencies sheet spells seal
  fields with long descriptive names (e.g. full seal-option/gland/flush/barrier
  descriptions), whereas `Pump Constraints` uses short canonical names
  (e.g. `Type N`). Because we cannot safely map one vocabulary onto the other
  without engineering's seal authority, these 519 seal codependencies are held out
  of the enforced FeasibleConstraint set. This is why the workbook's only 4-leg quad
  (Seal Option × Gland Type × Flush Plan × Barrier Plan) is not enforced.
  - **Impact:** seal codependencies are NOT enforced; consistent with seal being
    OMITTED-not-discarded. 256 non-seal tuples ARE enforced (251 2-leg + 5 3-leg).
  - **NEED:** With the seal code (A1 above), provide the crosswalk between the
    Codependencies seal descriptions and the Pump Constraints seal short-names so
    the 519 seal tuples can be reconciled and enforced.

### A2 — Standard Confs Access DB (per Series+Size standard configuration) — OPEN
`SetDefaultOptions_Click` fills a model's full default config from an external
"Standard Confs" Access DB keyed by Series+Size. We don't have it; our STD defaults
come from the `Pump Options` sheet (D110), which is not always the same fully-
specified standard row.
- **Impact:** for some models our STD seed differs from the workbook's Standard
  Confs, so a "standard" config can land on values the numbering can't encode.
- **MEANWHILE:** we use the `Pump Options` STD/X grid as the authoritative STD we
  have.
- **NEED:** Provide the "Standard Confs" table, OR confirm the `Pump Options` STD
  markers ARE the authoritative standard defaults.

---

## B. Authoritative-workbook internal inconsistencies (Pump Options vs numbering)

These are cases where the authoritative workbook itself offers an option its own
numbering engine (Module2) cannot turn into a code. We do NOT filter these out — we
preserve them and flag them.

### B1 — `OILER_OPTIONS` offered but absent from the Power-Frame numbering — RESOLVED (2026-08-26)
**Resolution:** In `PumpConfiguration_Logic_0.1.xlsm` the Power Frame Numbering
enumerates `Oiler Options` (col H) with `Thermoplastic Oiler`, `Glass/Alum Oiler`,
etc. — oiler IS now in the power-frame numbering, and the offered options + the
numbering come from the same workbook. Closed by the new authority.
For R5140 (and likely its family), `Pump Options` marks
`OILER_OPTIONS='Glass/Alum Oiler'` STD (also offers Glass w/Cage, Oil Mist
Pure/Purge, Thermoplastic Oiler). But the Power End numbering (460 rows) has Oiler
= `NONE` at every row — the workbook can offer an oiler but its own power-frame code
cannot represent it, so the power-frame segment resolves to unresolved for those
models.
- **NEED:** Is Oiler supposed to affect the Power Frame segment code? If yes, the
  power-frame numbering is missing oiler enumeration (workbook gap). If no, Oiler is
  a non-numbered/descriptive option and should not participate in the power-frame
  code.

### B2 — Wet-End option *combinations* not enumerated — RESOLVED (2026-08-26, pending re-load verification)
**Resolution:** The new workbook builds the Wet End numbering from the SAME Pump
Constraints per-model option sets that define the offered options (Module1
enumerates the cross-product per model). So every offered wet-end combination is,
by construction, enumerated. To be re-verified after the D110/D130 re-load.
CNV206 1.5x3x6: each value is valid in the numbering (`Aramid` gasket ✓, `NPT Plug`
drain ✓), but that specific full wet-end combination has no enumerated row in the
Wet End numbering.
- **NEED:** Are all offered wet-end option *combinations* meant to be numberable, or
  does the workbook intentionally enumerate only a subset (some allowable selections
  legitimately have no wet-end code)?

### B3 — `CASING_TAPS` standard value not offered by the config grid — RESOLVED (2026-08-26)
**Resolution:** New workbook: `Casing Taps` in Wet End Numbering includes `No Taps`
(+ NPT Discharge / NPT Discharge & Suction), and Config Options lists the same
domain — offered options and numbering aligned in one source.
The Wet End numbering standard row uses `No Taps`, but `Pump Options` for some models
offers only `Custom` / `NPT Discharge` / `NPT Discharge & Suction` (not `No Taps`).
- **NEED:** Is `No Taps` a valid Casing Taps selection for those models? Which source
  is authoritative for what's offered (Pump Options grid vs numbering)?

### B4 — `SHAFT_MATERIAL` standard value not offered by the config grid — RESOLVED (2026-08-26)
**Resolution:** New workbook: Power Frame Numbering `Shaft Material` includes
`Steel`, `316 SS`, `Hybrid 316 SS`, etc., matching Config Options — aligned in one
source.
Power-Frame numbering standard uses `Steel` shaft material, but `Pump Options` for
some models offers only `Custom` for Shaft Material.
- **NEED:** Is `Steel` a valid shaft material for those models? Same source-of-truth
  question as B3.

---

## C. Segments the workbook itself gates or leaves inert

### C1 — Motor Frame code (HP×RPM matrix) — OPEN
`W12 = IF(motor/baseplate/coupling present, BASE(MATCH(frame, Table2486[Motor Frame
Size]),36,2), "00")`. The frame code comes from a HP×RPM×frame matrix (`Motor
Constraints`); gated to `00` with no motor.
- **MEANWHILE:** we gate to `00` and have not reproduced the full matrix.
- **NEED:** Confirm the motor-frame code is only meaningful when a motor is included
  (Dean-supplied) and `00` otherwise. If it must encode for motor-included configs,
  confirm the authoritative HP×RPM→frame mapping.

### C2 — Motor Options segment (`AB12`) is inert — OPEN
The Smart Number "Motor Options" cell has NO formula — static `00`.
- **NEED:** Is Motor Options intentionally not encoded in the Part Number
  (placeholder `00`), or is this an unfinished workbook cell that should encode
  something?

### C3 — Motor / seal pricing is C/F — OPEN
Consistent with A1 and C1: the Dean Pricing Matrix marks seal "No Seal Only," motor
is C/F.
- **NEED:** Confirm motor and seal are intentionally Contact-Factory (quoted
  separately), not priced from the Matrix.

---

## D. Pricing / source anomalies (D120)

### D1 — RTA3146 / Formed / 326TS / Steel baseplate: two Matrix prices — OPEN
The Dean Pricing Matrix has two conflicting prices ($1,878 vs $2,209) for the same
key (RTA3146, Formed baseplate, 326TS frame, Steel). We took first-seen and flagged.
- **NEED:** Which price is correct?

### D2 — Baseplate keying (Type + Drip Pan; Economy = Formed) — OPEN
We decomposed the Matrix "Baseplate Material" dimension into Baseplate Type + Drip
Pan, treated "Economy" (Rev2) = "Formed" (Matrix), lugs descriptive (not separately
priced).
- **NEED:** Confirm "Economy = Formed," baseplate price driven by Type + Drip Pan
  (+ mounting), and lug flags are descriptive (no separate adder).

---

## E. Model scope / reconciliation

### E1 — Two Dean models have no A#/D# identity — OPEN
Of 206 reconciled models, 204 have an authoritative A#/D#; 2 are
`LOGIC_ONLY_REVIEW` (no full A#/D#) and were excluded from the identifier load.
- **NEED:** Are those 2 models real/current? If so, their A-numbers.

### E2 — Blocked codependency values (Throttle Bushing / Bearing Frame Cooling) — OPEN
D110 excluded two codependency tuples as out-of-domain, pending engineering:
`Throttle Bushing = Required` (domain: Not Required / Carbon) and `Bearing Frame
Cooling = NONE` (domain: Not Required / Steel Tube / ...). Look like copy/paste
errors in the Codependencies sheet.
- **NEED:** Confirm these are workbook data errors (and the correct values), or that
  they are intentional.

### E3 — Flush Plan letter derivation — RESOLVED (2026-08-26)
**Resolution:** The new workbook gives **Flush Plan** and **Barrier Plan** their own
numbering sheets (Flush Plan Numbering 185 rows with its own Alphanumeric Code;
Barrier Plan Numbering defined). Flush/barrier codes now come from a proper
per-plan numbering table driven by `Flush_Barrier Plan Constraints` (Module2), not
a derived letter cell. (Barrier table currently un-built — see §F2.)

### E2 — Blocked codependency values — RESOLVED pending re-load (2026-08-26)
**Resolution:** Codependencies are re-authored in the new workbook (row-3
NONE-collapse notes + driver→dependent whitelists). Re-load from the new source;
the old BLOCKED_VALUES (Throttle Bushing=Required, Bearing Frame Cooling=NONE)
should no longer be needed — verify during D110 re-load and drop if clean.

---

---

## F. NEW gaps in the authoritative PumpConfiguration_Logic_0.1 workbook (2026-08-26)

These are gaps in the NEW authoritative workbook itself (current engineering
items, not dev defects). Found while characterizing it (see PCL_V01_STRUCTURE.md).

### F1 — Cooling Plan Numbering is EMPTY — OPEN
The `Cooling Plan Numbering` sheet has no table (max_row=1). Cooling Plan option
domains exist (Config Options: Cooling Plan / Routing / Extras / Connections /
Temperature; a Cooling Plan group in Pump Constraints), but no enumerated numbering
table / codes were built.
- **MEANWHILE:** cooling-plan segment will be unresolved (retain slot, do not
  fabricate) until the table is built.
- **NEED:** Build the Cooling Plan Numbering table (run the numbering macro for
  cooling), or confirm cooling is not part of the Dean PN.

### F2 — Barrier Plan Numbering has header only, 0 data rows — OPEN
`Barrier Plan Numbering` has the header (Permutation / Alphanumeric Code) but no
enumerated rows (Module2 not yet run for barrier).
- **MEANWHILE:** barrier segment unresolved (retain slot).
- **NEED:** Build the Barrier Plan Numbering rows (Module2 from Flush_Barrier
  constraints), or confirm.

### F3 — Motor main Alphanumeric Code (col O) is inert `000` — OPEN
The Motor Numbering MAIN code column (O) is a single constant `000` across all
13,260 rows; the only live motor code is the Frame-Size sub-table (S/T/U → 2-char
code). So motor currently encodes frame size only, not the full motor combination.
- **MEANWHILE:** motor segment = frame-size code (from the sub-table) + the gated
  no-motor behavior; full motor code retained-but-unresolved.
- **NEED:** Should the Motor main code (full motor combination) be generated, or is
  motor intentionally frame-size-only in the PN? (Relates to C1/C2/C3.)

---

## How to record a resolution
For each item, set status to **RESOLVED (YYYY-MM-DD)**, capture the engineering
decision verbatim, and note the dev change that implements it (file + commit). Do
not silently redefine an item — corrections are permanent.

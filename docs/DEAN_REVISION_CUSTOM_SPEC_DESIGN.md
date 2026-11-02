# Dean Revision — Pump Constraints Custom Fields + Seal Reference + Custom-Spec Lifecycle (design)

**Status:** DRAFT for sign-off. Additive-only, **Fybroc (PumpFamilyId 2) frozen**.
**Authoritative source:** `workbooks/Dean/PumpConfiguration_Logic_0.1.xlsm` →
sheet **`Pump Constraints`** (NOT `Pump Constraints (2)`, which is an ignored copy).
**Owner request (this session):**
1. Re-ingest the revised `Pump Constraints` so every grouping's new **Custom**
   option is selectable.
2. Capture the new per-series **Seal Reference Table** as a reference (not in the PN).
3. Selecting **Custom** in the UI opens a **pop-up** to describe the needed
   customization; this **forces engineering review** on quote submit; the
   application engineer resolves the custom spec; the resolved spec is stored in
   the DB **associated with its grouping** (Motor Spec, Power Frame, Wet End, …)
   and is **reusable** for identical builds, exactly like standard specs.

---

## 1. Verified facts (from reading the workbook + code)

### Revised `Pump Constraints` sheet (233 rows × 595 cols)
- Row 2 = grouping names; Row 3 = per-option labels + identity (`A Number`,
  `Series`, `Size`); rows 4+ = per-(A#/series/size) applicability marks
  (`STD` / `X` / `O` / blank). 67 groupings.
- **Custom columns**: 41 of 67 groupings now carry a `Custom` option column
  (all material/selection groupings; NOT the Required/Not-Required toggles,
  Pump Configuration, Casing Gasket, Casing Mounting, Impeller Balance, bearing/
  oiler/sight-glass, Seal Option, Seal Configuration, Gland Type, Min-Flo, Drip Pan).
- **Seal Reference Table**: column **594**, header in **row 3** ("Seal Reference
  Table"), genuinely NEW. One value per series — a shaft-size seal key:
  `1.000"/1.375"/1.750"/2.125"/2.250"/3.000" Shafts`, plus `Misc.` and `X`.
  (e.g. R4140→`1.750" Shafts`, PH2110→`1.375" Shafts`, DL200→`1.000" Shafts`,
  RM5140/RMA5140/M300/Deanline→`X`, older R/RWA→`Misc.`).

### Existing pipeline (reused, not duplicated)
- `scripts/d110_load_dean_config_v01.py` reads `Pump Constraints` and loads
  `cfg.SeriesFieldOption` (per series/size STD/X options) + `cfg.FeasibleConstraint`
  (codependency allow tuples). A `Custom` cell is already normalized to the
  Contact-Factory marker **`C/F`** (`_norm_value`).
- `scripts/load_dean_identifier_to_sql.py` loads numbering → `stg.SegmentCombinationImport`
  (per-grouping coded combinations, with `ExpectedWidth`). Dean groupings & widths:
  WET_END_OPTIONS 4, IMPELLER_OPTIONS 2, POWER_FRAME_OPTIONS 4, BASEPLATE_OPTIONS 2,
  FLUSH_PLAN 2, MOTOR_FRAME 2, MOTOR_SPEC 4.
- `src/api/dean_identifier.py` resolves segment codes; a selected `Custom` collapses
  the owning segment to a padded placeholder (`SEGMENT_CUSTOM_PLACEHOLDER`).
- **A2** `quote.QuoteLineCustomization` (sql/30): per-line, per-grouping free-text
  customization requests, draft-only CRUD. Already surfaced in `/unresolved`.
- **A5** review case: unresolved items (incl. customizations) force review;
  engineer resolves; `usp_CompleteReviewCase` gate.
- **A4** `cfg.CustomSegmentCode` (sql/33): governed per-(family, grouping, spec-key)
  base-36 custom code, minted next-after-max(real ∪ custom), **family-wide reuse by
  spec SHA**. Mint needs an authoritative `ExpectedWidth` for the grouping.

> KNOWN CONSTRAINT: A4 minting requires a grouping width from
> `stg.SegmentCombinationImport`. Groupings WITHOUT a coded numbering table
> (e.g. seal groupings, which are resolved-but-omitted today) have no width, so
> they cannot mint a real code yet. The design handles this explicitly (§4.4).

---

## 2. Scope (phased)

### Phase D-R1 — Workbook re-ingest + Seal Reference Table (data, additive)
1. Re-run `d110_load_dean_config_v01.py` against the revised `Pump Constraints`.
   Verify: Custom columns load as `C/F` options; **no grouping header silently
   dropped** (compare parsed groupings to `CANONICAL_CODES`/aliases; add any
   missing). Row counts for Dean `cfg.SeriesFieldOption` rise by the new Custom
   rows; Fybroc watermark unchanged.
2. New additive table **`cfg.DeanSealReference`** (`Series` PK, `SealRefKey`,
   `SourceRow`), loaded from column 594. A new loader
   `scripts/load_dean_seal_reference.py`. **Not** wired into the PN. Read-only
   reference endpoint later if needed.

### Phase D-R2 — Custom-spec lifecycle (the main feature)
The configurator→quote→review→reusable-code flow, per grouping. The resolved
custom code occupies the grouping's PN segment slot at its native width (§4.1),
so a custom build has a same-shape PN with the custom code in that slot.

**2a. Configurator pop-up.** When a grouping's value is set to the Custom option
(`C/F`), the SPA opens a modal to capture the custom spec text for that grouping
(reuse the existing `CustomRequestModal`). On save it records a
`quote.QuoteLineCustomization` row (Grouping = the segment code, FieldCode = the
specific field, RequestedChange = the entered text) against the quote line.
(Configurator must be in a quote-line context; from a fresh config the custom
request is captured on the draft and persisted when the line is added.)

**2b. Forces review.** A line with a Custom selection (or any
`QuoteLineCustomization`) already makes `/unresolved` return `requires_review`,
which gates completion. On submit it routes to the engineer queue (existing A5).
We ensure a `C/F`-valued grouping is treated as unresolved (it is today via the
customization record; we add: a line whose selections contain a `C/F` grouping
value also flags unresolved even without a free-text row).

**2c. Engineer resolves → stores spec per grouping → mints reusable code.**
New proc **`cfg.usp_ResolveCustomSpec`** (additive) that, given
(family, grouping, spec text, optional selections), computes the spec SHA and
calls the existing `usp_GetOrCreateCustomSegmentCode` to store/reuse the code,
and links it to the review-case line + the `QuoteLineCustomization`. The engineer
UI (review workspace) gets a "Resolve custom spec" action per custom grouping.

**2d. Reuse.** Because `cfg.CustomSegmentCode` is keyed by (family, grouping,
spec SHA) with family-wide reuse, an identical build that enters the same custom
spec for the same grouping resolves to the **same code** — no new mint — exactly
like a standard coded combination is reused. The resolved code + spec are
retrievable via `usp_ListCustomSegmentCodes` and surfaced on the line.

### Phase D-R3 — Verify + ceremony
Audits + Fybroc gate + evidence + roadmap/register + commit/push.

---

## 3. Data model (all additive)

- `cfg.DeanSealReference(Series PK, SealRefKey, SourceRow, LoadedAt)` — new.
- Reuse `quote.QuoteLineCustomization` (A2) for the per-grouping request + the
  resolved result (add nullable `ResolvedCustomCode VARCHAR(16)` +
  `ResolvedSpecKey VARCHAR(64)` + `ResolvedByAppUserId` + `ResolvedAt` columns —
  additive ALTER; draft-only guard unchanged for the request fields).
- Reuse `cfg.CustomSegmentCode` (A4) for the reusable per-grouping code/spec.
- No change to `cfg.ConfiguredProduct`, `cfg.usp_AssembleConfiguredProduct`,
  `dean_identifier`, or the Dean PN shape. Seal stays out of the PN.

## 4. Key decisions / open points  (UPDATED per owner 2026-08-26)

1. **Custom does NOT change the PN STRUCTURE/WIDTH — but the minted custom code
   OCCUPIES the grouping's segment slot at the same width.** (Owner: "the new
   custom spec should fit into the original placeholder in the PN … same width but
   a new custom spec".) So choosing Custom for the Wet End yields a PN of the
   IDENTICAL shape, with the 4-char Wet End slot carrying the reusable custom
   base-36 code (from `cfg.CustomSegmentCode`, minted next-after-max at width 4,
   collision-safe, reusable by spec) instead of a standard wet-end code:
   `D<A#>-<CUSTOM_WETEND(4)>-<Trim(2)><ImpOpts(2)>-<PowerEnd(4)>-…`
   - The authoritative numbering tables (`stg.SegmentCombinationImport`) are NEVER
     edited; the custom code is minted in the SEPARATE A4 mirror and spliced into
     the segment slot at resolve time for that configuration only.
   - Two identical custom-wet-end builds reuse the SAME custom code → SAME PN
     (reuse parity, like standard builds).
   - A custom build therefore has a DISTINCT, STABLE PN (the custom code differs
     from every real code by construction) — correct: a customized wet end is a
     distinct product with the same PN structure.
   - IMPLEMENTATION IMPACT: `dean_identifier.resolve_segments()` (Python) and the
     DEAN branch of `sql/23_Create_Assemble_Configured_Product.sql` (SQL) must BOTH
     substitute the minted custom code into the grouping's slot when that grouping
     is custom. Standard builds stay byte-for-byte unchanged (python==SQL parity
     preserved; verified by the existing identifier parity audit).
2. **Grouping key** for a custom spec = the numbering segment code (WET_END_OPTIONS,
   POWER_FRAME_OPTIONS, IMPELLER_OPTIONS, BASEPLATE_OPTIONS, MOTOR_SPEC, FLUSH_PLAN).
   Field-level custom maps to its owning segment. [Confirmed]
3. **Seal Reference Table = capture-only** (Phase D-R1), per series, not in the
   PN. [Confirmed]. Engineering has just updated seal configuration; seal spec
   numbers will be filled in shortly, at which point seal gains a numbering width
   and seal customs can mint a code like any other grouping.
4. **Groupings with no coded width yet** (seal, until its numbering lands): the
   custom request is captured + forces review + the resolved spec text is stored,
   but the reusable CODE is deferred until that grouping has a width. The seal slot
   is not in the PN today anyway, so there is no PN placeholder to fill yet.
   Disclosed, not silently dropped. [Confirmed]

## 5. Verification

- `scripts/audit_dean_revision.py` (new, re-runnable, self-cleaning):
  1. Revised sheet re-ingested: every Custom-bearing grouping has a `C/F` option
     in `cfg.SeriesFieldOption` for the expected series; 0 literal "Custom" left;
     no grouping header dropped.
  2. `cfg.DeanSealReference` has one row per series with the exact col-594 value
     (derived from the workbook, not hardcoded).
  3. Lifecycle: select Custom on a grouping → customization row + unresolved →
     submit forces review → engineer resolve mints a code via A4 → identical spec
     reuses the SAME code (WasExisting) → different spec mints a new one.
  4. Dean PN for a non-custom build is byte-unchanged vs before (parity oracle).
- `scripts/audit_dean_config.py` still passes (STD/applicability/fail-closed).
- `scripts/run_all_fybroc_audits.py` = ALL CORRECTIONS INTACT 9/9.
- Isolation watermarks: non-DEAN cfg.SeriesFieldOption 3638, non-DEAN
  stg.SegmentCombinationImport 300608 unchanged; DEAN segment 140976 unchanged
  (no numbering reload in D-R1 unless we re-run the identifier loader — if we do,
  re-baseline DEAN segment count and disclose).

## 6. Questions for sign-off
- Confirm decisions 1, 2, 4 above (PN untouched; grouping=segment code; seal/no-width
  groupings defer the *code* but still capture+review+store the spec).
- Build order: D-R1 (re-ingest + seal ref) first as its own commit, then D-R2
  (lifecycle), then D-R3 ceremony. OK?

# CPQ UI Expansion Roadmap — align this project's UI + scope with `docs/api/ui_logic.md`

**Status:** DRAFT — awaiting user approval. No implementation has started.
**Backup taken:** `C:\Users\makorede\Downloads\Combine_partnumbering_BACKUP_pre_CPQ_20261026_183218.zip` (5.88 MB; source + config + SQL + UI + docs + scripts; excludes regenerable `.venv`/`.git`/caches/workbooks).
**Scope:** Bring the reference CPQ tool's **layout and feature scope** into this project for **BOTH Dean and Fybroc**, driven by the **real v2 API** (never the reference's client-side mock engine), with **zero functionality collision** and **Fybroc frozen**.

---

## 0. Guiding principles (non-negotiable)

1. **Server is the authority.** The reference script computes pricing, encoding, and
   constraints client-side from mock data (`priceCfg`, `encodeSpec`, `CONSTRAINTS`,
   `FIELD`, `GROUPS`). We **do not port any of that logic.** Every price, part
   number, SKU, constraint, standard default, and segment code continues to come
   from the Python v2 API / SQL Server. We adopt the reference's **UX patterns and
   layout only.**
2. **No collision.** We reuse the existing authoritative flows
   (`resolve-state`, `resolve`, `by-sku`, `quotes`) rather than creating parallel
   ones. New endpoints are **additive** and only fill genuine gaps.
3. **Fybroc stays frozen.** No changes to Fybroc pricing, constraints, PN assembly,
   or any shared table in a non-additive way. The Fybroc regression gate
   (`run_all_fybroc_audits.py` → "ALL CORRECTIONS INTACT" 9/9) and the isolation
   watermarks must hold after every phase.
4. **Both families, one UI.** The reference is Fybroc-only; we generalize its
   patterns so Dean and Fybroc share the same shell, each driven by its own
   family data from the API.
5. **Incremental + revertible.** Each phase is independently shippable, committed,
   and verified before the next begins. UI-only phases are LEAN; phases that add
   endpoints/tables or reload data are FULL milestones.

---

## 1. What the reference provides vs. what this project already has

The reference (`docs/api/ui_logic.md`) is a single-page CPQ tool: a `state → render()`
app with these views: **Log/Home, Quote, Configurator (`vConfig`), Lookup, Applications
Queue, Applications Worksheet, Custom-code Library, Data-model**, plus modals
(new quote, spec sheet, quote preview, customer-notify, drive-add, confirm) and
**jsPDF** quote + spec-sheet export.

Grounding check against this repo (already verified):

| Reference feature | This project's backend today | Gap |
|---|---|---|
| Configurator with constraints/std defaults | `POST /configurations/resolve-state` (both families) | **UI polish only** |
| Spec number / PN / SKU | `POST /configured-products/resolve` (PN+SKU+signature+reuse) | **UI only** |
| Component prices + deltas | `resolve` returns `pricing` + `component_pricing` (per-component, found/C\/F) | **UI only** |
| SKU/spec lookup | `GET /configured-products/by-sku/{sku}` | **UI only** |
| Quotes (header + lines) | `POST /quotes`, `POST /quotes/{id}/lines`, `GET /quotes/{id}` + `quote.usp_*` | **UI + a few list/read endpoints** |
| BOM per line | `resolve` returns `bom` | **UI only** |
| Accounts / contacts / roles | — none — | **New (thin) endpoint + seed data** |
| Applications queue (pending/C\/F lines) | derivable from quote line `pricing_status` | **New list endpoint + UI** |
| Custom X-code library (seal/motor/special) | — none — | **New table + endpoints + UI (biggest new piece)** |
| PDF quote + spec sheet | — none (text render exists in `_quote_to_document`) | **New (client-side jsPDF, UI only)** |
| Data-model page | scattered across docs | **UI (optional, read-only)** |

**Conclusion:** the heavy backend (pricing, encoding, constraints, quotes, BOM) already
exists and is family-agnostic. The expansion is **predominantly a UI build** on top of
the real API, plus a small number of additive endpoints. This is what makes "same scope,
no collision" realistic.

---

## 2. Target architecture for the new UI

- **One SPA shell** adopting the reference's `state → render()` + delegated
  `data-action` pattern, but every data mutation that matters (price, PN, SKU,
  constraints, quote persistence) is a call to the v2 API. Client state holds only
  view/session/UI data (active view, current quote id, draft selections, lookup
  result, toasts), never authoritative pricing/encoding.
- **Family-parametric.** A top-level family switch (Dean / Fybroc) drives every view
  from that family's API responses (`field_groups`, `allowable_options`,
  `standard_defaults`, `resolved_codes`, `pricing`). No family-specific hardcoding of
  options or prices in the client.
- **Files:** evolve the existing `ui/` (keep `configurator.html` working at all times;
  introduce the shell incrementally so we never have a broken UI between phases).
  Reuse existing `postJson`, `esc`, cold-start retry, and the accordion renderer.
- **No new client pricing/encoding modules** (no `cpq-logic.js` equivalent).

---

## 3. Phased plan

Each phase lists: deliverables, API touchpoints, collision guard, effort mode, exit check.

### Phase A — UI shell + view router (LEAN, UI-only)
- **Deliverables:** Introduce the `state/render/action` shell and a top nav
  (Configurator · Lookup · Quotes · Queue · Library · Data model) wrapping the
  **existing** configurator and lookup views unchanged. Family switch at the top.
- **API:** none (pure refactor around current calls).
- **Collision guard:** existing configurator/lookup behavior must be byte-for-byte
  equivalent in outcome (same API calls, same results). Manual smoke on both families.
- **Exit:** both families still configure + look up exactly as before; nav switches views.

### Phase B — Configurator view polish `vConfig` (LEAN, UI-only, both families)
- **Deliverables (implemented):** adopt the reference's configurator UX on top of the
  data `resolve-state` already returns:
  - **"Standard" badges** on a field row when its value equals `standard_defaults`.
  - inline **blocked / conflict / dropped reasons** per field (from `conflicts`,
    `dropped_fields`, `reset_fields`).
  - a **spec-number "plate"** with per-segment chips on the **result view**. *(Placement
    finding: a truly LIVE configurator plate is NOT possible in a LEAN UI pass — see note
    below — so the plate is shown where the data is real: the result page.)*
- **DEFERRED — per-option price-delta labels.** The reference shows a price delta next to
  every option, but it computes prices client-side from its mock engine. This project's
  `resolve-state` returns `allowable_options` / `standard_defaults` / `resolved_codes` /
  `conflicts` but **no per-option prices**, and the authoritative price lives server-side
  (`/configured-products/resolve` → `pricing` + `component_pricing`, for the whole
  configuration). Showing a per-option delta would require either an N-options×`resolve`
  fan-out (slow) or a new "price this option" endpoint — neither is a LEAN UI change, and
  faking it client-side is exactly the collision we forbade. So per-option deltas are
  deferred to a later additive pricing endpoint; the **total price already shows on the
  result page** from `resolve`. Recorded here so the gap is not glossed over.
- **FINDING — no live per-field codes.** `resolve-state` returns `resolved_codes` with
  every field key present but **all values `null`** (verified live: Fybroc 1500 → 31 keys,
  0 non-null; Dean Deanline → 63 keys, 0 non-null). The PN segment codes are produced by
  `/configured-products/resolve`, which returns the assembled `part_number` string (not a
  per-field code map). So a "live" plate in the configurator would always be empty, and
  per-segment chips can't be truthfully built from a code map. The plate therefore renders
  the **real generated Part Number split on `-` into one chip per segment** on the result
  page — every chip is a true segment of the actual PN, nothing faked, no client-side
  encoding. A genuinely live plate would need a new endpoint and is deferred with the
  price-delta work.
- **API:** existing `resolve-state` + `resolve` only (no new calls, no change to existing
  calls).
- **Collision guard:** zero pricing/encoding math in the client — every value shown
  (std default, segment code, conflict) comes straight from the API. Fybroc view updates
  visually but calls the same frozen endpoint with identical payloads.
- **Exit:** both families show Standard badges and inline reasons in the configurator;
  the result-view plate renders the generated Part Number as per-segment chips (chips
  reassemble to exactly the `resolve` Part Number).

### Phase C — Quotes view + quote lifecycle UI (FULL, mostly UI + thin endpoints) — ✅ COMPLETE
**Status: PASS** (evidence: `docs/evidence/PHASE_C/CPQ_QUOTES_UI_EXIT.md`). Shipped: Quotes
page (list/create/open) + "Add to a quote" on the result page; new additive read-only
`GET /families/{family}/quotes` + `quote.usp_ListQuotes`. Milestone audit
`scripts/audit_cpq_quotes_ui.py` 16/0; Fybroc gate 9/9 ALL CORRECTIONS INTACT; isolation
before==after on all config/constraint/segment/non-Dean tables (only quote tables grew).
Known gap: Dean base price pending (Dean line = call_for_price/$0) — pre-existing, disclosed.
Line edit/remove UI deferred.

- **Deliverables:** Quote list, open quote, add line from a configuration, edit/duplicate/
  remove line, line summary with item/spec number + price + lead, quote totals.
- **API:** reuse `POST /quotes`, `POST /quotes/{id}/lines`, `GET /quotes/{id}`.
  **New additive endpoints:** `GET /families/{family}/quotes` (list),
  and line update/remove if not already covered by `quote.usp_*` (confirm during design;
  add procs only if missing, additively).
- **Collision guard:** lines persist through the existing resolve→line flow (identity/
  BOM/price unchanged). No change to `usp_AddQuoteLine` pricing semantics.
- **Exit:** create a Dean quote and a Fybroc quote, add lines, reopen, totals correct;
  Fybroc gate + watermarks intact.

### Phase D — Accounts / contacts / roles (FULL, additive backend + UI)
- **Deliverables:** account + contact directory, role toggle (distributor vs applications),
  "quote for any company" like the reference.
- **API:** **new additive table(s)** `quote.Account` / `quote.Contact` (or a seed JSON if
  we want zero schema change — decided in design), plus `GET/POST` endpoints. Quote header
  already has `customer_name`/`customer_account`.
- **Collision guard:** additive tables only; nothing shared with Fybroc config/pricing.
- **Exit:** can pick an account/contact when creating a quote; persists on the header.

### Phase E — Per-grouping custom-hex codes + applications queue + custom-code library (FULL, the one PN-touching phase)
This replaces the reference's single global `X01/X0001` space with **per-segment base-36
custom codes** that extend each grouping's own combination table. This is the ONLY phase
that touches authoritative part-number assembly, so it carries the strongest guards.

**User-approved design decisions (locked):**
- **Radix:** base-36 (`0-9A-Z`), matching the segment code vocabulary.
- **Minting (Q2 = option 2):** a new custom value takes the **next incremental base-36
  value after the current last value** in that segment's combination field (straight
  increment in the segment's shared space — not a reserved top-down range).
- **Reuse (Q3 = option 3):** **family-wide** across all series. The same custom option
  selection for a grouping always resolves to the **same hex + value row**, regardless of
  series.
- **Families:** **Dean first.** Replicate to Fybroc as a separate additive pass only after
  Dean is proven. Fybroc stays frozen during Dean work.
- **Proc style (Q5):** ONE parameterized proc driven by `@SegmentCode` (behaves
  per-grouping), not six near-identical procs.
- **Storage (Q6):** append custom rows into `stg.SegmentCombinationImport` under a
  **dedicated custom `ImportBatchId`** (separate from the frozen 'Loaded' numbering batch),
  so the frozen batch's row counts/watermarks are never mutated.

**Deliverables:**
- **`cfg.usp_GetOrCreateCustomSegmentCode`** (parameterized per grouping):
  `@FamilyCode, @SegmentCode, @CombinationKey, @SelectionsJson` →
  1. normalize the selection to the segment's existing `CombinationKey` format (reuse the
     `_build_combo` column ordering so a hit matches);
  2. look up `CombinationKeyHash` in the custom batch for that segment — **if found,
     return the existing `SegmentValue`** (family-wide reuse);
  3. else, under a lock (`sp_getapplock`/serializable), read the segment's current **max
     base-36 `SegmentValue`** (across real + custom rows for that segment), compute the
     **next** base-36 value at the segment's fixed `ExpectedWidth`, insert a new row into
     the custom batch (correct width, `SelectionsJson`, source markers), and return it.
- **Dean identifier wiring:** `src/api/dean_identifier.py` calls the proc **only at the
  custom branch** (the exact place that currently emits the `____`/`__`
  `SEGMENT_CUSTOM_PLACEHOLDER`). Non-custom segments, nearest-combo snapping, parity, and
  the whole Fybroc path are untouched.
- **Custom-code library + applications queue UI:** list every minted custom code per
  grouping (segment, selection, hex value, first-seen), and a queue of lines carrying a
  custom grouping (derived from quote-line `pricing_status` / presence of a custom
  segment). New additive read endpoints:
  `GET /families/{family}/custom-codes`, `GET /families/{family}/quotes/pending-lines`.

**Collision guards (strict):**
- Custom rows live in a **dedicated custom batch**; the frozen DEAN 'Loaded' numbering
  batch and the Fybroc batch are never modified. `stg.SegmentCombinationImport` watermark
  is measured **per frozen batch** so it stays exact (300608 Fybroc unchanged).
- **PN parity:** `py_pn == sql_pn` must hold for a representative set of custom + non-custom
  configurations. A non-custom config's PN must be **byte-identical** before/after Phase E.
- **Reload reconciliation (the option-2 caveat):** because customs increment in the shared
  base-36 space, a future authoritative workbook reload could theoretically mint a real
  code equal to an existing custom value. The audit script MUST check for any
  `SegmentValue` collision between the custom batch and the real batch per segment and fail
  closed if found; the reload procedure documents re-basing customs above the new max.
- Width `CHECK (LEN(SegmentValue)=ExpectedWidth)` is respected by the mint (fail closed if
  the segment's space is exhausted at that width).
- Concurrency: minting is atomic so two simultaneous requests cannot grab the same next hex.

**Milestone-specific audit (`scripts/audit_dean_custom_codes.py`):**
- reuse: same selection twice → identical hex; different selection → different, strictly
  incrementing hex;
- per-grouping independence: WET_END / POWER_FRAME / BASEPLATE / IMPELLER_OPTIONS sequences
  are independent;
- width + radix correctness (base-36, exact width);
- no collision between custom and real `SegmentValue` within a segment;
- PN parity on custom configs; non-custom PNs unchanged vs a pre-Phase-E snapshot.

- **Exit:** mint a Dean custom code for a grouping, reuse it on another line/series
  (same hex), library + queue list it, PN parity holds, non-custom PNs unchanged, Fybroc
  gate 9/9 and all watermarks (per frozen batch) intact.

### Phase F — PDF export: quote + spec sheet (LEAN→FULL, UI-only)
- **Deliverables:** jsPDF-based quote PDF (header + line table + totals) and per-line
  spec-sheet PDF, matching the reference's output, built from the **API's** quote document
  and configuration (reuse `_quote_to_document` data + resolved spec).
- **API:** none new (uses `GET /quotes/{id}` + resolved config).
- **Collision guard:** rendering only; no data authority in the client.
- **Exit:** download a Dean quote PDF and a Fybroc quote PDF with correct numbers.

### Phase G — Data-model page (LEAN, UI-only, optional)
- **Deliverables:** read-only page summarizing fields/groups/constraints/pricing per
  family, sourced live from the API dictionaries (not hardcoded like the reference).
- **Exit:** page renders for both families from real metadata.

---

## 4. Collision-avoidance checklist (applied every phase)

- No client-side pricing/encoding/constraint math — display API values only.
- New endpoints are additive; no change to existing endpoint response contracts
  (the VBA/Excel client and current UI must keep working).
- New tables are additive (nullable columns, new tables in `quote` schema); no
  non-additive change to any shared table.
- Fybroc isolation watermarks unchanged after each FULL phase:
  `cfg.FeasibleConstraint` 4487, `cfg.ConstraintFieldMap` 28, `cfg.SeriesFieldOption`
  3638, `stg.SegmentCombinationImport` 300608, `cfg.ConfiguredProduct` non-DEAN 1196.
- `run_all_fybroc_audits.py` → "ALL CORRECTIONS INTACT" (9/9) after each FULL phase.
- Keep `configurator.html` functional at every commit (incremental shell).

---

## 5. Verification & governance

- **LEAN phases (A, B, F, G):** make the change, smoke-test the affected view on both
  families against a running API, commit to feature + main, push `claude` + `origin`.
- **FULL phases (C, D, E):** full milestone-exit audit — milestone-specific audit script
  + `run_all_fybroc_audits.py` 9/9 + isolation watermark diff + evidence doc under
  `docs/evidence/<PHASE>/…_EXIT.md` + roadmap/register bump + commit/push all 4 refs +
  explicit PASS/FAIL exit-gate decision, then wait for go-ahead.
- **D150 (Exhaustive Dean Regression) stays PARKED** throughout; not started without
  explicit go-ahead.

---

## 6. Sequencing & checkpoints

A → B first (immediate visible value, low risk, UI-only). Pause for review after B.
Then C (quotes) → D (accounts) → E (queue + custom codes, the largest new backend) →
F (PDF) → G (data model). Each phase gated by its exit check; FULL phases wait for your
go-ahead before the next starts.

---

## 7. Decisions

### Resolved (custom-hex codes, Phase E) — user-approved
- Radix **base-36**; minting is **next-after-last** in the segment's shared space
  (option 2); reuse is **family-wide** (option 3); **Dean first**, Fybroc as a later
  additive pass; **one parameterized proc** by `@SegmentCode`; custom rows stored in a
  **dedicated custom batch** inside `stg.SegmentCombinationImport`.

### Deferred follow-on
- **Phase E-F (Fybroc custom-hex):** replicate the per-grouping custom-hex mechanism for
  Fybroc only after Dean Phase E passes its exit gate. Separate FULL milestone, additive,
  with the full Fybroc regression + per-batch watermark guards. Not started without
  explicit go-ahead (Fybroc is frozen until then).

### Still open for you (before Phase B/C design)
1. **Phase scope to approve now:** all of A–G, or stop after a subset (e.g. A–C)?
2. **Spec-number plate placement:** configurator view, result view, or both?
3. **Accounts/contacts (Phase D):** real `quote` tables, or a seeded JSON directory to
   avoid schema change? (Both are additive; tables are more faithful to the reference.)
4. **Visual theme:** keep the current sky-blue theme, or reskin closer to the
   reference's look?
```

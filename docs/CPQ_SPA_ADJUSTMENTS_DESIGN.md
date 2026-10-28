# CPQ SPA — Pre-U4 Adjustments (design, approved)

**Source:** `docs/newadjustment.md` (owner adjustments before advancing to U4).
**Branch:** `feature/cpq-spa`. Additive-only, Fybroc frozen, `uv`/npm per steering.
**Reference assets provided:** `docs/style.md` (reference CSS + Dean base-36 `encode(n,width)`).

This closes gaps in the U2/U3 workflow and brings the acceptance+PDF work forward.
Each adjustment is its own shippable unit with its own verification; the governed
custom-code model (A4) is the final, dedicated, PN-adjacent milestone.

## Investigation findings (what exists vs. gaps)
- Quote engine has `usp_CreateQuote` / `usp_AddQuoteLine` / `usp_GetQuote` / `usp_ListQuotes`
  only — **no update/remove line** proc. Editable drafts need a new additive proc.
- No per-grouping customization-request table exists (only free-text `CustomSpec` on a
  review line). Needs a new additive table.
- The governed custom-spec→code model does **not** exist (Phase E was designed, never
  built). The authoritative numbering path (`dean_identifier.resolve_segments` →
  `cfg.usp_AssembleConfiguredProduct`; `cfg.fn_LookupIdentifierCode`) exists and stays
  **untouched**. `docs/style.md` supplies the base-36 `encode(n,width)` primitive.
- Reference presentation (`docs/style.md` CSS) defines the target configurator layout
  (`.cfg` = `.summary` + `.opts`/`.gtab`/`.field`/`.opt`, `.plate`, `.req`, `.doc`).

## Decisions locked (this pass)
- **Custom code = parallel mirror, never edits the authoritative PN.** Custom codes live
  in their own per-grouping registry tables; minting mirrors the authoritative base-36
  format/width but writes to separate tables. The real PN pipeline is unchanged.
- **Mint = next-after-max (backward read).** For a grouping, max(decoded real codes ∪
  decoded custom codes) + 1, encoded at the segment width → always strictly above every
  real code, so a future real-numbering reload cannot silently collide; audit fails closed.
- **Reuse per associated custom value, family-wide:** identical custom spec for a grouping
  → same custom code + row, across quotes/series.
- **PDF = client-side (jsPDF)** off one persisted order record, so distributor and engineer
  render byte-identical documents. Retry-safe confirmation (idempotent).
- **Decode:** add inverse `decode(code)->int` mirroring `encode` exactly.

---

## Adjustment milestones

### A1 — Editable / resumable draft quotes  (item 1)  [additive proc]
- New `quote.usp_UpdateQuoteLine` (and `usp_RemoveQuoteLine`): re-resolve a line's config
  through the authoritative resolve flow and write PN/SKU/BOM/pricing/lineage back to the
  SAME line (no duplicate). Draft-only; submitted/completed revisions are immutable (go
  through the review/revision workflow).
- API: `PUT /api/v2/families/{family}/quotes/{id}/lines/{lineId}` (re-resolve+save),
  `DELETE …/{lineId}`. SPA: "Edit Configuration" on a draft line → opens configurator
  seeded with saved selections → save back. Persist across reload/reopen.

### A2 — Multiple customization requests per grouping  (item 2)  [additive table]
- New `quote.QuoteLineCustomization` (QuoteLineId, Grouping, FieldCode, CurrentValue,
  RequestedChange, Notes, RevisionNo, CreatedAt) — many per line/grouping; editable/
  removable while draft; visible on reopen and to engineering.
- API: list/add/update/remove customization requests for a draft line.
- SPA: a **Custom** button per grouping → modal (what to customize) with **Add Another
  Customization**; renders the reference's `.req` block.

### A3 — C/F forces engineering review + explicit unresolved list  (item 3)
- Submit-for-review computes + persists the explicit list of unresolved items: every C/F
  field (pricing_status in partial/call_for_price, or a custom request) → listed on the
  case; C/F is never treated as a completed value or $0. Surface the list in the SPA
  before submit and on the case. (Reuses U3 routing/queue.)

### A5 — Reviewed revision return + Request Further Review + Confirm Order  (item 5)
- Engineer `complete` already returns the case; add the distributor-facing reviewed
  revision view (completed config, custom specs, PN/SKU, pricing, loyalty discount, lead
  time) + **Request Further Review** (back to the same brand/site team with comments +
  revision history) and **Confirm Order**. Block engineer completion while required C/F /
  specs / prices / lead time unresolved (server-enforced).

### A6 — Confirm Order + identical PDF (both parties), retry-safe  (item 6)  [additive table]
- New `quote.OrderConfirmation` (QuoteHeaderId, ReviewCaseId, ConfirmedRevisionNo,
  ConfirmedByAppUserId, ConfirmedAt, DocumentRef, idempotency key). Confirm persists the
  exact reviewed revision; idempotent (repeat clicks → one order/doc). Engineer gets an
  order-completion notification. Both download the SAME document (client jsPDF off the one
  persisted record). Later catalog/discount changes don't alter it. **Identifier:** keep
  the quote number as the document id + add a CPQ order id on `OrderConfirmation`
  (confirm in build). No D365.

### A7 — Reference configurator presentation  (item 7)  [UI-only]
- Adopt `docs/style.md`: the `.cfg` summary+options layout, group tabs, `.opt` option
  rows, the `.plate` spec-number plate, `.req` custom block, `.doc` document. Keep the API
  + SQL metadata + engineering rules authoritative (no client math). Replaces the current
  SPA field layout (not just a recolor).

### A4 — Governed per-grouping custom-code model  (item 4)  [FINAL, dedicated milestone]
- New tables (per all groupings — wet-end, impeller, motor, power-frame, baseplate, seal,
  etc.): `cfg.CustomSegmentCode` (Family, SegmentCode/Grouping, Width, CustomValue code,
  CombinationKey/Hash of the custom spec, SelectionsJson, FirstSeenAt) + a registry of the
  custom spec itself. Separate from `stg.SegmentCombinationImport`; the real pipeline is
  untouched.
- `cfg.usp_GetOrCreateCustomSegmentCode(@Family,@SegmentCode,@SpecKey,@SelectionsJson)`:
  reuse by spec-key (family-wide) → else mint `encode(max_decoded(real ∪ custom)+1, width)`
  under a lock; fail closed if width exhausted.
- `encode`/`decode` base-36 helper (mirrors `docs/style.md`). Engineering custom-spec
  resolution calls this and displays the custom code **alongside** the authoritative PN,
  never overwriting it.
- Dean first; Fybroc replicate later (frozen until then). Audit `audit_cpq_custom_codes.py`:
  reuse determinism, per-grouping independence, width/radix, **no real∪custom collision**
  (fail closed), authoritative PN byte-unchanged.

## Verification (every milestone)
Re-runnable self-cleaning `scripts/audit_cpq_<Ax>.py`; Fybroc gate 9/9 on merits + frozen
watermarks for any DB-touching milestone; SPA build clean; `/ui` + prior `/app` intact;
evidence doc; roadmap/register bump; commit + push 4 refs. Final end-to-end demo
(newadjustment.md "Completion evidence"): reopen draft → edit → add multiple custom
requests → submit to correct queue → resolve C/F + custom specs (mint codes) → regenerate
custom representation + pricing → return for review → confirm order → notify engineering →
retrieve identical PDF; drafts stay editable after reopen; Dean/Fybroc queues isolated;
standard config/numbering regression intact.

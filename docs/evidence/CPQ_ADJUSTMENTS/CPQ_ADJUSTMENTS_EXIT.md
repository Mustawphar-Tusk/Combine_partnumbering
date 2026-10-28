# CPQ SPA — Pre-U4 Adjustments Exit Evidence (A1–A7 + A4)

**Source:** `docs/newadjustment.md` (owner adjustments before advancing to U4).
**Design:** `docs/CPQ_SPA_ADJUSTMENTS_DESIGN.md`. **Branch:** `feature/cpq-spa`.
**Mode:** FULL (the pass adds schema; A4 is the PN-adjacent milestone). Additive-only,
Fybroc frozen, `uv`/npm per steering.

This closes the seven owner adjustments. Each was built + verified with its own
re-runnable self-cleaning audit; a consolidated Fybroc gate + isolation check was run
after the DB-touching batch (A1/A2/A5/A6) and again after A4.

---

## 1. Deliverables inventory

| # | Adjustment | Migration | Audit |
|---|-----------|-----------|-------|
| A1 | Editable/resumable draft quote lines (edit in place, re-resolve, remove) | `sql/29` (`quote.usp_UpdateQuoteLine`, `usp_RemoveQuoteLine`) | `audit_cpq_a1.py` 11/11 |
| A2 | Multiple per-grouping customization requests | `sql/30` (`quote.QuoteLineCustomization` + 5 procs) | `audit_cpq_a2.py` 11/11 |
| A3 | C/F forces review + explicit unresolved-items list | (read-only endpoint) | `audit_cpq_a3.py` 6/6 |
| A5 | Completion gate + reviewed-revision return + Request Further Review | `sql/31` (gate on `usp_CompleteReviewCase`, `usp_RequestFurtherReview`) | `audit_cpq_a5.py` 11/11 |
| A6 | Confirm Order + identical PDF (both parties), retry-safe | `sql/32` (`quote.OrderConfirmation`, `usp_ConfirmOrder`, `usp_GetOrderByCase`) | `audit_cpq_a6.py` 11/11 |
| A7 | Reference configurator presentation (`docs/style.md`) | (UI-only) | SPA build (tsc+vite) |
| A4 | Governed per-grouping custom-code MIRROR model | `sql/33` (`cfg.CustomSegmentCode`, base-36 fns, `usp_GetOrCreateCustomSegmentCode`, `usp_ListCustomSegmentCodes`) | `audit_cpq_custom_codes.py` 11/11 |

**SPA:** editable-draft flow (Edit/Remove on draft lines → configurator seeded with saved
selections → save in place); per-grouping Custom modal with "Add Another Customization";
unresolved-items panel before submit; distributor "My Reviews" (reviewed revision +
Request Further Review + Confirm Order & download PDF); engineer custom-code mint UI +
"Download order PDF"; reference CSS + `.cfg`/`.summary`/`.opts`/`.plate` configurator
layout; jsPDF order document rendered from one `OrderRecord` (byte-identical for both
parties).

---

## 2. A4 — the governed custom-code model (the PN-adjacent piece)

**It MIRRORS, never edits, the authoritative PN.** `cfg.usp_AssembleConfiguredProduct`,
`dean_identifier`, and `stg.SegmentCombinationImport` are untouched. Custom codes live in
a SEPARATE table (`cfg.CustomSegmentCode`), one registry per grouping (WET_END_OPTIONS,
IMPELLER_OPTIONS, POWER_FRAME_OPTIONS, MOTOR_SPEC, BASEPLATE_OPTIONS, …).

- **Backward-read, collision-safe minting:** a new code = `encode(max(real ∪ custom)+1,
  width)`. Because every grouping's `SegmentValue` is fixed-width base-36 (`0-9A-Z`),
  lexical MAX == numeric MAX, so customs sit strictly above every real code. A future
  authoritative reload cannot silently collide, and the audit fails closed if any
  real∪custom collision is ever detected.
- **base-36 fidelity:** `cfg.fn_Base36Encode/Decode` mirror `docs/style.md` exactly
  (`encode(87265,4)='1VC1'`, `encode(1,4)='0001'`, overflow → NULL / fail-closed).
- **Family-wide reuse by spec-key** (SHA-256 of the normalized spec text).
- **Concurrency-safe:** mint is serialized with `sp_getapplock` + re-check under the lock.

---

## 3. Verification (commands + numbers)

Per-adjustment audits (each self-cleaning, run via `uv run`):
```
audit_cpq_a1  11/11   audit_cpq_a2  11/11   audit_cpq_a3  6/6
audit_cpq_a5  11/11   audit_cpq_a6  11/11   audit_cpq_custom_codes 11/11
```
A4 highlights (observed): WET_END realMax `1SYA`(84178) → first mint `1SYB`(84179),
reuse → same `1SYB`, next spec → `1SYC`; IMPELLER own sequence `0P`→`0Q`; BASEPLATE
(real max `ZZ`, 2-char space full) → **fail-closed 409**; authoritative Dean PN
`D770-0022-EE01-000S-00000-0000-0000` byte-identical before and after minting; 0
real-custom collisions.

**Fybroc regression gate** `uv run python scripts/run_all_fybroc_audits.py`:
`RESULT: ALL CORRECTIONS INTACT` (9/9). (Run after the A1/A2/A5/A6 batch and again after A4.)

**Isolation watermarks (frozen invariants, unchanged throughout):**
```
cfg.FeasibleConstraint                  : 4743
non-Dean cfg.SeriesFieldOption          : 3638
non-DEAN stg.SegmentCombinationImport   : 300608
DEAN stg.SegmentCombinationImport       : 140976   (A4 did NOT append here)
cfg.CustomSegmentCode real-custom collisions : 0
```

**SPA build:** `npm run build` → tsc strict + vite clean (jsPDF adds html2canvas/dompurify
chunks + a benign >500 kB chunk-size warning for this internal tool).

---

## 4. Known gaps / disclosed

- **non-DEAN `cfg.ConfiguredProduct` drifted 1196 → 1211** across the pass. NOT a Fybroc
  regression and NOT from any migration: the `resolve` endpoint accrues product-identity
  rows, and the A1/A5/A6 audits resolve Fybroc/Dean configs. The frozen *config* invariants
  (constraints/options/combinations) are unchanged and the Fybroc gate is 9/9.
- **BASEPLATE_OPTIONS cannot accept a custom code** — its real 2-char base-36 space is
  already full (`ZZ`). The mint fails closed (409) rather than overflow/collide; this is
  the correct, honest behavior. If baseplate customs are needed, engineering must widen
  that grouping's numbering (a source/authority change), which is out of scope here.
- **Custom code is a parallel mirror shown alongside the PN**, per owner decision; it is
  recorded in the review line's custom-spec text and the order document. The authoritative
  PN is never rewritten. Fybroc custom codes are supported by the same mechanism but
  untested here (Fybroc frozen; Dean-first).
- **Real Entra** remains U5; the pass runs on dev-mock auth. `spa/dist` is a gitignored
  build artifact (`npm install && npm run build`).

---

## 5. Completion-sequence demo (newadjustment.md)
Reopen draft → Edit Configuration (A1) → add multiple customization requests (A2) →
unresolved C/F list forces review (A3) → submit to the correct brand/site queue (U3) →
engineer resolves C/F price + mints governed custom code for the grouping (A4) →
completion gate requires lead time + resolved C/F (A5) → reviewed revision returned to the
distributor (A5) → Confirm Order (A6) → engineer notified → both retrieve the identical
PDF (A6). Dean/Fybroc queues stay isolated (U3); standard numbering regression intact
(Fybroc gate 9/9; authoritative PN byte-unchanged by A4).

---

## 6. Exit decision
**PASS.** All seven owner adjustments are built, each verified by its own self-cleaning
audit; the governed custom-code model mints collision-safe base-36 codes per grouping
without touching the authoritative PN; the Fybroc gate is 9/9 and frozen invariants are
unchanged. Ready to proceed to **U4** (the next SPA milestone) on explicit user go-ahead.

# F110 — Pending Engineering Decisions

Running log of decisions made provisionally during F110 (V5/V6 nomenclature
reconciliation) that need engineering confirmation before they're treated
as final. Each entry states what was decided *for now*, and what would
change it.

---

## ENGINEERING HAS RESPONDED (2026-08-20): V6 is authoritative over V5

**Update:** this is now formally part of a broader decision - see
`docs/milestones/FYBROC_AUTHORITATIVE_SOURCE_PROMOTION.md`. Rev0.3 also
replaces `Fybroc Attributes and Constraints.xlsx` as the authoritative
configuration source, not just V6 replacing V5 for nomenclature. Kept
here in full since this file is the detailed reasoning trail for the
nomenclature-specific items below; the promotion doc is the short,
formal record of the decision itself.

This supersedes the "merge both as one source of truth" framing in item 0
below - engineering gave a simpler, more decisive rule than the interim
working hypothesis. **Where V5 and V6 differ, V6 wins.**

This resolves every item below that was genuinely a "which version is
correct" question - see each item's updated status.

**What this does NOT automatically resolve:** whether V6 itself is
structurally complete. "V6 is authoritative" is a different question
from "does V6 fully cover everything V5 did." Two concrete open cases:
`Seal Assembly - Horizontal` has no Vertical counterpart in V6 at all,
and V6's `Smart Number` is explicitly titled "Fybroc Horizontal Part
Number," implying a Vertical builder may exist elsewhere and hasn't
been located. Working assumption going forward: V6 wins wherever it has
content; a gap in V6 still needs to be found and filled, not silently
dropped just because V6 is now authoritative. Flagging this interpretation
rather than assuming it's obviously correct - it's the sensible default,
not a confirmed instruction from engineering.

---

## 0. Governing policy: V5 + V6 as one merged source of truth (2026-08-20)
**SUPERSEDED by the engineering response above.** Kept here for the
reasoning trail, not as the active policy.

**Decision:** V5 and V6 are not "old vs. new, pick one." They're used
together, interwoven, as one combined source of truth going forward:

- V6's role is specifically to compensate for gaps in V5 - primarily
  Horizontal/Vertical orientation-specific configuration and adders V5
  didn't distinguish, plus any configuration/adder coverage V5 was
  missing outright.
- Where V5 already has an established hex code for a value/constraint,
  it stays authoritative.
- Where V6 introduces something V5 simply doesn't have, V6's hex code
  is adopted.
- Both are tied back to the same underlying constraints (`MAIN`, the
  per-series sheets) regardless of which workbook a given value's hex
  code actually comes from.

**What this resolves, as a working hypothesis - not yet a confirmed
fact about these specific sheets:** the two structural pairings F110.1
flagged `NEEDS_ENGINEERING_REVIEW` - `Pump Options - Vertical` and
`Options - Horizontal` - fit this pattern exactly: V6 adding an
orientation-specific breakdown V5's single combined sheet never had.
Read as ADDITIVE under this policy, not conflicting. Same logic applies
to `Seal Manufacturer` and `C-Face Adapter` (item 3 below) - V5 has
nothing there, so V6's hex codes are adopted by default, no conflict.

**What this does NOT resolve** - these are V6 doing the same job
differently, not filling a gap, so a policy default doesn't apply:
Series+Flange encoding (item 1) and the reworded values in item 3
(`"Mechanical Seal Included*"` vs `"Supplied by Fybroc"`, etc.) - those
still need an actual engineering answer.

**Scope note:** this governs how F110's classification results get
*used*, not what F110 itself is required to determine - the roadmap's
own F110 objective (classify every V5/V6 difference) is unchanged.
Directly relevant to F140 (Metadata Corrections & Publication) once we
reach it; recorded now so it isn't lost between here and there.

---

## 1. Series + Flange hex encoding — RESOLVED (2026-08-20)

**Was:** interim decision to keep V5's single hex letter approach
(`"1500 (ANSI)" -> "A"`) pending engineering input.

**Now:** engineering says V6 is authoritative. V6's split representation
(bare series number `"1500"` + separate "Flange Type" `"ANSI"`) is the
adopted approach. Neither field is itself a hex code, so **downstream
identifier-generation logic needs to derive a hex code from these two
fields some other way** - this is real follow-up work, not a closed
loop. Flagging this explicitly so it doesn't get lost: adopting V6's
representation is not the same as having a working replacement for the
hex code V5 used to provide directly.

---

## 2. Testing hex mapping — which version: RESOLVED. Actual codes: still open

**Which version to use:** resolved by "V6 is authoritative." V6's split
into "Performance Testing" and "Hydro Testing" (confirmed live in
`Smart Number`) replaces V5's single combined Testing field.

**Still open:** V5 has a Testing hex table inside `Attributes` (columns
21/22). V6 has no such columns there — the actual codes now live in V6's
dedicated `Testing` sheet, which hasn't been read/verified yet. Adopting
V6's *approach* is settled; confirming what its actual hex codes are is
still real work.

**Resolves when:** F110.4 (Testing rule diff) reads V6's `Testing`
sheet directly and documents its codes.

---

## 4. Possible missing Vertical part-number builder — OPEN, not resolved by V6-authoritative

V6's `Smart Number` sheet is explicitly titled "Fybroc Horizontal Part
Number" (found directly in the sheet, row 4). That phrasing implies a
separate Vertical equivalent should exist. Not located yet.

This is NOT a "which version wins" question, so engineering's V6-
authoritative answer doesn't resolve it - it's a "does V6 actually have
this at all" question. Needs a direct answer.

**Resolves when:** engineering confirms whether a Vertical part-number
builder exists elsewhere in V6, or whether `Smart Number` handles both
orientations despite the Horizontal-specific title.

---

## 3. Wording differences in Seal Assembly / Options / Motor Assy — RESOLVED (2026-08-20)

Found while scoping the option-list comparator for these three sheets
(structurally different from `Attributes` — each column is a field, each
row a valid option value, not a name→hex-code pair).

**Now resolved by "V6 is authoritative":** V6's wording is simply what's
used going forward. No further confirmation needed on any of these:

- Seal Assembly: `"Supplied by Fybroc"` (V6) replaces V5's `"Mechanical
  Seal Included*"`. `"NoSeal Single Seal Gland"` (V6) replaces V5's
  `"No Seal (Single Seal Gland by Fyboc)"` (note: "Fyboc" was a typo in
  the V5 source itself).
- Options: `"Not Included"` (V6) replaces V5's `"No Customer Nameplate"`.
- Motor Assy: `"IEC"` (V6) is adopted as a real Motor Class option
  alongside `"Imperial"`. `"Standard Offering"` (V6) replaces V5's
  `"Fybroc Choice*"` for Motor Manufacturer.
- `Seal Manufacturer` and `C-Face Adapter` (new V6 fields, no V5
  equivalent) - adopted, as already noted under the old item 0 policy;
  V6-authoritative doesn't change this outcome, just the reasoning.

---

*Add new entries above this line as they come up during F110. Move an
entry to a proper milestone doc (e.g. `F110_x_..._CORRECTION.md`, same
pattern as `F100_5_1`) once engineering actually confirms it — this file
is for tracking what's still open, not for recording settled facts.*
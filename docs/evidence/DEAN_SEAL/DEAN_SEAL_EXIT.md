# Dean Seal Configuration — Exit Evidence

**Source:** `workbooks/Dean/SealNumbering.xlsx` (Master + 7 permutation sheets).
**Scope decisions (owner):** Master is the authority for seal selection options;
Seal Chamber Config left as is (wet-end numbered field); Combined Table and the
per-Type sheets are NOT extracted; `C/F` is a populated placeholder, not an option;
the Seal Reference Table decides which sheet applies to a series; `C.F.`/`TBD`
prices are placeholders engineering determines at quote review (shown as call
factory); the seal code is part of the PN.

## Deliverables
| Item | What |
|---|---|
| `scripts/load_dean_seal_master.py` | Replaces DEAN seal options with each Master column's contiguous block from row 3 (junk cells below the block excluded). Called at the end of `d110_load_dean_config_v01.py` so a re-ingest keeps Master as authority. |
| `sql/38_Create_Dean_Seal_Spec.sql` + `scripts/load_dean_seal_spec.py` | `cfg.DeanSealSpec`: one row per coded permutation of the 7 sheets (`1.000"…3.000" Shafts`, `Misc.`) keyed by `SealRefKey` (= `cfg.DeanSealReference`) + SHA-256 combo hash → `SealCode`, price, `PriceStatus` (PRICED/CF/TBD/BLANK). 315,196 rows. |
| `src/api/dean_seal.py` | Shared key construction + `resolve_seal_spec` (series → ref sheet → code/price). |
| `src/api/dean_identifier.py`, `sql/23` | Seal code occupies its own PN slot between power-frame and flush groups: `D<A#>-<WetEnd>-<Trim><ImpOpts>-<Power>-<Seal>-<Flush…>-…`. Not Included → `000`; Included but unresolved → `TBD`. SQL branch is back-compatible (slot omitted if no `seal_code`). |
| `src/api/v2_routes.py` | Dean Seal price line from `DeanSealSpec` (numeric → charged; CF/TBD/blank/pending → C/F). Legacy Fybroc-style seal block gated off for Dean. |
| `scripts/audit_dean_seal.py` | 37 checks (below). |
| `audit_dean_revision.py`, `audit_cpq_u4.py` | Updated: seal fields exempt from custom→C/F check (Master owns them); U4 FeasibleConstraint watermark corrected 4743→4733 (4487 + 246, stale since D-R1). |

## Verification (numbers)
- Master option sets: 3,770 (series,size,field) sets equal the Master block; 0 `C/F` options in replaced fields; `GLAND_GASKET` only on the 13 `Misc.` series (62 sets). `SEAL_CHAMBER_CONFIG` 616 rows and `SEAL_OPTION` 365 rows untouched. DEAN SFO 50,478 → 63,641; seal STD cells 2,244 → 2,100 (a prior STD is kept only if the value exists in Master).
- `DeanSealSpec` per sheet (rows / priced / CF / TBD): 1.000" 21,916/52/9,054/948; 1.375" 21,916/350/14,904/924; 1.750" 21,916/312/14,904/6,132; 2.125" 21,916/119/14,913/6,316; 2.250" 21,916/572/14,669/6,035; 3.000" 22,408/211/17,041/2,440; Misc. 183,208/4/0/0 (all match the workbook).
- 1,050 random permutations (150/sheet) resolve back to their code; API PNs show the seal slot with python==SQL parity; priced vs C/F components as expected.
- Isolation: non-DEAN `SeriesFieldOption` 3,638, `FeasibleConstraint` 4,487, `ConstraintFieldMap` 28, `stg.SegmentCombinationImport` 300,608 — unchanged.
- No enforced DEAN constraint leg touches a replaced seal field (checked before the change), so no dead ends were introduced.
- Other audits: `audit_dean_revision` 15/15, `audit_dean_config` 28/0, `audit_cpq_a2` 11/11, `audit_cpq_u3` 20/20, `audit_dean_wet_end_resolve` 33/0.

## Known gaps / disclosures
1. **Seal slot position** (between power-frame and flush) and widths (3 chars shaft sheets, 4 chars `Misc.` and 492 extra 3.000" rows) were chosen by me; the PN seal slot is therefore variable width. Confirm.
2. **Source duplicates:** 12 identical permutations per shaft sheet (480 on 3.000") carry two different codes. The resolver returns the lowest code; engineering should dedupe the sheet.
3. **Seal Chamber Config:** the wet-end values (`Standard Bore Jacketed`, `Large Taper Bore`, …) are matched to the sheet's `Standard Bore`/`Large Bore` by prefix; values with no bore class (e.g. `NONE`) match no permutation → `TBD`. Heuristic, needs engineering confirmation.
4. **Unreachable sheet rows:** permutation rows using values not on Master (Ni-Resist stationary face, Inconel hardware, `FAS Type VTSMS - Double/Tandem`, `JC Type 5620PR - Double/Tandem`, `SIB/SIU - Pusher Wedge Seal`, `Type 8BITH/8-1T`, Lantern Ring `NONE`) cannot be selected since Master is authoritative. Conversely 9 Master seal types and all 4 Seal Manufacturers never appear in any sheet (selecting them → `TBD`).
5. **Series with ref `X`** (4 series) and any `Misc.` BLANK-price row resolve to `TBD`/C/F; engineering completes at review. `Misc.` has only 4 priced rows.
6. **Seal codependencies** (492 tuples) remain deferred (Option A); not part of this scope.
7. **Seal Manufacturer `Custom`** is now a literal Master option; custom seal code minting still returns 409 (no numbering width for a custom seal group).
8. Master junk cells differ from the row numbers in the instruction (see session notes); the contiguous-block rule was used and yields clean lists.

## Reproduce
```
uv run python scripts/load_dean_seal_master.py      # Master options (idempotent)
uv run python scripts/load_dean_seal_spec.py        # applies sql/38, loads spec/price
uv run python scripts/apply_sql23_assemble.py       # assembler with seal slot
# API on 127.0.0.1:8080, then:
$env:PYTHONPATH="."; uv run python scripts/audit_dean_seal.py
uv run python scripts/run_all_fybroc_audits.py      # port 8080 must be free
```

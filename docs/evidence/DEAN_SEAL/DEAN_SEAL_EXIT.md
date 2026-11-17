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
| `sql/39_Create_Dean_Seal_Sheet_Tables.sql` + `scripts/load_dean_seal_spec.py` | ONE table per permutation sheet (`cfg.DeanSealSpec_S1000/S1375/S1750/S2125/S2250/S3000/Misc`), PRIMARY KEY on the permutation hash and unique `SealCode`; `cfg.DeanSealSheet` maps each Seal Reference key to its table. Permutations that appear more than once on a sheet are quarantined in `cfg.DeanSealSpecCollision` (see Correction 2). The earlier combined `cfg.DeanSealSpec` (sql/38) was dropped. |
| `src/api/dean_seal.py` | Shared key construction + `resolve_seal_spec` (series → ref sheet → code/price). |
| `src/api/dean_identifier.py`, `sql/23` | Seal code occupies its own PN slot between power-frame and flush groups: `D<A#>-<WetEnd>-<Trim><ImpOpts>-<Power>-<Seal>-<Flush…>-…`. Not Included → `000`; Included but unresolved → `TBD`. SQL branch is back-compatible (slot omitted if no `seal_code`). |
| `src/api/v2_routes.py` | Dean Seal price line from `DeanSealSpec` (numeric → charged; CF/TBD/blank/pending → C/F). Legacy Fybroc-style seal block gated off for Dean. |
| `scripts/audit_dean_seal.py` | 37 checks (below). |
| `audit_dean_revision.py`, `audit_cpq_u4.py` | Updated: seal fields exempt from custom→C/F check (Master owns them); U4 FeasibleConstraint watermark corrected 4743→4733 (4487 + 246, stale since D-R1). |

## Verification (numbers)
- Master option sets: 3,770 (series,size,field) sets equal the Master block; 0 `C/F` options in replaced fields; `GLAND_GASKET` only on the 13 `Misc.` series (62 sets). `SEAL_CHAMBER_CONFIG` 616 rows and `SEAL_OPTION` 365 rows untouched. DEAN SFO 50,478 → 63,641; seal STD cells 2,244 → 0 (see Correction below: no seal STD seeds).
- `DeanSealSpec` per sheet (rows / priced / CF / TBD): 1.000" 21,916/52/9,054/948; 1.375" 21,916/350/14,904/924; 1.750" 21,916/312/14,904/6,132; 2.125" 21,916/119/14,913/6,316; 2.250" 21,916/572/14,669/6,035; 3.000" 22,408/211/17,041/2,440; Misc. 183,208/4/0/0 (all match the workbook).
- 1,050 random permutations (150/sheet) resolve back to their code; API PNs show the seal slot with python==SQL parity; priced vs C/F components as expected.
- Isolation: non-DEAN `SeriesFieldOption` 3,638, `FeasibleConstraint` 4,487, `ConstraintFieldMap` 28, `stg.SegmentCombinationImport` 300,608 — unchanged.
- No enforced DEAN constraint leg touches a replaced seal field (checked before the change), so no dead ends were introduced.
- Other audits: `audit_dean_revision` 15/15, `audit_dean_config` 28/0, `audit_cpq_a2` 11/11, `audit_cpq_u3` 20/20, `audit_dean_wet_end_resolve` 33/0.

## Correction 2026-08-26 (follow-up audit): options must follow the Seal Reference sheet and Seal Type
The first delivery offered the full Master list for every series, ignoring the Seal
Reference Table. Audit showed e.g. DL200 (ref `1.000" Shafts`) was offered 33 Seal
Types while its sheet carries 21 (20 on Master), `Misc.` series were offered 19 Seal Types not on their sheet, and inboard/outboard elastomers, hardware, gland style etc. also
exceeded the sheet. Selecting a Seal Type did not narrow anything, and the old
partial Pump-Constraints STD seeds (sleeve, faces, hardware, bushings…) pre-filled
fields and, through the permutation cascade, left a single Seal Type.
Fix:
- `dean_seal.filter_options` (called from `_apply_constraints`, Dean-only) keeps an
  option only if some permutation on the series' sheet carries it together with every
  other selected seal field, Seal Type included. Series with ref `X` are not narrowed.
- No STD seeds for the Master-replaced seal fields (`load_dean_seal_master.py`);
  `dean_seal.prune_seed` additionally drops any seeded seal set that is not one
  permutation of the sheet.
- `audit_dean_seal.py` section F (22 new checks): per sheet, Seal Type options ==
  sheet types ∩ Master (20/20/20/20/20/20 for the shaft sheets, 14 for Misc.); with a
  Seal Type chosen, every seal field's options == the sheet values for that type
  (4 types per sheet); Type + Configuration narrows further; seeds form a real
  permutation for all series. Audit now 59/59.

## Correction 2 (2026-08-26): per-sheet tables, permutation collisions, no seal default
- Each sheet is its own permutation space, so each now has its own table with the permutation hash as PRIMARY KEY. A colliding permutation cannot be stored in a sheet table. All its rows go to `cfg.DeanSealSpecCollision` and the resolver returns seal code `TBD` (status pending, detail lists the colliding codes such as KNZ/KRT, Seal line shows C/F) instead of picking one. Verified through the API (PN `…-1HWL-TBD-01000-…`, parity true).
- Counts (unique permutations / quarantined rows): 1.000"–2.250" 21,892 / 24 each; 3.000" 21,424 / 984; Misc. 183,208 / 0. Table rows + quarantined rows equal the workbook coded rows on every sheet.
- Seal configuration has no default: 0 STD rows on any Master-replaced seal field, and a fresh configuration seeds none of them for any series.
- `audit_dean_seal.py` is now 87/87. `audit_dean_revision` 15/15, `audit_dean_wet_end_resolve` 33/0, `audit_cpq_a2` 11/11, `audit_cpq_u4` 17/17. The Fybroc gate was NOT re-run for this change (no shared/Fybroc code touched since the last passing gate; non-DEAN watermarks re-verified by the audit).

## Correction 3 (2026-08-26): collisions fixed at load (earlier row kept), not quarantined
Owner rule: when the same permutation (same values across every column) appears more than once on a sheet, the EARLIER row is retained and later rows are discarded; permutation numbers are re-sequenced.
- `load_dean_seal_spec.py` now keeps the first row of each permutation (with its code and price) and discards later ones, logging them in `cfg.DeanSealSpecDiscarded` (with the retained code). `cfg.DeanSealSpecCollision` and the `TBD` collision branch are gone. Each sheet table also stores `PermutationNo`, re-sequenced 1..N in sheet order; retained rows keep their codes, so codes never move.
- Result: every shaft sheet = 21,904 unique permutations (1.000"–2.250": 12 discarded each; 3.000": 504 discarded, 480 duplicated permutations of which 12 appeared three times); Misc. 183,208, none discarded. All 564 discarded rows had no price, as did the rows kept, so no price data was lost.
- Checked in the source: permutation NUMBERS are already unique on every sheet (no number collisions to renumber); the collisions were identical values under different numbers/codes. The 564 discarded codes (e.g. KRT, KN9) are no longer assigned to any permutation.
- Selecting a previously colliding permutation now resolves to the earlier row's code (`audit_dean_seal` 101/101, incl. a check that every discarded row is later than the retained one and its code is absent from the table).

## Correction 4 (2026-08-26): Seal Option and Seal Manufacturer do not drive the PN
The seal PN slot is now computed only from the seal configuration fields and the series' Seal Reference sheet. Seal Option and Seal Manufacturer are not permutation fields and no longer affect the code: no seal configuration field selected -> `000`; some selected but unresolved -> `TBD`; resolved -> the sheet code, whatever Seal Option / Seal Manufacturer say. Seal Option still gates the seal PRICE line (charged only when Included); that is pricing, not the PN. `audit_dean_seal.py` now 111/111 (25 permutations x 8 option/manufacturer variants per sheet give identical codes; API: 6 option x manufacturer variants give one identical PN). Other audits unchanged and passing (revision 15/15, config 28/0, wet_end_resolve 33/0, U3 20/20, U4 17/17, A2 11/11). Fybroc gate not re-run (Dean-only code paths).

## Correction 5 (2026-08-27): seal STD and offered options from Pump Constraints
Owner: seal configuration DOES have STD values; `Pump Constraints` (PumpConfiguration_Logic_0.1) holds the STD and the selectable options for every series. Supersedes the "no seal default" rule of Corrections 1-3.
- **Options and STD per model** (`load_dean_seal_master.py`, also called by `d110`): a (series, size) offers a seal option only if Pump Constraints offers it for that model AND Master lists it; STD = the Pump Constraints STD. Master remains the vocabulary: Pump Constraints spellings are mapped (`Hastelloy C`->`Hastelloy`, `420 SS`->`420`, `420 SS Hardened`->`420 Hardened`). Values with no Master equivalent are not loaded: `Custom` (all seal fields; Custom is the C/F placeholder, not an option) and `Tandem Component` (Seal Configuration, 103 models; STD on 9). Result: 3,173 option sets, 2,145 STD cells, every one of the 206 models has seal STD values. Gland Gasket (not in Pump Constraints) keeps the Master options for Misc. series, no STD.
- **Defaults vs drivers** (`dean_seal.py`): Seal Configuration and Seal Type drive the seal; their value (STD or chosen) always narrows the other seal fields. The other STD values are per-field defaults that do not have to form one permutation together (e.g. shaft-sheet series default Outboard Rotating Face `Carbon`, which only double seals use). A field still at its STD never narrows other fields; once changed it does. Without this, the shaft-series defaults left exactly one selectable Seal Type (measured: 1 of 16-17).
- **Seed**: a fresh configuration seeds the Pump Constraints seal STD; drivers must form a permutation, each other default must be valid with the drivers, otherwise it is dropped. 23 models have dropped seeds, all on `Misc.` sheets: RSWA (Inboard Elastomer `Kalrez`, Lantern Ring `Not Required`), RTA3146 (Seal Type `JC Type S8B1/8-1T`, not on the Misc. sheet; 9 models), RWA4166 / RWA4206 (Lantern Ring `Not Required`, Sleeve `316 SS`; sheet has NONE), RWAV4166 (Lantern Ring `Not Required`).
- **Picking a Seal Type** clears defaults that do not fit it (reported in `dropped_fields`, not as conflicts). User-changed values still raise conflicts as elsewhere.
- **Stale stored products** (`sql/23`, DEAN branch only): a configured product persisted under an earlier rule could hold the same configuration signature with an old PN, so the API returned that old PN (parity failures in `audit_dean_wet_end_resolve`, e.g. `...-000-...` vs `...-TBD-...`). The Dean branch now retires the stale row's signature (its PN, SKU and quote references stay) and creates the current PN. Fybroc branch unchanged.
- Verified: `audit_dean_seal.py` 115/115 (new: option sets == Pump Constraints offer in Master spelling; STD == Pump Constraints STD; seed per series; defaults never narrow Seal Type; picking a type gives no seal conflicts and a sheet permutation). `audit_dean_wet_end_resolve` 33/0, `audit_dean_revision` 15/15, `audit_dean_config` 28/0, `audit_cpq_u3` 20/20, `audit_cpq_u4` 17/17, `audit_cpq_a2` 11/11.

## Known gaps / disclosures
1. **Seal slot position** (between power-frame and flush) and widths (3 chars shaft sheets, 4 chars `Misc.` and 492 extra 3.000" rows) were chosen by me; the PN seal slot is therefore variable width. Confirm.
2. **Source collisions** (same selections, different codes and permutation numbers): 12 permutations on each of the 1.000"–2.250" sheets and 480 on 3.000" (1,104 rows total, none on `Misc.`). Resolved at load by keeping the earlier row (see Correction 3).
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

- Correction 5 Fybroc gate: `run_all_fybroc_audits.py` ALL CORRECTIONS INTACT (9/9), run because sql/23 is shared.

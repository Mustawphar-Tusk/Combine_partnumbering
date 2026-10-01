# Fybroc 1500 Pricing — Series Attribution Correction (Vibration/Sound Testing)

**Milestone slice:** Correct the Rev0.4 `1500 Pricing` series attribution — the
1500-series Vibration Testing and Sound Level Testing adders were missing from the
published pricing (effectively recorded only under 5500). Re-publish so the 1500
testing rows are present and price correctly.
**Family:** FYBROC (PumpFamilyId 2, PriceBook 2) — frozen at F180; DEAN (1) untouched.
**Date:** 2026-08-26
**Mode:** FULL (authoritative pricing re-publication; cross-family blast radius).
**New active pricing publication:** `FYBROC-REV04-MERGE-20260826-V2` (PriceBookVersionId 9),
superseding `FYBROC-REV04-MERGE-20260914-V1`.

---

## 1. Deliverables & exit-gate criteria

**Objective:** The Rev0.4 `1500 Pricing` datasheet is authoritative for the **1500
series**. Every block of that sheet (base + adders + testing) must be attributed to
1500. Specifically, Vibration Testing and Sound Level Testing (1500) must be published
and resolve to the sheet price; 5500's own testing rows (from the 5500 sheet) must stay.

**Criteria:**
1. `1500` Vibration/Sound Testing present in the publication and priced to the sheet value.
2. 5500's legitimate pricing not clobbered.
3. Cross-family regression `run_all_fybroc_audits.py` = ALL CORRECTIONS INTACT.
4. Dean isolation: Dean pricing rules unchanged.

---

## 2. Investigation & root cause (not what the symptom suggested)

The user reported "series mistakenly recorded as 5500 instead of 1500." The precise
finding, from reading the source and the DB:

- The Rev0.4 `1500 Pricing` sheet stamps **Series = `1500`** in every block's Series
  column (the Seal and Flush blocks have no Series column — they're series-less and get
  stamped to the adopted series during the merge). So the whole sheet is authoritative
  for **1500**.
- The `5500 Pricing` sheet **legitimately** has its own Sleeve / Performance / Vibration /
  Sound / Flush / Flange / Mounting / Coupling / Tailpipe blocks (Series = `5500`), so the
  DB's 5500 rows for those are correct — not mis-stamped 1500 data.
- **The real defect was data staleness, not a wrong series code.** In the previously
  published set, `VIBRATION_TESTING` and `SOUND_LEVEL_TESTING` existed **only under 5500**;
  the 1500 rows were simply **absent**. Re-running the current compiler produces BOTH
  (`1500: 57` + `5500: 57` each). The compiled export grew from 52,378 → 52,492 candidates
  (+114 = the two restored 1500 blocks). `PERFORMANCE_TESTING` already had both 1500 and
  5500, which is why it priced correctly and these two did not. The publication simply
  pre-dated the compiler state that extracts the 1500 testing blocks.

So the fix is a **recompile → re-merge → re-publish**, not a code change.

---

## 3. The correction (data re-publication, family-safe)

```
# recompile Rev0.4 pricing (restores 1500 vibration/sound)
python scripts/compile_fybroc_rev04_pricing.py --all --found-only
# re-merge over the Price-Estimator baseline (adopted series 1500 + 5500)
python scripts/merge_rev04_over_price_estimator.py
# publish a NEW FYBROC pricing version (supersede-not-delete)
python scripts/publish_fybroc_combined_pricing.py \
    --input exports/fybroc_merged_pricing.json \
    --version-code FYBROC-REV04-MERGE-20260826-V2 --effective-from 2026-08-26
```

Publication result: **56,355 rules** (was 56,241; +114), Found 56,202 / C/F 153, 228,005
conditions. The publish proc superseded only the FYBROC price book's current version
(set `IsCurrent=0` on the old, inserted the new with `IsCurrent=1`) — **no cross-family
delete**, so DEAN's price book is untouched.

---

## 4. Verification (commands + numbers)

### 4.1 Per-series attribution corrected (DB, new current publication)
| Component | Before (series:count) | After |
|---|---|---|
| VIBRATION_TESTING | `5500: 57` | **`1500: 57, 5500: 57`** |
| SOUND_LEVEL_TESTING | `5500: 57` | **`1500: 57, 5500: 57`** |
| PERFORMANCE_TESTING | `1500: 57, 5500: 57` | unchanged |
| SLEEVE | `1500: 114, 5500: 95` | unchanged |

### 4.2 Live price matches the authoritative sheet
`1500 / 1x1.5x6`: Vibration/Sound `Not Included` = **$0**, `Non-Wit` = **$1395**,
`Wit` = **$3045**. `1500 / 3x4x10`: `$0 / $1761 / $3888`. All equal the sheet's DH–DK
(Vibration) and DM–DP (Sound) values exactly. Before the re-publish these lines were
**C/F** (no 1500 rows existed).

### 4.3 Guard added (permanent)
`scripts/audit_fybroc_pricing.py` extended with 12 sheet-derived Vibration/Sound
assertions (2 sizes × 3 options × 2 components). Sheet read widened to column 126 so the
DH–DP testing blocks are covered. Audit now **47 passed, 0 failed** (was 35).

### 4.4 Cross-family regression + isolation
```
Get-NetTCPConnection -LocalPort 8080 -State Listen | %{Stop-Process -Id $_.OwningProcess -Force}
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\run_all_fybroc_audits.py
```
→ **ALL CORRECTIONS INTACT (9/9):** selections, feasible constraints (44/44), motor
constraints (91/0), identifier parity (44/0), BOM (38/0), quote (22/0), free config (32/0),
**pricing (47/0)**, motor CPQ (37/0).

**Isolation:** DEAN current pricing rules = **9874** before and after (unchanged). FYBROC
new current = 56,355. The old FYBROC version (56,241) is retained non-current. No Dean
write. `imports OK`.

---

## 5. Exit-gate decision — PASS

| # | Criterion | Result |
|---|---|---|
| 1 | 1500 Vibration/Sound present + priced to sheet | **PASS** — audit 47/0, live $0/$1395/$3045 |
| 2 | 5500 pricing not clobbered | **PASS** — 5500 counts unchanged |
| 3 | run_all_fybroc_audits ALL CORRECTIONS INTACT | **PASS** — 9/9 |
| 4 | Dean isolated (9874 unchanged) | **PASS** |

---

## 6. Known gaps / disclosures

- This was a **data staleness** correction (re-publication), not a code bug — the compiler
  already extracted the 1500 testing blocks. The guard (audit §4.3) now prevents the 1500
  testing attribution from silently regressing in a future publication.
- `FLANGE_TYPE` is 1500-only (36 rows) in the publication; 5500 Flange Type is a distinct
  block on the 5500 sheet (its rows are present under 5500 via the 5500 blocks). No change.
- 153 rows remain `call_for_price` by source (unpriced combos) — honest C/F, unchanged.
- The previous publication `FYBROC-REV04-MERGE-20260914-V1` is retained (IsCurrent=0) for
  lineage; it is not deleted.

---

## 7. Reproducibility — exact commands
```
python scripts/compile_fybroc_rev04_pricing.py --all --found-only
python scripts/merge_rev04_over_price_estimator.py
python scripts/publish_fybroc_combined_pricing.py --input exports/fybroc_merged_pricing.json --version-code FYBROC-REV04-MERGE-20260826-V2 --effective-from 2026-08-26
.\.venv\Scripts\python.exe scripts\audit_fybroc_pricing.py
$env:PYTHONPATH="."; .\.venv\Scripts\python.exe scripts\run_all_fybroc_audits.py
```

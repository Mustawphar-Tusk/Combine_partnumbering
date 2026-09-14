# Rev0.4 vs Price-Estimator — pricing difference

_Generated 2026-09-14T19:53:45.805889+00:00_

## Adoption model (option 2b)

- Rev0.4 pricing is adopted **only for series 1500 and 5500** (both largely complete per engineering). All other series keep their Price-Estimator prices.

- Within 1500/5500: a Rev0.4 **determined** price (`found`) updates the price; a Rev0.4 **C/F (Contact Factory)** does not overwrite — the existing Price-Estimator price is retained where one exists; otherwise the configuration is Contact-Factory (no priced row; runtime default).

- The Price-Estimator baseline (`FYBROC-CONFIG-20260807-V3`) contained only BASE_PUMP + SEAL and only horizontal series (1500, 1530, 1550, 1600, 1630, 1650, 2530, 2580, 2630, 3000) — no 5500 and no other components. So 5500 and every non-BASE/SEAL component are **new** from Rev0.4; 1500 BASE_PUMP is a true overlay; 1500 SEAL is superseded by the Rev0.4 seal table (decision a).


## Summary

| Class | Meaning | Rows |
|-------|---------|------|
| changed | 1500 BASE_PUMP: Rev0.4 price differs from Price-Estimator | 0 |
| unchanged | 1500 BASE_PUMP: Rev0.4 price equals Price-Estimator | 109 |
| retained_v3 | 1500 BASE_PUMP: no Rev0.4 determined price, kept Price-Estimator | 21 |
| superseded_by_rev04 | 1500 SEAL: V3 price replaced by Rev0.4 seal table | 646 |
| new_rev04 | priced only in Rev0.4 (5500 + new components) | 54635 |

### CHANGED — 1500 BASE_PUMP (Price-Estimator → Rev0.4)

_(none — all matched 1500 base prices were unchanged)_

### RETAINED — 1500 BASE_PUMP kept at Price-Estimator (no Rev0.4 determined price)

| Size | Material | Retained price |
|------|----------|---------------:|
| 1.5X3X10 | VR-1V BPO/DMA | 27,166 |
| 1.5X3X6 | VR-1V BPO/DMA | 15,145 |
| 1.5X3X8 | VR-1V BPO/DMA | 24,440 |
| 10X12X16 | VR-1V BPO/DMA | 159,195 |
| 1X1.5X6 | VR-1V BPO/DMA | 14,369 |
| 1X1.5X8 | VR-1V BPO/DMA | 17,235 |
| 1X2X10 | VR-1V BPO/DMA | 26,013 |
| 2X3X10 | VR-1V BPO/DMA | 27,999 |
| 2X3X13 | VR-1V BPO/DMA | 39,076 |
| 2X3X6 | VR-1V BPO/DMA | 15,878 |
| 2X3X8 | VR-1V BPO/DMA | 25,313 |
| 3X4X10 | VR-1V BPO/DMA | 34,319 |
| 3X4X13 | VR-1V BPO/DMA | 44,592 |
| 3X4X8 | VR-1V BPO/DMA | 26,961 |
| 4X4X10 | VR-1V BPO/DMA | 39,273 |
| 4X6X10 | VR-1V BPO/DMA | 43,482 |
| 4X6X13 | VR-1V BPO/DMA | 54,311 |
| 6X8X13 | EY-2 | 0 |
| 6X8X13 | VR-1V BPO/DMA | 80,704 |
| 8X10X15 | EY-2 | 0 |
| 8X10X15 | VR-1V BPO/DMA | 100,284 |

### UNCHANGED — 1500 BASE_PUMP identical in both (109 rows)

_Listed in the machine-readable classification; omitted here for brevity._

### SUPERSEDED — 1500 SEAL V3 prices replaced by Rev0.4 seal table (646 rows)

Per decision (a), the Rev0.4 mechanical-seal pricing table (series-independent, keyed by size + seal mfg/option/type/materials/elastomers) supersedes the Price-Estimator 1500 seal prices. The old V3 1500 seal rows are not carried into the new publication.

### NEW — priced only in Rev0.4 (by component)

| Component | New priced rows |
|-----------|----------------:|
| TAILPIPE | 46000 |
| SEAL | 4102 |
| COUPLING | 1878 |
| BASEPLATE | 564 |
| MOTOR | 290 |
| FLUSH | 228 |
| SLEEVE | 209 |
| BASE_PUMP | 117 |
| PERFORMANCE_TESTING | 114 |
| PUMP_ELASTOMERS | 114 |
| HYDROTEST_CERTIFICATE | 114 |
| PUMP_MATERIAL_ADDER | 109 |
| GLAND_HARDWARE | 95 |
| COUPLING_GUARD | 76 |
| IMPELLER_BALANCE | 76 |
| BEARING_OPTION | 57 |
| VIBRATION_TESTING | 57 |
| SOUND_LEVEL_TESTING | 57 |
| SHAFT_MATERIAL | 38 |
| POWER_FRAME_HARDWARE | 38 |
| CASING_HARDWARE | 38 |
| BASEPLATE_HARDWARE | 38 |
| CYCLONE_SEPARATOR | 38 |
| CASING_DRAINS | 38 |
| SUCTION_DISCHARGE_TAPS | 38 |
| SEAL_GUARD | 38 |
| FLANGE_TYPE | 36 |
| C_FACE_ADAPTOR | 19 |
| MOUNTING_PLATE | 19 |

## Notes

- `new_rev04` rows include both series 1500 and 5500. Series-independent Rev0.4 tables (SEAL, and family-wide adders: pump elastomers, hydrotest, impeller balance) were stamped to **both** adopted series so they only apply to 1500/5500.

- Contact-Factory (C/F) configurations are NOT stored as priced rows: an unpriced configuration resolves to call-for-price at runtime by default. Only Rev0.4 `found` prices were merged.

- Full machine-readable classification: `exports/fybroc_merge_classification.json`.


# D120 — Dean Pricing & Adders: Design

**Date:** 2026-08-26
**Milestone:** D120 — Dean Pricing & Adders
**Status:** DESIGN (pre-implementation). Records the pricing model, sources,
component scheme, and load/resolve plan agreed with engineering before coding.

---

## 1. Authority & source precedence (engineering-confirmed)

1. **`Dean Pricing Matrix.xlsx` is authoritative** for all Dean pricing.
2. **`Dean Data Sheet Rev 2.xlsm`** is the fallback where the Matrix is silent.
3. **C/F (Contact Factory)** only when both are silent.

Every published price rule records **which source** supplied it (Matrix vs Rev2)
in its lineage, so a reviewer can see any fallback. The Matrix `Pricing`-vs-Rev2
overlap was verified identical in task 2 (base pump 107/107, couplings 626/626),
so fallback never contradicts the Matrix — it only fills gaps.

## 2. Price composition (engineering-confirmed)

```
total = base list price          (row by Series + Size + Pump Material)
      + Σ |option adder|          (for each selected option that has an adder)
      + coupling list             (by Series + Frame + Coupling)
      + baseplate list + Σ lug adders
      + shaft config adder        (where the Matrix prices it)
```

Rules:
- **Pump Material selects the base row** — the base list price is absolute per
  (series, size, material), NOT an adder (DL200 1x1.5x6 (22) D,I. = $3,401;
  (50) 316 S.S. = $6,890).
- **Adders are ADDED to the base, using the ABSOLUTE VALUE** — the Matrix stores
  some adders negative; the sign is ignored (`-170.05` contributes `+170.05`).
- **Adders apply only when the pump HAS a base price.** A pump with no base list
  (e.g. the two DEANLINE 0.75x0.75 / 1.5x1.5 sizes) is **C/F as a whole**; adders
  are not applied standalone.

## 3. Matrix coverage (task 2 findings)

| Component | Matrix sheet | Key | Rows |
|-----------|--------------|-----|------|
| Base pump | Std Options (E–J) | Series, Size, Material → Pump List Price | 288 across 31 series |
| Option adders (29 groups) | Std Options (K…) | Series, Size, Material(base row) → per-option delta | ~29 field groups |
| Couplings | COUPLINGS | Series, Frame, Coupling → List | ~630 |
| Baseplates + 6 lug adders | Base Plates | Series, FrameType, FrameSize, BaseplateType, Material → List; lug groups Not Required/Required | 1067 |
| Shaft config | Shaft Configuration | Series, Material, ShaftMaterial × config → adder | 60 priced ('x'/blank = applicability) |

29 adder groups all map to Dean field codes; 6 via alias (Seal Chamber
Configuration→SEAL_CHAMBER_CONFIG, Impeller Wear Ring→IMPELLER_WEAR_RING_MATERIAL,
Oiler→OILER_OPTIONS, Min Flo Bushing→MIN_FLO_BUSHING, Paint→PAINT_OPTIONS, Aux
Nameplate→AUXILLARY_NAMEPLATE).

**Not priced by the Matrix:** motor, mechanical seal → fall back to Rev 2, else
C/F.

## 4. Vocabulary normalization (load-side)

The Matrix uses abbreviated material names (`(22) D,I.`, `(40) C.S.`,
`(50) 316 S.S.` and inconsistently `(50) 316 S/S`, `(41) 11-13 (CR)`) vs the D110
`PUMP_MATERIAL`/`CASING_MATERIAL` option values (`(22) Ductile Iron`, `(40) Cast
Steel`, `(50) 316 S/S`, `(41) Cast Steel (420 SS Trim)`). The compiler normalizes
Matrix material spellings to the canonical D110 option values so price rows join
to configured selections (the pricing analogue of the D110 SEAL_TYPE / Barrier
Plan casing normalization). Normalization is table-driven and logged; any Matrix
material that cannot be mapped is reported, not silently dropped.

## 5. Infrastructure reuse — NO schema migration

Pricing is already family-scoped at `price.PriceBook.PumpFamilyId`
(`UNIQUE(PumpFamilyId, PriceBookCode)`). Publishing `@FamilyCode='DEAN'` creates/
uses the `DEAN_STANDARD` pricebook (PumpFamilyId=1) with its own version chain;
the Fybroc `FYBROC_STANDARD` book/version is untouched. An empty `DEAN_STANDARD`
seed already exists (`sql/05`). **No `price.*` schema change is needed** (unlike
D110's constraint tables).

Reused pipeline: **compiler → candidates JSON → `publish_compiled_pricing()` →
`stg.PricingExtract` → `price.usp_PublishPricingFromStaging` → `price.PriceRule` +
`price.PriceCondition`**, with `@FamilyCode='DEAN'`, a new `VersionCode`
(`DEAN-MATRIX-<date>-V1`), superseding the empty DEV1.

**Load-bearing invariant preserved:** the runtime resolver filters by
`PriceBookVersion.IsCurrent=1` + SeriesCode (no family filter), relying on
SeriesCode global uniqueness. Dean series (RA2096, DL200, …) do not collide with
Fybroc series (1500, 5500, …); the compiler will assert no Dean SeriesCode
collides with a Fybroc one before publishing.

## 6. Component-code scheme

| Component | ComponentCode | Keyed by (SourceSeriesCode / SourceSizeValue / SourceOptionValue + conditions) |
|-----------|---------------|-------------------------------------------------------------------------------|
| Base pump | `BASE_PUMP` | Series, Size, Pump Material |
| Option adder (per field) | `OPTION_ADDER` | Series, Size, + conditions FieldCode=<code>, Value=<option> |
| Coupling | `COUPLING` | Series, + conditions Frame, Coupling |
| Baseplate | `BASEPLATE` | Series, + conditions FrameType, FrameSize, BaseplateType, Material |
| Lug adder | `BASEPLATE_LUG` | Series, + conditions lug field + Required |
| Shaft config | `SHAFT_CONFIG` | Series, + conditions Material, ShaftMaterial, ShaftConfiguration |

Decision: use a **single generic `OPTION_ADDER` component** carrying the driving
field as a `PriceCondition` (FieldCode/ComparisonValue), rather than 29
Fybroc-style per-field ComponentCodes. This keeps the Dean resolver generic (one
adder lookup that iterates the config's selected fields) and avoids polluting the
Fybroc-specific `ADDER_COMPONENTS` list in `v2_routes.py`.

## 7. Runtime resolve (Dean-side, Fybroc-safe)

The existing `v2_routes.py` `ADDER_COMPONENTS`/`MULTI_COMPONENTS` are Fybroc field
codes. For Dean, add a **family-aware Dean pricing path** that:
1. Prices `BASE_PUMP` by series+size+material (base row).
2. Only if base found, iterates the configured option selections and looks up an
   `OPTION_ADDER` rule per (series, size, field, value), summing `|amount|`.
3. Prices `COUPLING`, `BASEPLATE`(+lugs), `SHAFT_CONFIG` by their conditions.
4. Marks any missing component C/F; honest `PricingStatus`.

The Fybroc resolve path is left byte-for-byte unchanged (guarded by the gate).
Whether this is a new branch keyed on family or a small generic helper is an
implementation detail settled in task 4; the constraint is **zero Fybroc change**.

## 8. Verification (per milestone-exit-audit steering)

- `scripts/audit_dean_pricing.py`: for representative (series, size), a resolved
  Dean pump total = base + Σ|adders| (+coupling/baseplate/shaft); every priced
  line has lineage + amount matching the Matrix; adders apply only for selected
  options and only when a base price exists; honest C/F on gaps; deterministic.
- `scripts/run_all_fybroc_audits.py` → ALL CORRECTIONS INTACT 7/7; Fybroc price
  rows + counts unchanged (isolation check).

## 9. Known gaps to report at exit

- Motor + seal pricing: from Rev 2 if present, else C/F (Matrix does not price
  them). Report coverage.
- DEANLINE 0.75x0.75 / 1.5x1.5: no base price in the Matrix → C/F.
- Shaft config is mostly applicability ('x'/blank); only 60 priced cells load as
  adders.
- Any Matrix material spelling that fails normalization (expected: none).

---

## 10. Baseplate-type + material mapping (engineering-confirmed 2026-08-26)

- **Matrix "Economy" baseplate type = config "Formed"** (Dean Data Sheet Rev 2).
  Engineering-confirmed. So the baseplate-type normalization at load:
  `Economy -> Formed`, `ANSI -> ANSI`, `API -> API`, `Support Base -> Support Base`.
- **Baseplate price key** = Baseplate Type (normalized) + **Drip Pan** (Steel /
  Stainless — the disambiguator, from the Matrix "…w/ SS Drip Pan" material and the
  `Formal Quote!C30` formula) + mounting (C-Face / Yoke where present).
- **Lugs are descriptive, no separate priced adder** (Matrix lug columns are 'X'
  applicability; `Formal Quote!C30` lists Required lugs in the baseplate line).
- With Economy=Formed + Drip Pan, baseplate is FULLY priceable; the only residual
  is 1 source anomaly (RTA3146 Economy 326TS has two Formed-Steel prices) — flag,
  do not silently pick.

## 11. Authoritative principle (2026-08-26)

The Dean Data Sheet Rev 2 **macros AND formulas are authoritative over all Dean
configuration** (not only pricing). Implemented behaviors derive from
`docs/evidence/D100/DEAN_DATASHEET_VBA_LOGIC.md`:
- Pump Configuration gates Baseplate/Coupling/Motor presence (Sheet1 cascade).
- Baseplate priced by Type + Drip Pan; lugs descriptive.
- Quote math: Net = List×(1−Discount); Extended = Qty×Net; Total = ΣExtended.
- PN assembly = `Smart Number!B5` segment structure (D130).
- Seal via the seal authority (external DB), else C/F (Matrix does not price seal).

OPEN SCOPE DECISION (awaiting user): Pump Configuration gating enforced in the
D110 config model vs applied only as a D120 pricing gate.

"""D120 - compile Dean pricing from the AUTHORITATIVE Dean Pricing Matrix.xlsx
into a candidates JSON for the existing pricing publisher
(src/pricing_engine/publisher.py -> publish_compiled_pricing).

Coverage (Matrix sheets):
  * Std Options : BASE_PUMP (base list per Series+Size+Pump Material) +
                  OPTION_ADDER (per selected option, |delta| on top of base)
  * COUPLINGS   : COUPLING (Series+Frame+Coupling)
  * Base Plates : BASEPLATE (Series+FrameType+FrameSize+BaseplateType+Material)
                  + BASEPLATE_LUG (per lug field, Required)
  * Shaft Config: SHAFT_CONFIG (Series+Material+ShaftMaterial+Configuration) - only
                  the numerically-priced cells

Engineering-confirmed pricing model (see docs/evidence/D120/DEAN_D120_DESIGN.md):
  total = base list (by Series+Size+Pump Material)
        + Σ |option adder| (selected options; adder SIGN IGNORED -> abs value)
        + coupling + baseplate(+lugs) + shaft config
  Adders apply ONLY when a base price exists. Missing -> C/F (handled at runtime).

Material vocabulary is normalized to the D110 canonical option values so price
rows join to configured selections.

Output: exports/dean_pricing_matrix.json  {"issue_count":0,"candidates":[...]}
Then publish:
  python scripts/publish_dean_pricing.py --version-code DEAN-MATRIX-<date>-V1 \
         --effective-from YYYY-MM-DD
"""
from __future__ import annotations

import json
import openpyxl
from openpyxl.utils import get_column_letter
from pathlib import Path

WB_PATH = Path("workbooks/Dean/Dean Pricing Matrix.xlsx")
WORKBOOK = "Dean Pricing Matrix.xlsx"
OUT = Path("exports/dean_pricing_matrix.json")
M023 = Path("exports/m023_dean_source_reconciliation.json")
CURRENCY = "USD"
FAMILY = "DEAN"

# Std Options adder group label -> canonical Dean field code (6 aliases + direct).
ADDER_LABEL_ALIASES = {
    "seal chamber configuration": "SEAL_CHAMBER_CONFIG",
    "impeller wear ring": "IMPELLER_WEAR_RING_MATERIAL",
    "oiler": "OILER_OPTIONS",
    "min flo bushing": "MIN_FLO_BUSHING",
    "paint": "PAINT_OPTIONS",
    "aux nameplate": "AUXILLARY_NAMEPLATE",
}

# Baseplate type: Matrix -> config BASEPLATE_TYPE (engineering-confirmed
# Economy == Formed). ANSI/API/Support Base map to themselves.
BASEPLATE_TYPE_NORMALIZE = {
    "economy": "Formed",
    "ansi": "ANSI",
    "api": "API",
    "support base": "Support Base",
    "formed": "Formed",
    "none": "NONE",
}


def _normalize_bp_type(bt: str) -> str:
    return BASEPLATE_TYPE_NORMALIZE.get(str(bt).strip().lower(), str(bt).strip())


def _drip_pan_from_material(mat: str) -> str:
    """Baseplate 'Material' encodes the Drip Pan choice (the price disambiguator,
    per Formal Quote!C30). '...w/ SS Drip Pan' -> Stainless; a real Formed Steel
    baseplate -> Steel; '-'/blank (Support Base) -> NONE."""
    m = str(mat).strip().lower()
    if "w/ ss drip pan" in m:
        return "Stainless"
    if m in ("-", ""):
        return "NONE"
    return "Steel"


# Material vocabulary: Matrix abbreviations -> D110 canonical PUMP_MATERIAL values.
MATERIAL_NORMALIZE = {
    "(20) c.i.": "(20) Cast Iron",
    "(22) d,i.": "(22) Ductile Iron",
    "(22) d.i.": "(22) Ductile Iron",
    "(40) c.s.": "(40) Cast Steel",
    "(41) 11-13 (cr)": "(41) Cast Steel (420 SS Trim)",
    "(41) c.s. (420 ss trim)": "(41) Cast Steel (420 SS Trim)",
    "(50) 316 s.s.": "(50) 316 S/S",
    "(50) 316 s/s": "(50) 316 S/S",
    "(55) cd4mcu": "(55) CD4MCu",
    "(60) alloy 20": "(60) Alloy 20",
    "(63) hastelloy c": "(63) Hastelloy C",
    "custom": "Custom",
}


def _label_to_code_map() -> dict:
    d = json.loads(M023.read_text(encoding="utf-8"))
    m = {}
    for lod in d["logic_option_domains"]:
        m[str(lod["field_label"]).strip().lower()] = str(lod["canonical_field_code"]).strip()
    for dep in d["dependencies"]:
        for lab, code in zip(dep["field_labels"], dep["canonical_field_codes"]):
            m.setdefault(str(lab).strip().lower(), str(code).strip())
    return m


def _num(v):
    if v is None:
        return None
    try:
        return round(float(str(v).replace(",", "").replace("$", "").strip()), 4)
    except Exception:
        return None


def _norm_material(v: str) -> str:
    key = str(v).strip().lower()
    return MATERIAL_NORMALIZE.get(key, str(v).strip())


def _cond(seq, field, value):
    return {"sequence_no": seq, "field_code": field.upper(),
            "comparison_operator": "EQ", "comparison_value": str(value)}


def main():
    label_to_code = _label_to_code_map()
    wb = openpyxl.load_workbook(WB_PATH, data_only=True, read_only=True)
    candidates: list[dict] = []
    stats = {"BASE_PUMP": 0, "OPTION_ADDER": 0, "COUPLING": 0,
             "BASEPLATE": 0, "SHAFT_CONFIG": 0}
    unmapped_adder_groups = set()
    unmapped_materials = set()

    # Read-only random .cell() access is O(scan) and far too slow over the wide
    # Std Options / Base Plates sheets. Load each sheet ONCE into a row-major grid
    # (list of tuples, 0-based) and read from that. C(grid, r, c) uses 1-based
    # r,c (matching Excel) against the grid.
    grids: dict[str, list] = {}

    def load_grid(name):
        if name not in grids:
            grids[name] = list(wb[name].iter_rows(values_only=True))
        return grids[name]

    def C(grid, r, c):
        if r - 1 < 0 or r - 1 >= len(grid):
            return ""
        row = grid[r - 1]
        v = row[c - 1] if 0 <= c - 1 < len(row) else None
        return "" if v is None else v

    def nrows(grid):
        return len(grid)

    def ncols(grid):
        return max((len(r) for r in grid), default=0)

    # ================= Std Options: BASE_PUMP + OPTION_ADDER =================
    ws = load_grid("Std Options")
    maxc = ncols(ws)
    # header rows: row3 = adder group label (at first col of block); row4 = per-col option value
    row3 = {c: str(C(ws, 3, c)).strip() for c in range(1, maxc + 1) if str(C(ws, 3, c)).strip()}
    row4 = {c: str(C(ws, 4, c)).strip() for c in range(1, maxc + 1) if str(C(ws, 4, c)).strip()}
    group_cols = sorted(row3)

    def group_for(col):
        g = None
        for gc in group_cols:
            if gc <= col:
                g = row3[gc]
            else:
                break
        return g

    # adder columns: col >= 11 with a row4 option header, mapped to (code, option)
    adder_cols = []
    for c in range(11, maxc + 1):
        ov = row4.get(c)
        if not ov:
            continue
        g = group_for(c)
        if not g:
            continue
        code = label_to_code.get(g.strip().lower()) or ADDER_LABEL_ALIASES.get(g.strip().lower())
        if not code:
            unmapped_adder_groups.add(g)
            continue
        adder_cols.append((c, code, ov))

    # data rows from row 5: base list (col J=10) keyed Series(G=7)/Size(H=8)/Material(I=9)
    for r in range(5, nrows(ws) + 1):
        series = str(C(ws, r, 7)).strip()
        size = str(C(ws, r, 8)).strip()
        material_raw = str(C(ws, r, 9)).strip()
        base = _num(C(ws, r, 10))
        if not series or not size or not material_raw:
            continue
        material = _norm_material(material_raw)
        if str(material_raw).strip().lower() not in MATERIAL_NORMALIZE and material == material_raw:
            unmapped_materials.add(material_raw)
        # BASE_PUMP only when a numeric base list exists (base-price gate).
        if base is None:
            continue
        candidates.append({
            "family_code": FAMILY, "currency_code": CURRENCY,
            "workbook_name": WORKBOOK, "worksheet_name": "Std Options",
            "table_name": "Std Options", "source_cell": f"J{r}",
            "component_code": "BASE_PUMP",
            "series_code": series, "source_series_code": series,
            "size_value": size, "source_size_value": size,
            "option_field_code": "PUMP_MATERIAL",
            "option_value": material, "source_option_value": material,
            "conditions": [_cond(1, "SIZE", size), _cond(2, "PUMP_MATERIAL", material)],
            "amount": base, "pricing_status": "found",
            "source_price_value": str(C(ws, r, 10)),
        })
        stats["BASE_PUMP"] += 1

        # OPTION_ADDER: each adder cell that is numeric (|value| added on top).
        for c, code, opt in adder_cols:
            cell = C(ws, r, c)
            amt = _num(cell)
            if amt is None:
                continue  # blank / 'X' / n/a -> not a priced adder
            candidates.append({
                "family_code": FAMILY, "currency_code": CURRENCY,
                "workbook_name": WORKBOOK, "worksheet_name": "Std Options",
                "table_name": f"Std Options / {code}", "source_cell": f"{get_column_letter(c)}{r}",
                "component_code": "OPTION_ADDER",
                "series_code": series, "source_series_code": series,
                "size_value": size, "source_size_value": size,
                "option_field_code": code, "option_value": opt,
                "source_option_value": opt,
                "conditions": [
                    _cond(1, "SIZE", size),
                    _cond(2, "PUMP_MATERIAL", material),
                    _cond(3, code, opt),
                ],
                "amount": abs(amt),  # ADDER SIGN IGNORED (engineering-confirmed)
                "pricing_status": "found",
                "source_price_value": str(cell),
            })
            stats["OPTION_ADDER"] += 1

    # ================= COUPLINGS =================
    ws = load_grid("COUPLINGS")
    for r in range(5, nrows(ws) + 1):
        series = str(C(ws, r, 3)).strip()
        frame = str(C(ws, r, 4)).strip()
        coupling = str(C(ws, r, 5)).strip()
        amt = _num(C(ws, r, 6))
        if not series or amt is None:
            continue
        candidates.append({
            "family_code": FAMILY, "currency_code": CURRENCY,
            "workbook_name": WORKBOOK, "worksheet_name": "COUPLINGS",
            "table_name": "COUPLINGS", "source_cell": f"F{r}",
            "component_code": "COUPLING",
            "series_code": series, "source_series_code": series,
            "size_value": None, "source_size_value": None,
            "option_field_code": None, "option_value": None,
            "source_option_value": coupling,
            "conditions": [_cond(1, "FRAME_SIZE", frame), _cond(2, "COUPLING_TYPE", coupling)],
            "amount": amt, "pricing_status": "found",
            "source_price_value": str(C(ws, r, 6)),
        })
        stats["COUPLING"] += 1

    # ================= Base Plates =================
    # BASEPLATE price key = BaseplateType (Economy->Formed) + FrameSize + Drip Pan
    # (Steel/Stainless, decoded from the Matrix "Material"). Verified unique except
    # ONE genuine source anomaly (flagged, not silently deduped). Lugs are
    # DESCRIPTIVE (Matrix lug cols are 'X' applicability, not $; Formal Quote!C30
    # lists Required lugs in the baseplate line) -> NOT priced as separate adders.
    ws = load_grid("Base Plates")
    bp_seen = {}   # (series, bp_type, frame_size, drip) -> amount  (anomaly detect)
    bp_anomalies = []
    for r in range(5, nrows(ws) + 1):
        series = str(C(ws, r, 2)).strip()          # B
        frame_type = str(C(ws, r, 3)).strip()      # C (mounting family, informational)
        frame_size = str(C(ws, r, 4)).strip()      # D
        bp_type_raw = str(C(ws, r, 5)).strip()     # E
        bp_material = str(C(ws, r, 6)).strip()     # F
        amt = _num(C(ws, r, 7))                    # G List
        if not series or amt is None:
            continue
        bp_type = _normalize_bp_type(bp_type_raw)
        drip = _drip_pan_from_material(bp_material)
        key = (series, bp_type, frame_size, drip)
        if key in bp_seen and abs(bp_seen[key] - amt) > 0.005:
            # Genuine duplicate key with a DIFFERENT price -> source anomaly. Keep
            # the first, log it; do not silently overwrite.
            bp_anomalies.append((key, bp_seen[key], amt, f"G{r}"))
            continue
        if key in bp_seen:
            continue  # exact duplicate, skip
        bp_seen[key] = amt
        # Conditions: Support Base has no drip pan; otherwise gate on Drip Pan too.
        conds = [_cond(1, "BASEPLATE_TYPE", bp_type or "-"),
                 _cond(2, "FRAME_SIZE", frame_size or "-")]
        if drip != "NONE":
            conds.append(_cond(3, "DRIP_PAN", drip))
        candidates.append({
            "family_code": FAMILY, "currency_code": CURRENCY,
            "workbook_name": WORKBOOK, "worksheet_name": "Base Plates",
            "table_name": "Base Plates", "source_cell": f"G{r}",
            "component_code": "BASEPLATE",
            "series_code": series, "source_series_code": series,
            "size_value": None, "source_size_value": None,
            "option_field_code": "BASEPLATE_TYPE", "option_value": bp_type,
            "source_option_value": f"{bp_type} / {drip} drip pan ({bp_material})",
            "conditions": conds,
            "amount": amt, "pricing_status": "found",
            "source_price_value": str(C(ws, r, 7)),
        })
        stats["BASEPLATE"] += 1
    if bp_anomalies:
        print(f"  [ANOMALY] {len(bp_anomalies)} baseplate key(s) with >1 price "
              f"(kept first, flagged):")
        for key, a, b, cell in bp_anomalies:
            print(f"      {key} -> {a} vs {b} ({cell})")

    # ================= Shaft Configuration (priced cells only) =================
    ws = load_grid("Shaft Configuration")
    cfg_hdr = {c: str(C(ws, 4, c)).strip() for c in range(4, 10)}  # D..I config names
    for r in range(5, nrows(ws) + 1):
        series = str(C(ws, r, 1)).strip()          # A
        material = _norm_material(str(C(ws, r, 2)).strip())  # B
        shaft_mat = str(C(ws, r, 3)).strip()       # C
        if not series:
            continue
        for c in range(4, 10):
            amt = _num(C(ws, r, c))
            if amt is None:
                continue  # 'x'/blank/n-a = applicability, not price
            cfg = cfg_hdr.get(c, "")
            candidates.append({
                "family_code": FAMILY, "currency_code": CURRENCY,
                "workbook_name": WORKBOOK, "worksheet_name": "Shaft Configuration",
                "table_name": "Shaft Configuration", "source_cell": f"{get_column_letter(c)}{r}",
                "component_code": "SHAFT_CONFIG",
                "series_code": series, "source_series_code": series,
                "size_value": None, "source_size_value": None,
                "option_field_code": "SHAFT_CONFIGURATION", "option_value": cfg,
                "source_option_value": cfg,
                "conditions": [
                    _cond(1, "SHAFT_MATERIAL", shaft_mat or "-"),
                    _cond(2, "SHAFT_CONFIGURATION", cfg),
                ],
                "amount": abs(amt), "pricing_status": "found",
                "source_price_value": str(C(ws, r, c)),
            })
            stats["SHAFT_CONFIG"] += 1
    wb.close()

    # De-duplicate on the publisher's uniqueness key (component, series, conditions).
    seen = set()
    deduped = []
    dupes = 0
    for cand in candidates:
        key = (cand["component_code"], cand["series_code"],
               tuple((c["field_code"], c["comparison_operator"], str(c["comparison_value"]))
                     for c in cand["conditions"]))
        if key in seen:
            dupes += 1
            continue
        seen.add(key)
        deduped.append(cand)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(
        {"issue_count": 0, "source_workbook": WORKBOOK, "family_code": FAMILY,
         "candidates": deduped}, indent=1), encoding="utf-8")

    print(f"Dean pricing candidates written: {OUT}")
    print(f"  total candidates: {len(deduped)}  (deduped {dupes})")
    for k, v in stats.items():
        print(f"    {k}: {v}")
    if unmapped_adder_groups:
        print(f"  UNMAPPED adder groups (skipped): {sorted(unmapped_adder_groups)}")
    if unmapped_materials:
        print(f"  UNMAPPED materials (kept as-is): {sorted(unmapped_materials)}")
    # distinct Dean series (for the collision check in the publish step)
    dean_series = sorted({c["series_code"] for c in deduped})
    print(f"  distinct Dean series in pricing: {len(dean_series)}")


if __name__ == "__main__":
    main()

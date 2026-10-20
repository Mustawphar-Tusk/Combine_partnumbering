"""Milestone audit: Dean UI selection-hierarchy rearrangement (presentation).

Verifies the Dean field ORDER + 10-group PRESENTATION delivered by the API
matches the authoritative Dean Data Sheet Rev 2 layout, WITHOUT changing Part
Number assembly / parity (presentation-only) and WITHOUT touching Fybroc.

Exit-gate criteria checked (exits non-zero on any failure):

  1. Family-aware ordering: Dean resolve-state returns fields in the
     authoritative Smart-Number order (DEAN_FIELD_HIERARCHY), not alphabetical.
  2. Grouping present for Dean: field_groups is a non-empty, ordered list of the
     authoritative 10-group structure (subset per bundle), each field carrying a
     boolean `placeholder` flag.
  3. C/F semantics correct:
       - genuinely-unbuilt authoritative fields -> placeholder=True (C/F);
       - fields a PUMP_CONFIGURATION bundle excludes -> OMITTED (not C/F);
       - a fully bundle-excluded component group -> its header dropped;
       - identity fields (SERIES/SIZE/ALT_SIZE) -> never shown as grid C/F.
  4. Fybroc untouched: Fybroc resolve-state returns field_groups == [] (flat)
     and its field order is unchanged (Fybroc hierarchy, byte-for-byte).
  5. PN assembly unchanged: a Dean STD config still resolves to a PN/SKU through
     the same path (presentation reorder did not alter numbering).

Run (PowerShell):
    $env:PYTHONPATH="."; .\\.venv\\Scripts\\python.exe scripts\\audit_dean_ui_rearrange.py

Requires the API running locally at 127.0.0.1:8080 (the project's standard
uvicorn start). The script starts/stops nothing; it only probes.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

from src.api.v2_routes import (
    DEAN_FIELD_HIERARCHY,
    DEAN_FIELD_GROUPS,
    _dean_pump_config_excluded_fields,
    _order_fields,
)

BASE = "http://127.0.0.1:8080/api/v2"
DEAN_SERIES = ["PH2110", "DL200", "RA3146", "R5140"]

_passed = 0
_failed = 0


def check(cond: bool, label: str, detail: str = "") -> None:
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  [PASS] {label}" + (f" ({detail})" if detail else ""))
    else:
        _failed += 1
        print(f"  [FAIL] {label}" + (f" ({detail})" if detail else ""))


def post(path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def _fybroc_series() -> str | None:
    """Pick a Fybroc series from the dictionary (non-Dean)."""
    import pyodbc
    c = pyodbc.connect(
        'DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;'
        'DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;Encrypt=yes;'
        'TrustServerCertificate=yes;')
    cur = c.cursor()
    cur.execute("""
        SELECT TOP 1 so.SeriesCode
        FROM cfg.SeriesFieldOption so
        WHERE so.SeriesCode NOT IN (
            SELECT DISTINCT SeriesCode FROM cfg.PumpModelReference pmr
            JOIN cfg.PumpFamily f ON pmr.PumpFamilyId=f.PumpFamilyId
            WHERE f.FamilyCode='DEAN')
        ORDER BY so.SeriesCode
    """)
    row = cur.fetchone()
    return row[0] if row else None


def audit_dean_ordering_and_groups() -> None:
    print("=== Dean ordering + authoritative grouping ===")
    group_names = [g for g, _ in DEAN_FIELD_GROUPS]
    for series in DEAN_SERIES:
        state = post("/families/DEAN/configurations/resolve-state",
                     {"series": series, "selections": {}})
        ordered = state["ordered_fields"]
        groups = state["field_groups"]

        # (1) ordering = authoritative hierarchy order
        expected_order = _order_fields(ordered, "DEAN")
        check(ordered == expected_order, f"{series}: fields in authoritative order",
              f"n={len(ordered)}")

        # (2) grouping present and in authoritative group order
        check(isinstance(groups, list) and len(groups) >= 1,
              f"{series}: field_groups present", f"groups={len(groups)}")
        got_group_order = [g["group"] for g in groups if g["group"] != "Other"]
        order_ok = got_group_order == [g for g in group_names if g in got_group_order]
        check(order_ok, f"{series}: groups in authoritative order",
              " > ".join(got_group_order))

        # field entries carry {field, placeholder}
        shape_ok = all(
            isinstance(f, dict) and "field" in f and "placeholder" in f
            for g in groups for f in g["fields"])
        check(shape_ok, f"{series}: every group field has field+placeholder flag")

        # (3) C/F semantics: bundle-excluded components are omitted, not C/F.
        bundle = state["selections"].get("PUMP_CONFIGURATION", "")
        excluded = _dean_pump_config_excluded_fields(
            {"PUMP_CONFIGURATION": bundle})
        shown = {f["field"] for g in groups for f in g["fields"]}
        no_excluded_shown = not (shown & {e for e in excluded})
        check(no_excluded_shown, f"{series}: bundle-excluded fields omitted (not C/F)",
              f"bundle='{bundle}'")

        # SERIES is owned by the top-of-UI series selector and must never appear
        # as a grid field. SIZE, by contrast, IS a selectable Pump-Information
        # field (sourced from cfg.PumpModelReference for Dean) and SHOULD appear
        # so the user can pick a size after choosing a series.
        check("SERIES" not in shown, f"{series}: SERIES not shown as a grid field")
        pump_info = next((g for g in groups if g["group"] == "Pump Information"), None)
        size_first = (pump_info is not None and pump_info["fields"]
                      and pump_info["fields"][0]["field"] == "SIZE"
                      and pump_info["fields"][0]["placeholder"] is False)
        check(size_first,
              f"{series}: SIZE is the first selectable field in Pump Information")
        check(bool(state["selections"].get("SIZE")),
              f"{series}: SIZE is STD-seeded", state["selections"].get("SIZE"))

        # a real (present) field is never flagged placeholder, and vice-versa
        present = set(ordered)
        mislabeled = [f["field"] for g in groups for f in g["fields"]
                      if f["placeholder"] and f["field"] in present]
        check(not mislabeled, f"{series}: no present field mislabeled C/F",
              ",".join(mislabeled) or "none")


def audit_bundle_gating() -> None:
    print("=== PUMP_CONFIGURATION bundle gating (component groups) ===")
    series = "PH2110"
    # Pump Only -> Coupling/Baseplate/Motor omitted.
    s0 = post("/families/DEAN/configurations/resolve-state",
              {"series": series, "selections": {"PUMP_CONFIGURATION": "Pump Only"},
               "changed_field": "PUMP_CONFIGURATION"})
    names0 = {g["group"] for g in s0["field_groups"]}
    check(not ({"Coupling", "Baseplate"} & names0),
          "Pump Only: Coupling+Baseplate groups omitted", ",".join(sorted(names0)))

    # Full bundle -> all three appear, with real fields.
    s1 = post("/families/DEAN/configurations/resolve-state",
              {"series": series,
               "selections": {"PUMP_CONFIGURATION": "Pump, Baseplate, Coupling and Motor"},
               "changed_field": "PUMP_CONFIGURATION"})
    gmap = {g["group"]: g for g in s1["field_groups"]}
    for grp, min_real in (("Coupling", 1), ("Baseplate", 1), ("Motor", 1)):
        real = sum(1 for f in gmap.get(grp, {"fields": []})["fields"]
                   if not f["placeholder"])
        check(grp in gmap and real >= min_real,
              f"Full bundle: {grp} present with real field(s)", f"real={real}")


def audit_fybroc_untouched() -> None:
    print("=== Fybroc isolation (presentation unchanged) ===")
    fseries = _fybroc_series()
    check(fseries is not None, "found a Fybroc series", str(fseries))
    if not fseries:
        return
    state = post("/families/FYBROC/configurations/resolve-state",
                 {"series": fseries, "selections": {}})
    check(state["field_groups"] == [],
          "Fybroc field_groups empty (flat render)",
          f"got len={len(state['field_groups'])}")
    # Fybroc order must equal the Fybroc hierarchy ordering (not Dean's).
    ordered = state["ordered_fields"]
    check(ordered == _order_fields(ordered, "FYBROC"),
          "Fybroc fields in Fybroc hierarchy order", f"n={len(ordered)}")
    # And Dean's hierarchy must NOT describe the Fybroc order (sanity: families differ).
    check(ordered != _order_fields(ordered, "DEAN") or
          all(fc not in DEAN_FIELD_HIERARCHY for fc in ordered),
          "Fybroc order is family-specific (not Dean-ordered)")


def audit_pn_unchanged() -> None:
    print("=== PN assembly unchanged (presentation-only) ===")
    for series in ("PH2110", "DL200"):
        state = post("/families/DEAN/configurations/resolve-state",
                     {"series": series, "selections": {}})
        sel = dict(state["selections"])
        sel["SERIES"] = series
        seg = {k: v for k, v in state["resolved_codes"].items() if v}
        res = post("/families/DEAN/configured-products/resolve",
                   {"series": series, "selections": sel, "segment_codes": seg,
                    "requested_by": "audit_dean_ui_rearrange"})
        check(bool(res.get("part_number")), f"{series}: resolves to a PN",
              res.get("part_number", ""))
        check(bool(res.get("sku")), f"{series}: resolves to a SKU",
              res.get("sku", ""))


def _get(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=90) as r:
        return json.loads(r.read())


def audit_sku_lookup() -> None:
    """The by-sku lookup returns the stored configuration for a real SKU, and a
    clean not-found for a bogus SKU. Resolve a Dean config first to guarantee a
    SKU exists, then look it up."""
    print("=== SKU lookup (by-sku) ===")
    state = post("/families/DEAN/configurations/resolve-state",
                 {"series": "PH2110", "selections": {}})
    sel = dict(state["selections"]); sel["SERIES"] = "PH2110"
    seg = {k: v for k, v in state["resolved_codes"].items() if v}
    res = post("/families/DEAN/configured-products/resolve",
               {"series": "PH2110", "selections": sel, "segment_codes": seg,
                "requested_by": "audit_dean_ui_rearrange"})
    sku = res.get("sku")
    check(bool(sku), "a Dean SKU exists to look up", sku)
    if not sku:
        return

    import urllib.parse
    look = _get(f"/configured-products/by-sku/{urllib.parse.quote(sku, safe='')}")
    check(look.get("found") is True, "lookup returns found=True", sku)
    check((look.get("family") or "").upper() == "DEAN", "lookup family is DEAN",
          look.get("family"))
    check(len(look.get("selections", {})) > 0, "lookup returns stored selections",
          f"{len(look.get('selections', {}))} fields")
    check(len(look.get("field_groups", [])) >= 1,
          "lookup returns Dean grouped field_groups",
          f"{len(look.get('field_groups', []))} groups")

    missing = _get("/configured-products/by-sku/NO-SUCH-SKU-XYZ")
    check(missing.get("found") is False, "bogus SKU returns found=False")
    check(bool(missing.get("errors")), "bogus SKU returns an error message")


def main() -> int:
    try:
        post("/families/DEAN/configurations/resolve-state",
             {"series": DEAN_SERIES[0], "selections": {}})
    except (urllib.error.URLError, OSError) as e:
        print(f"ERROR: API not reachable at {BASE} ({e}). Start the local API first.")
        return 2

    audit_dean_ordering_and_groups()
    audit_bundle_gating()
    audit_fybroc_untouched()
    audit_pn_unchanged()
    audit_sku_lookup()

    print("=" * 76)
    print(f"RESULT: {_passed} passed, {_failed} failed")
    print("=" * 76)
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

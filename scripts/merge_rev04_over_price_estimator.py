"""Build the Rev0.4 <-> Price-Estimator OVERLAY MERGE (option 2b).

Goal (per engineering + product owner):
  - Adopt Rev0.4 pricing ONLY for series 1500 and 5500 (both largely complete).
  - Within 1500/5500: a Rev0.4 DETERMINED price ('found') UPDATES the price;
    a Rev0.4 'C/F' (Contact Factory) does NOT overwrite -> retain the existing
    Price-Estimator price if one exists (else it is genuinely Contact Factory,
    i.e. no priced row -> runtime default is call-for-price).
  - All OTHER series keep their existing Price-Estimator prices unchanged.

Reality of the sources (verified):
  - The Price-Estimator baseline (FYBROC-CONFIG-20260807-V3, preserved non-current)
    has only BASE_PUMP + SEAL, and only HORIZONTAL series (1500,1530,1550,1600,
    1630,1650,2530,2580,2630,3000). No 5500/vertical, no other components.
  - So: 5500 = Rev0.4-only (no V3 to retain). 1500 BASE_PUMP/SEAL = overlay onto
    V3. All other Rev0.4 components (sleeve/coupling/hardware/testing/motor/...) =
    new (no V3 counterpart). Other series = untouched V3.

Merge algorithm (produces a single merged candidate set = the new publication):
  1. Start from ALL V3 rows (the retained Price-Estimator baseline).
  2. For series 1500: overlay Rev0.4 BASE_PUMP + SEAL found prices onto V3
     (replace the V3 amount for a matching key; V3 rows with no Rev0.4 'found'
     match are retained unchanged). Add Rev0.4 found rows for keys not in V3.
  3. Add ALL other Rev0.4 found rows (5500 everything; 1500 non-BASE/SEAL
     components; family-wide adders) as-is (they are new).
  4. Leave every non-1500/5500 V3 row untouched.

Key normalization for the 1500 BASE_PUMP/SEAL overlay match:
  - size: uppercase, strip ' (..)' suffix
  - material: map Rev0.4 'VR-1' -> V3 'VR-1 (Standard)', 'VR-1_BPO/DMA' ->
    'VR-1 BPO/DMA', underscores->spaces, uppercase.
  SEAL keys differ in shape between sources; per decision (a) we PREFER the
  Rev0.4 found seal price and keep V3 seal only where Rev0.4 has no match. Seal
  overlay is therefore done by (series,size,material-ish) best-effort and all
  unmatched are reported by the diff script.

Writes exports/fybroc_merged_pricing.json (publisher-ready) + a machine-readable
merge classification exports/fybroc_merge_classification.json used by the diff doc.

Read-only against the DB (SELECT). Does not publish; run the publisher separately.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pyodbc

ROOT = Path(__file__).resolve().parents[1]
CONN = ("DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=PumpConfiguratorDB;"
        "Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;")
BASELINE_VERSION = "FYBROC-CONFIG-20260807-V3"   # Price Estimator (preserved non-current)
ADOPT_SERIES = {"1500", "5500"}                   # option 2b
WORKBOOK_NAME = "Fybroc Configuration Rev0.4.xlsx + Price Estimator-Fybroc.xlsm (merged)"


# ---- normalization helpers for the 1500 BASE_PUMP/SEAL overlay match ----
def norm_size(v: str | None) -> str:
    if not v:
        return ""
    return v.split(" (", 1)[0].strip().upper()


def norm_series(v: str | None) -> str:
    if not v:
        return ""
    return v.split(" (", 1)[0].strip()      # '1530 (ANSI)' -> '1530'


def norm_material(v: str | None) -> str:
    if not v:
        return ""
    m = v.strip().upper().replace("_", " ")
    m = m.replace("VR-1 (STANDARD)", "VR-1").replace("(STANDARD)", "").strip()
    return m


# ---- read the V3 Price-Estimator baseline from the DB ----
def read_baseline():
    conn = pyodbc.connect(CONN, autocommit=True)
    cur = conn.cursor()
    vid = cur.execute(
        """SELECT pbv.PriceBookVersionId FROM price.PriceBookVersion pbv
           JOIN price.PriceBook pb ON pb.PriceBookId=pbv.PriceBookId
           JOIN cfg.PumpFamily pf ON pf.PumpFamilyId=pb.PumpFamilyId
           WHERE pf.FamilyCode='FYBROC' AND pbv.VersionCode=?""", BASELINE_VERSION).fetchone()[0]
    rows = cur.execute(
        """SELECT pr.ComponentCode, pr.SeriesCode, pr.SourceSizeValue, pr.SourceOptionValue,
                  pr.Amount, pr.PricingStatus, pr.SourceWorksheet, pr.SourceTable, pr.SourceCell
           FROM price.PriceRule pr WHERE pr.PriceBookVersionId=?""", vid).fetchall()
    conn.close()
    out = []
    for r in rows:
        out.append({
            "component_code": r[0], "series_code": r[1], "source_size_value": r[2],
            "source_option_value": r[3],
            "amount": float(r[4]) if r[4] is not None else None,
            "pricing_status": r[5],
            "source_worksheet": r[6], "source_table": r[7], "source_cell": r[8],
        })
    return out


def load_rev04():
    data = json.loads((ROOT / "exports" / "fybroc_rev04_pricing.json").read_text(encoding="utf-8"))
    return data["candidates"]


def baseline_to_candidate(b: dict) -> dict:
    """Turn a V3 baseline row into a publisher candidate (retain as-is)."""
    conds = []
    if b["source_size_value"] is not None:
        conds.append({"sequence_no": 1, "field_code": "SIZE", "comparison_operator": "EQ",
                      "comparison_value": b["source_size_value"]})
    if b["source_option_value"] is not None:
        fld = "PUMP_MATERIAL" if b["component_code"] == "BASE_PUMP" else "SEAL"
        conds.append({"sequence_no": len(conds) + 1, "field_code": fld,
                      "comparison_operator": "EQ", "comparison_value": b["source_option_value"]})
    # Publisher invariant: found => amount present; call_for_price => amount NULL.
    status = b["pricing_status"]
    amount = b["amount"]
    if status == "call_for_price":
        amount = None
    return {
        "family_code": "FYBROC", "component_code": b["component_code"],
        "series_code": b["series_code"], "source_series_code": b["series_code"],
        "size_value": b["source_size_value"], "source_size_value": b["source_size_value"],
        "option_field_code": ("PUMP_MATERIAL" if b["component_code"] == "BASE_PUMP" else "SEAL"),
        "option_value": b["source_option_value"], "source_option_value": b["source_option_value"],
        "amount": amount, "pricing_status": status,
        "source_price_value": amount, "currency_code": "USD",
        "workbook_name": WORKBOOK_NAME, "worksheet_name": b.get("source_worksheet") or "PriceEstimator",
        "table_name": b.get("source_table") or "PriceEstimator", "source_cell": b.get("source_cell") or "",
        "conditions": conds,
        "_origin": "price_estimator",
    }


def main():
    baseline = read_baseline()
    rev04 = load_rev04()

    # Index Rev0.4 1500 BASE_PUMP by normalized (size, material) for overlay match.
    rev04_1500_base = {}
    for c in rev04:
        if c["component_code"] == "BASE_PUMP" and norm_series(c["series_code"]) == "1500":
            k = (norm_size(c["source_size_value"]), norm_material(c["option_value"]))
            rev04_1500_base[k] = c

    merged = []
    classification = []   # for the diff doc
    used_rev04 = set()     # id() of rev04 candidates consumed as overlay

    # 1) walk the V3 baseline
    for b in baseline:
        ser = norm_series(b["series_code"])
        if ser == "1500" and b["component_code"] == "BASE_PUMP":
            k = (norm_size(b["source_size_value"]), norm_material(b["source_option_value"]))
            rc = rev04_1500_base.get(k)
            if rc is not None and rc["pricing_status"] == "found":
                used_rev04.add(id(rc))
                new = baseline_to_candidate(b)
                old_amt = new["amount"]
                new["amount"] = rc["amount"]; new["source_price_value"] = rc["amount"]
                new["workbook_name"] = WORKBOOK_NAME
                new["_origin"] = "rev04_overlay"
                merged.append(new)
                cls = "unchanged" if old_amt == rc["amount"] else "changed"
                classification.append({
                    "component": "BASE_PUMP", "series": "1500",
                    "size": b["source_size_value"], "option": b["source_option_value"],
                    "class": cls, "old_amount": old_amt, "new_amount": rc["amount"],
                    "delta": (rc["amount"] - old_amt) if old_amt is not None else None,
                })
                continue
            # no Rev0.4 found match -> retain V3
            merged.append(baseline_to_candidate(b))
            classification.append({
                "component": "BASE_PUMP", "series": "1500",
                "size": b["source_size_value"], "option": b["source_option_value"],
                "class": "retained_v3", "old_amount": b["amount"], "new_amount": b["amount"], "delta": 0,
            })
            continue
        # Decision (a): for series 1500, Rev0.4 SEAL supersedes V3 SEAL. Drop the
        # V3 1500 SEAL rows here; the Rev0.4 seal table (series-less) is stamped to
        # 1500/5500 below. V3 SEAL for NON-adopted series is retained.
        if ser == "1500" and b["component_code"] == "SEAL":
            classification.append({
                "component": "SEAL", "series": "1500",
                "size": b["source_size_value"], "option": b["source_option_value"],
                "class": "superseded_by_rev04", "old_amount": b["amount"],
                "new_amount": None, "delta": None,
            })
            continue
        # all other V3 rows retained unchanged (non-adopted series)
        merged.append(baseline_to_candidate(b))

    # 2) add ALL Rev0.4 found rows that were not consumed as a 1500 BASE overlay.
    #    (5500 everything, 1500 non-BASE components incl SEAL per decision (a),
    #     family-wide adders). These are 'new' relative to V3.
    added_new = 0
    for c in rev04:
        if id(c) in used_rev04:
            continue
        if c["pricing_status"] != "found":
            continue
        ser = norm_series(c.get("series_code"))
        # Series-scoping for 2b:
        #  - a Rev0.4 row WITH a series must be one we adopt (1500/5500).
        #  - a Rev0.4 row WITHOUT a series (series-less: SEAL table, family-wide
        #    adders) is stamped to BOTH adopted series 1500 & 5500 so it only
        #    matches those (not the non-adopted series still on Price-Estimator).
        if ser and ser not in ADOPT_SERIES:
            continue
        targets = [c.get("series_code")] if ser else sorted(ADOPT_SERIES)
        for tgt in targets:
            cc = dict(c)
            cc["series_code"] = tgt
            cc["source_series_code"] = tgt
            cc["workbook_name"] = WORKBOOK_NAME
            cc["_origin"] = "rev04_new"
            merged.append(cc)
            added_new += 1
            classification.append({
                "component": c["component_code"], "series": tgt,
                "size": c.get("source_size_value"), "option": c.get("option_value"),
                "class": "new_rev04", "old_amount": None, "new_amount": c["amount"],
                "delta": None,
            })

    # De-dup merged using the PUBLISHER'S EXACT staging key so SQL's 51005 dedup
    # (GROUP BY ComponentCode,SeriesCode,SizeValue,OptionFieldCode,OptionValue)
    # can never fire. We reuse the publisher's own normalization functions.
    from src.pricing_engine.publisher import (
        _normalized_conditions, _legacy_transport_values,
    )

    def _sqlnorm(v):
        # SQL Server default collation is case- AND trailing-space-insensitive,
        # so GROUP BY treats values equal under those rules. Mirror that here so
        # our dedup catches everything SQL's 51005 check would.
        if v is None:
            return None
        return str(v).rstrip().casefold()

    def staging_key(c):
        cj = json.dumps(_normalized_conditions(c), ensure_ascii=False,
                        separators=(",", ":"), sort_keys=True)
        size_v, _ss, of, ov, _sov = _legacy_transport_values(c, cj)
        return (_sqlnorm(c["component_code"]), _sqlnorm(c.get("series_code")),
                _sqlnorm(size_v), _sqlnorm(of), _sqlnorm(ov))

    uniq = {}
    dupes = 0
    for c in merged:
        k = staging_key(c)
        if k in uniq:
            dupes += 1
            continue
        uniq[k] = c
    merged = list(uniq.values())

    # strip internal _origin before publishing (keep in classification file)
    origins = defaultdict(int)
    for c in merged:
        origins[c.pop("_origin", "?")] += 1

    out = {"artifact": "FYBROC_MERGED_PRICING", "issue_count": 0,
           "candidate_count": len(merged), "candidates": merged}
    (ROOT / "exports" / "fybroc_merged_pricing.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8")
    (ROOT / "exports" / "fybroc_merge_classification.json").write_text(
        json.dumps({"classification": classification}, indent=2, default=str), encoding="utf-8")

    by_comp = defaultdict(int)
    for c in merged:
        by_comp[c["component_code"]] += 1
    print(f"merged candidates: {len(merged)}  dupes_removed: {dupes}")
    print(f"origins: {dict(origins)}")
    print(f"rev04 new added: {added_new}")
    print(f"by component (top): {dict(sorted(by_comp.items(), key=lambda x:-x[1])[:12])}")


if __name__ == "__main__":
    raise SystemExit(main())

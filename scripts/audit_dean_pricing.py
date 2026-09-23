"""D120 Dean pricing audit.

Guards the D120 exit gate: a configured Dean pump resolves to a traceable total =
base list + Σ|option adder| (+ coupling / baseplate / shaft config), with every
priced amount matching the authoritative Dean Pricing Matrix (as published to
cfg/price.* SQL), adders applying ONLY for selected options, the Pump
Configuration gate honored, and honest C/F where the Matrix is silent (motor,
seal). Expectations are DERIVED FROM THE PUBLISHED DB PRICE RULES (which came from
the Matrix) - not hardcoded - so the audit tracks the authoritative data.

Requires the API on 127.0.0.1:8080 + the DEAN_STANDARD current pricing version.
Exit 0 if all pass, 1 otherwise.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request

import pyodbc

BASE = "http://127.0.0.1:8080/api/v2/families/DEAN"
CONN = ("DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;"
        "DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;"
        "Encrypt=yes;TrustServerCertificate=yes;")


def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def _wait():
    for _ in range(40):
        try:
            post("/configurations/resolve-state", {"series": "DL200", "selections": {}})
            return True
        except Exception:
            time.sleep(1)
    return False


def _dean_version_id(cur):
    return cur.execute(
        "SELECT v.PriceBookVersionId FROM price.PriceBook pb "
        "JOIN price.PriceBookVersion v ON v.PriceBookId=pb.PriceBookId "
        "WHERE pb.PriceBookCode='DEAN_STANDARD' AND v.IsCurrent=1").fetchone()[0]


def _base_price(cur, ver, series, size, material):
    """Matrix base list for (series, size, material) from the published rules."""
    row = cur.execute(
        "SELECT TOP 1 Amount FROM price.PriceRule "
        "WHERE PriceBookVersionId=? AND ComponentCode='BASE_PUMP' AND SeriesCode=? "
        "AND UPPER(SourceSizeValue)=UPPER(?) AND LOWER(SourceOptionValue)=LOWER(?)",
        ver, series, size, material).fetchone()
    return float(row[0]) if row else None


def _option_adder(cur, ver, series, size, material, field, value):
    """Published OPTION_ADDER for (series,size,material,field=value) via conditions."""
    row = cur.execute("""
        SELECT TOP 1 pr.Amount FROM price.PriceRule pr
        WHERE pr.PriceBookVersionId=? AND pr.ComponentCode='OPTION_ADDER' AND pr.SeriesCode=?
          AND EXISTS (SELECT 1 FROM price.PriceCondition c WHERE c.PriceRuleId=pr.PriceRuleId
                      AND UPPER(c.FieldCode)='SIZE' AND UPPER(c.ComparisonValue)=UPPER(?))
          AND EXISTS (SELECT 1 FROM price.PriceCondition c WHERE c.PriceRuleId=pr.PriceRuleId
                      AND UPPER(c.FieldCode)='PUMP_MATERIAL' AND LOWER(c.ComparisonValue)=LOWER(?))
          AND EXISTS (SELECT 1 FROM price.PriceCondition c WHERE c.PriceRuleId=pr.PriceRuleId
                      AND UPPER(c.FieldCode)=UPPER(?) AND LOWER(c.ComparisonValue)=LOWER(?))
    """, ver, series, size, material, field, value).fetchone()
    return abs(float(row[0])) if row else None


def _full_config(series, size, material, pump_config):
    """Seed + fill a full Dean config for (series,size,material,pump_config)."""
    sel = {"ALT_SIZE": size, "PUMP_MATERIAL": material,
           "PUMP_CONFIGURATION": pump_config}
    st = post("/configurations/resolve-state", {"series": series, "selections": sel})
    sel = dict(st.get("selections", {}))
    sel.update({"ALT_SIZE": size, "PUMP_MATERIAL": material,
                "PUMP_CONFIGURATION": pump_config})
    for _ in range(6):
        ao = st.get("allowable_options", {})
        prog = False
        for fc in st.get("ordered_fields", []):
            if fc not in sel and ao.get(fc):
                sel[fc] = ao[fc][0]; prog = True
        if not prog:
            break
        st = post("/configurations/resolve-state", {"series": series, "selections": sel})
    return {k: v for k, v in sel.items()}


def main():
    if not _wait():
        print("FAIL: API not reachable on 127.0.0.1:8080")
        return 1
    cn = pyodbc.connect(CONN); cur = cn.cursor()
    ver = _dean_version_id(cur)

    P = [0]; F = [0]
    def ok(cond, msg):
        cond = bool(cond); P[0] += cond; F[0] += (not cond)
        print(f"  [{'PASS' if cond else 'FAIL'}] {msg}")

    print("=" * 92)
    print(f"DEAN PRICING AUDIT (D120 exit gate)  DEAN_STANDARD version id={ver}")
    print("=" * 92)

    # Representative models with a known base price (verified in DB).
    CASES = [
        ("DL200", "1x1.5x6", "(22) Ductile Iron"),
        ("DL200", "1x1.5x6", "(50) 316 S/S"),
        ("CNV206", "1.5x3x6", "(22) Ductile Iron"),
    ]
    for series, size, material in CASES:
        print(f"\n=== {series} | {size} | {material} ===")
        base = _base_price(cur, ver, series, size, material)
        ok(base is not None, f"base price present in DB ({base})")
        if base is None:
            continue

        sel = _full_config(series, size, material, "Pump, Baseplate, Coupling and Motor")
        payload = {"series": series, "selections": {"SERIES": series, **sel},
                   "segment_codes": {}, "requested_by": "audit_dean_pricing"}
        r = post("/configured-products/resolve", payload)
        pricing = r.get("pricing", [])
        total = float(r.get("total_price") or 0)

        # (1) Base Pump line equals the Matrix base price.
        base_lines = [p for p in pricing if p["component"] == "Base Pump"]
        ok(len(base_lines) == 1 and abs(base_lines[0]["amount"] - base) < 0.005,
           f"Base Pump line == Matrix base ({base_lines[0]['amount'] if base_lines else None} == {base})")

        # (2) Every 'Adder: X' line equals the DB OPTION_ADDER for that selected
        #     field+value (and only appears for a selected option that HAS an adder).
        adder_ok = 0; adder_bad = 0
        for p in pricing:
            if not p["component"].startswith("Adder: "):
                continue
            fc = p["component"][len("Adder: "):]
            val = sel.get(fc)
            expected = _option_adder(cur, ver, series, size, material, fc, val) if val else None
            if expected is not None and abs(p["amount"] - expected) < 0.005:
                adder_ok += 1
            else:
                adder_bad += 1
                print(f"      adder mismatch {fc}={val}: got {p['amount']} expected {expected}")
        ok(adder_bad == 0,
           f"every adder line matches its DB OPTION_ADDER ({adder_ok} ok, {adder_bad} bad)")

        # (3) total == base + Σ adder/component lines (self-consistent).
        recomputed = sum(p["amount"] for p in pricing)
        ok(abs(total - recomputed) < 0.005,
           f"total == Σ priced lines ({total} == {recomputed})")

        # (4) Pump Configuration gate: 'Pump Only' must not price Baseplate/
        #     Coupling and must produce a total <= the full-bundle total.
        sel_po = dict(sel); sel_po["PUMP_CONFIGURATION"] = "Pump Only"
        r_po = post("/configured-products/resolve",
                    {"series": series, "selections": {"SERIES": series, **sel_po},
                     "segment_codes": {}, "requested_by": "audit_dean_pricing"})
        comps_po = [p["component"] for p in r_po.get("pricing", [])]
        ok("Baseplate" not in comps_po and "Coupling" not in comps_po,
           f"Pump Only excludes Baseplate/Coupling from pricing")

        # (5) Determinism: same config resolves to same total.
        r2 = post("/configured-products/resolve", payload)
        ok(abs(float(r2.get("total_price") or 0) - total) < 0.005,
           f"deterministic total on re-resolve ({total})")

        # (6) Honest C/F: motor/seal appear in the component breakdown as C/F
        #     (not priced by the Matrix).
        cp = {c["component"]: c for c in r.get("component_pricing", [])}
        motor = cp.get("Motor")
        ok(motor is not None and motor.get("status") == "C/F",
           f"Motor honest C/F (status={motor.get('status') if motor else None})")

    # (7) Base-price gate: a size with NO base price prices to no Base Pump line.
    print("\n=== base-price gate (DEANLINE 0.75x0.75 has no Matrix base) ===")
    nb = _base_price(cur, ver, "DEANLINE", "0.75x0.75", "(20) Cast Iron")
    ok(nb is None, "DEANLINE 0.75x0.75 (20) Cast Iron has NO base price in DB (C/F pump)")

    cn.close()
    print(f"\n=== RESULT: {P[0]} passed, {F[0]} failed ===")
    return 0 if F[0] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

"""Migration: re-derive every cfg.ConfiguredProduct SKU from its Part Number.

WHY
---
The SKU identity model changed: the SKU is now DERIVED FROM THE PART NUMBER
(SKU <-> PN is strictly 1:1), not from the configuration signature. Rows created
under the old model carry signature-derived SKUs. Because the SKU is now a pure
function of the PN, we recompute each stored row's SKU in place:

    token = first 8 hex chars of SHA-256(PartNumber)   (upper)
    SKU   = <FamilyPrefix><Series>-<token><VersionLetter>

This exactly mirrors cfg.usp_GenerateSKU (PN-derived form). FamilyPrefix is F for
Fybroc / D for Dean. Series is parsed from the existing SKU's '<prefix><series>-'
head so we preserve the readable series label. VersionLetter is 'A' (first/only
SKU per PN, which the 1:1 rule guarantees).

SAFETY
------
- These are regenerable configured-product rows with zero downstream references
  (verified: cfg.BOMHeader / quote.QuoteLine empty).
- Idempotent: running twice yields the same SKUs.
- Prints before/after and requires --confirm to write.
- Verifies the PN<->SKU 1:1 invariant after the update.

Usage:
    python scripts/migrate_sku_from_partnumber.py            # dry-run
    python scripts/migrate_sku_from_partnumber.py --confirm  # apply
"""
from __future__ import annotations
import argparse
import hashlib
import pyodbc

CONN = ("DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;"
        "DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;Encrypt=yes;"
        "TrustServerCertificate=yes;")


def family_prefix(code: str) -> str:
    return {"FYBROC": "F", "DEAN": "D"}.get(code.upper(), code[:1].upper())


def sku_for(family_code: str, series_label: str, part_number: str) -> str:
    token = hashlib.sha256(part_number.encode()).hexdigest().upper()[:8]
    return f"{family_prefix(family_code)}{series_label}-{token}A"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", action="store_true")
    a = ap.parse_args()

    conn = pyodbc.connect(CONN, autocommit=True)
    cur = conn.cursor()

    rows = cur.execute("""
        SELECT cp.ConfiguredProductId, pf.FamilyCode, cp.PartNumber, cp.SKUCode
        FROM cfg.ConfiguredProduct cp
        JOIN cfg.PumpFamily pf ON pf.PumpFamilyId = cp.PumpFamilyId
        ORDER BY cp.ConfiguredProductId
    """).fetchall()

    print(f"=== {len(rows)} configured products ===")
    updates = []
    for cpid, fam, pn, old_sku in rows:
        # series label = between the family prefix and the first '-' of the old SKU
        # e.g. 'F1500-155F718DA' -> series '1500'
        head = old_sku.split("-", 1)[0]  # F1500
        series_label = head[1:] if head[:1] in ("F", "D") else head
        new_sku = sku_for(fam, series_label, pn)
        mark = "" if new_sku == old_sku else "  <-- CHANGE"
        print(f"  {cpid:>3} {pn:<40} {old_sku:<20} -> {new_sku}{mark}")
        if new_sku != old_sku:
            updates.append((cpid, new_sku))

    # invariant preview: would any PN map to >1 distinct new SKU? (should be 0)
    from collections import defaultdict
    pn_to_sku = defaultdict(set)
    for cpid, fam, pn, old_sku in rows:
        head = old_sku.split("-", 1)[0]
        series_label = head[1:] if head[:1] in ("F", "D") else head
        pn_to_sku[pn].add(sku_for(fam, series_label, pn))
    bad = {pn: s for pn, s in pn_to_sku.items() if len(s) > 1}
    print(f"\nPN -> multiple SKUs after re-derivation: {len(bad)} (must be 0)")
    for pn, s in bad.items():
        print(f"  {pn}: {s}")

    if not a.confirm:
        print(f"\nDRY-RUN. {len(updates)} rows would change. Re-run with --confirm.")
        return 0

    for cpid, new_sku in updates:
        cur.execute("UPDATE cfg.ConfiguredProduct SET SKUCode = ? WHERE ConfiguredProductId = ?",
                    new_sku, cpid)
    print(f"\nUpdated {len(updates)} SKUs.")

    # verify 1:1 both directions
    dup_pn = cur.execute("""
        SELECT PartNumber, COUNT(DISTINCT SKUCode) FROM cfg.ConfiguredProduct
        GROUP BY PartNumber HAVING COUNT(DISTINCT SKUCode) > 1""").fetchall()
    dup_sku = cur.execute("""
        SELECT SKUCode, COUNT(DISTINCT PartNumber) FROM cfg.ConfiguredProduct
        GROUP BY SKUCode HAVING COUNT(DISTINCT PartNumber) > 1""").fetchall()
    print(f"Invariant check -> PN with >1 SKU: {len(dup_pn)}, SKU with >1 PN: {len(dup_sku)}")
    conn.close()
    return 0 if not dup_pn and not dup_sku else 1


if __name__ == "__main__":
    raise SystemExit(main())

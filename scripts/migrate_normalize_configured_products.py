"""F160 follow-up migration: reset regenerable configured-product test rows so
they repopulate with NORMALIZED (deterministic, sort_keys) signatures.

WHY
---
The resolve endpoint now canonicalizes the configuration JSON (sort_keys) before
hashing, so the same pump configuration always yields the same signature -> same
SKU -> reused Part Number (and different configurations yield different ones).
Rows persisted BEFORE that fix carry legacy, order-dependent signatures. Because
those rows have NO downstream references (cfg.BOMHeader and quote.QuoteLine are
empty) and were all created by debug/audit/oracle/UI test runs, the cleanest way
to make the store consistent is to clear the Fybroc rows and let them regenerate
through the fixed endpoint.

SAFETY
------
- Only deletes cfg.ConfiguredProduct rows for the FYBROC family.
- Refuses to run if ANY row is referenced by a BOM or Quote line.
- Prints a full inventory before deleting and requires --confirm to act.

Usage:
    python scripts/migrate_normalize_configured_products.py            # dry-run
    python scripts/migrate_normalize_configured_products.py --confirm  # apply
"""
from __future__ import annotations
import argparse
import pyodbc

CONN = ("DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;"
        "DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;Encrypt=yes;"
        "TrustServerCertificate=yes;")
FAMILY = "FYBROC"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", action="store_true", help="actually delete")
    a = ap.parse_args()

    conn = pyodbc.connect(CONN, autocommit=True)
    cur = conn.cursor()

    fam_id = cur.execute(
        "SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode = ?", FAMILY
    ).fetchone()
    if not fam_id:
        print(f"FAIL: family {FAMILY} not found"); return 1
    fam_id = fam_id[0]

    rows = cur.execute(
        "SELECT ConfiguredProductId, PartNumber, SKUCode, CreatedBy "
        "FROM cfg.ConfiguredProduct WHERE PumpFamilyId = ? "
        "ORDER BY ConfiguredProductId", fam_id).fetchall()
    print(f"=== {FAMILY} configured products: {len(rows)} rows ===")
    for r in rows:
        print(f"  {r[0]:>3} {r[1]:<40} {r[2]:<20} {r[3]}")

    ids = [r[0] for r in rows]
    if not ids:
        print("Nothing to migrate."); return 0

    # Guard: refuse if anything downstream references these rows.
    def _refs(table, col):
        exists = cur.execute(
            "SELECT COUNT(*) FROM sys.objects WHERE object_id=OBJECT_ID(?) AND type='U'",
            table).fetchone()[0]
        if not exists:
            return 0
        placeholders = ",".join("?" * len(ids))
        return cur.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {col} IN ({placeholders})", *ids
        ).fetchone()[0]

    bom_refs = _refs("cfg.BOMHeader", "ConfiguredProductId")
    quote_refs = _refs("quote.QuoteLine", "ConfiguredProductId")
    print(f"\nDownstream references -> BOMHeader: {bom_refs}, QuoteLine: {quote_refs}")
    if bom_refs or quote_refs:
        print("REFUSING: some rows are referenced downstream; migrate manually.")
        return 2

    if not a.confirm:
        print("\nDRY-RUN. Re-run with --confirm to delete these rows "
              "(they will regenerate with normalized signatures on next resolve).")
        return 0

    n = cur.execute(
        "DELETE FROM cfg.ConfiguredProduct WHERE PumpFamilyId = ?", fam_id).rowcount
    print(f"\nDeleted {n} rows. They will repopulate with normalized signatures.")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

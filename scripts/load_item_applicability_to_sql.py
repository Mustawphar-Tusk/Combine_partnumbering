"""Load the corrected Fybroc Items applicability model into cfg.ItemApplicability.

Source: docs/evidence/F120/FYBROC_ITEMS_HIERARCHY_MODEL.json (items.rows, 467
item records). Normalized to one row per (series, item, applicable field).

Idempotent: ensures the table exists (sql/20_...) and reloads for the active
publication + FYBROC family.
"""
import json
from pathlib import Path

import pyodbc

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "docs" / "evidence" / "F120" / "FYBROC_ITEMS_HIERARCHY_MODEL.json"
DDL = ROOT / "sql" / "20_Create_Item_Applicability.sql"

conn_str = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;DATABASE=PumpConfiguratorDB;"
    "Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;"
)


def main():
    d = json.loads(MODEL.read_text(encoding="utf-8"))
    item_rows = d["items"]["rows"]

    conn = pyodbc.connect(conn_str, autocommit=True)
    cur = conn.cursor()

    for batch in DDL.read_text(encoding="utf-8").split("\nGO"):
        if batch.strip():
            cur.execute(batch)

    pub_id = cur.execute(
        "SELECT MetadataPublicationId FROM cfg.MetadataPublication WHERE Status='Active'"
    ).fetchone()[0]
    family_id = cur.execute(
        "SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode='FYBROC'"
    ).fetchone()[0]

    cur.execute(
        "DELETE FROM cfg.ItemApplicability WHERE MetadataPublicationId=? AND PumpFamilyId=?",
        pub_id, family_id,
    )
    cur.execute(
        "DELETE FROM cfg.ItemRegistry WHERE MetadataPublicationId=? AND PumpFamilyId=?",
        pub_id, family_id,
    )

    applic_rows = []
    registry_rows = []
    for r in item_rows:
        series = str(r["series"]).strip()
        item = str(r["item"]).strip()
        fields = r.get("applicable_fields", []) or []
        # Registry: EVERY item record, incl. zero-field items, so none are lost.
        registry_rows.append((pub_id, family_id, series, item, len(fields)))
        for field in fields:
            applic_rows.append((pub_id, family_id, series, item, str(field)))

    conn.autocommit = False
    batch_size = 1000
    for i in range(0, len(registry_rows), batch_size):
        cur.executemany(
            "INSERT INTO cfg.ItemRegistry "
            "(MetadataPublicationId, PumpFamilyId, SeriesCode, ItemCode, ApplicableFieldCount) "
            "VALUES (?,?,?,?,?)",
            registry_rows[i:i + batch_size],
        )
    for i in range(0, len(applic_rows), batch_size):
        cur.executemany(
            "INSERT INTO cfg.ItemApplicability "
            "(MetadataPublicationId, PumpFamilyId, SeriesCode, ItemCode, FieldCode) "
            "VALUES (?,?,?,?,?)",
            applic_rows[i:i + batch_size],
        )
    conn.commit()

    registry_total = cur.execute(
        "SELECT COUNT(*) FROM cfg.ItemRegistry WHERE MetadataPublicationId=? AND PumpFamilyId=?",
        pub_id, family_id).fetchone()[0]
    applic_total = cur.execute(
        "SELECT COUNT(*) FROM cfg.ItemApplicability WHERE MetadataPublicationId=? AND PumpFamilyId=?",
        pub_id, family_id).fetchone()[0]
    zero_field = cur.execute(
        "SELECT COUNT(*) FROM cfg.ItemRegistry WHERE MetadataPublicationId=? AND PumpFamilyId=? AND ApplicableFieldCount=0",
        pub_id, family_id).fetchone()[0]
    print(f"cfg.ItemRegistry item records: {registry_total}  (expected 467)")
    print(f"  of which zero-applicable-field items: {zero_field}  (expected 208)")
    print(f"cfg.ItemApplicability (series,item,field) rows: {applic_total}")

    print("\nBy series (registry items / applicability field-rows):")
    for r in cur.execute(
        "SELECT reg.SeriesCode, COUNT(*) AS items, "
        "       ISNULL(SUM(reg.ApplicableFieldCount),0) AS field_rows "
        "FROM cfg.ItemRegistry reg "
        "WHERE reg.MetadataPublicationId=? AND reg.PumpFamilyId=? "
        "GROUP BY reg.SeriesCode ORDER BY reg.SeriesCode",
        pub_id, family_id).fetchall():
        print(f"  {r[0]:<6} items={r[1]:<4} field_rows={r[2]}")

    conn.close()


if __name__ == "__main__":
    main()

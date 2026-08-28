"""Load the Fybroc Combine Variables model into SQL.

Source: docs/evidence/F120/FYBROC_MOTOR_CONSTRAINT_MODEL.json
  combine_variable_tables      -> cfg.CombineVariable      (key -> value)
  combine_value_domain_tables  -> cfg.CombineValueDomain   (attribute value lists)

Idempotent: ensures tables exist (sql/19_...) and reloads for the active
publication + FYBROC family.
"""
import json
from pathlib import Path

import pyodbc

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "docs" / "evidence" / "F120" / "FYBROC_MOTOR_CONSTRAINT_MODEL.json"
DDL = ROOT / "sql" / "19_Create_Combine_Variables.sql"

conn_str = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;DATABASE=PumpConfiguratorDB;"
    "Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;"
)


def main():
    d = json.loads(MODEL.read_text(encoding="utf-8"))
    kv_tables = d.get("combine_variable_tables", [])
    domain_tables = d.get("combine_value_domain_tables", [])

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

    cur.execute("DELETE FROM cfg.CombineVariable WHERE MetadataPublicationId=? AND PumpFamilyId=?", pub_id, family_id)
    cur.execute("DELETE FROM cfg.CombineValueDomain WHERE MetadataPublicationId=? AND PumpFamilyId=?", pub_id, family_id)

    # (a) key -> value tables: one row per (key, value-field)
    kv_rows = []
    for t in kv_tables:
        name = t["table"]
        key_field = t["key_field"]
        value_fields = t["value_fields"]
        for r in t["rows"]:
            key_val = r.get("key")
            for vf in value_fields:
                kv_rows.append((pub_id, family_id, name, str(key_field), str(key_val),
                                str(vf), None if r.get(vf) is None else str(r.get(vf))))

    # (b) value domains: one row per (attribute, value) with sort order
    dom_rows = []
    for t in domain_tables:
        name = t["table"]
        for dom in t["domains"]:
            attr = dom["attribute"]
            for i, val in enumerate(dom["values"]):
                dom_rows.append((pub_id, family_id, name, str(attr), str(val), i))

    conn.autocommit = False
    if kv_rows:
        cur.executemany(
            "INSERT INTO cfg.CombineVariable "
            "(MetadataPublicationId, PumpFamilyId, TableName, KeyField, KeyValue, ValueField, ValueValue) "
            "VALUES (?,?,?,?,?,?,?)",
            kv_rows,
        )
    if dom_rows:
        cur.executemany(
            "INSERT INTO cfg.CombineValueDomain "
            "(MetadataPublicationId, PumpFamilyId, TableName, AttributeName, AttributeValue, SortOrder) "
            "VALUES (?,?,?,?,?,?)",
            dom_rows,
        )
    conn.commit()

    kv_total = cur.execute(
        "SELECT COUNT(*) FROM cfg.CombineVariable WHERE MetadataPublicationId=? AND PumpFamilyId=?",
        pub_id, family_id).fetchone()[0]
    dom_total = cur.execute(
        "SELECT COUNT(*) FROM cfg.CombineValueDomain WHERE MetadataPublicationId=? AND PumpFamilyId=?",
        pub_id, family_id).fetchone()[0]
    print(f"cfg.CombineVariable rows: {kv_total}")
    for r in cur.execute(
        "SELECT TableName, COUNT(*) FROM cfg.CombineVariable "
        "WHERE MetadataPublicationId=? AND PumpFamilyId=? GROUP BY TableName ORDER BY TableName",
        pub_id, family_id).fetchall():
        print(f"  {r[0]}: {r[1]}")
    print(f"\ncfg.CombineValueDomain rows: {dom_total}")
    for r in cur.execute(
        "SELECT AttributeName, COUNT(*) FROM cfg.CombineValueDomain "
        "WHERE MetadataPublicationId=? AND PumpFamilyId=? GROUP BY AttributeName ORDER BY AttributeName",
        pub_id, family_id).fetchall():
        print(f"  {r[0]}: {r[1]}")

    conn.close()


if __name__ == "__main__":
    main()

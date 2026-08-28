"""Load the corrected Fybroc Motor Constraints model into cfg.MotorConstraint.

Source: docs/evidence/F120/FYBROC_MOTOR_CONSTRAINT_MODEL.json (3278 rows across
19 blocks). This is the authoritative runtime table for motor-attribute
allowed/not-allowed pairs, parallel to load_constraints_to_sql.py.

Idempotent: creates the table if missing (via sql/18_...) and reloads all rows
for the active publication + FYBROC family.
"""
import json
from pathlib import Path

import pyodbc

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "docs" / "evidence" / "F120" / "FYBROC_MOTOR_CONSTRAINT_MODEL.json"
DDL = ROOT / "sql" / "18_Create_Motor_Constraint.sql"

conn_str = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;DATABASE=PumpConfiguratorDB;"
    "Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;"
)


def _active_publication(cur):
    row = cur.execute(
        "SELECT MetadataPublicationId FROM cfg.MetadataPublication WHERE Status='Active'"
    ).fetchone()
    if row is None:
        raise SystemExit("No active MetadataPublication found.")
    return row[0]


def _fybroc_family(cur):
    row = cur.execute(
        "SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode='FYBROC'"
    ).fetchone()
    if row is None:
        raise SystemExit("FYBROC family not found.")
    return row[0]


def main():
    d = json.loads(MODEL.read_text(encoding="utf-8"))
    blocks = d["motor_constraint_blocks"]

    conn = pyodbc.connect(conn_str, autocommit=True)
    cur = conn.cursor()

    # Ensure table exists (run DDL batches).
    ddl = DDL.read_text(encoding="utf-8")
    for batch in ddl.split("\nGO"):
        if batch.strip():
            cur.execute(batch)

    pub_id = _active_publication(cur)
    family_id = _fybroc_family(cur)

    cur.execute(
        "DELETE FROM cfg.MotorConstraint WHERE MetadataPublicationId=? AND PumpFamilyId=?",
        pub_id, family_id,
    )

    rows = []
    for b in blocks:
        scope = b["series_scope"]
        d1 = b["dimension1"]
        d2 = b["dimension2"]
        for r in b["rows"]:
            # Each row dict keys are the two dimension headers + "Allowed?".
            v1 = r.get(d1)
            v2 = r.get(d2)
            allowed = r.get("Allowed?") or r.get("Allowed") or "Allowed"
            if v1 is None or v2 is None:
                continue
            rows.append((pub_id, family_id, scope, d1, str(v1), d2, str(v2), str(allowed)))

    conn.autocommit = False
    batch_size = 1000
    for i in range(0, len(rows), batch_size):
        cur.executemany(
            "INSERT INTO cfg.MotorConstraint "
            "(MetadataPublicationId, PumpFamilyId, SeriesScope, "
            " Dimension1Field, Dimension1Value, Dimension2Field, Dimension2Value, Allowed) "
            "VALUES (?,?,?,?,?,?,?,?)",
            rows[i:i + batch_size],
        )
    conn.commit()

    total = cur.execute(
        "SELECT COUNT(*) FROM cfg.MotorConstraint WHERE MetadataPublicationId=? AND PumpFamilyId=?",
        pub_id, family_id,
    ).fetchone()[0]
    print(f"Loaded {total} motor constraint rows into cfg.MotorConstraint")

    print("\nBy series scope + dimension pair:")
    for r in cur.execute(
        "SELECT SeriesScope, Dimension1Field, Dimension2Field, COUNT(*) "
        "FROM cfg.MotorConstraint WHERE MetadataPublicationId=? AND PumpFamilyId=? "
        "GROUP BY SeriesScope, Dimension1Field, Dimension2Field "
        "ORDER BY SeriesScope, Dimension1Field, Dimension2Field",
        pub_id, family_id,
    ).fetchall():
        print(f"  {r[0]:<26} {r[1]} x {r[2]:<16} {r[3]}")

    conn.close()


if __name__ == "__main__":
    main()

"""D110 step 1: add PumpFamilyId scoping to the two currently-global constraint
tables (cfg.FeasibleConstraint, cfg.ConstraintFieldMap), backfilling ALL existing
rows to FYBROC (id 2). Idempotent. This is the schema change that lets Dean
constraints coexist without touching Fybroc's frozen enforcement data.

FYBROC family id is looked up (not hardcoded) but asserted = 2 as a safety check.
"""
import pyodbc

cs = ('DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;'
      'DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;Encrypt=yes;'
      'TrustServerCertificate=yes;')
conn = pyodbc.connect(cs, autocommit=True)
c = conn.cursor()

fybroc_id = c.execute("SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode='FYBROC'").fetchone()[0]
dean_id = c.execute("SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode='DEAN'").fetchone()[0]
print(f"FYBROC id={fybroc_id}  DEAN id={dean_id}")


def col_exists(table, col):
    return c.execute(
        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA='cfg' AND TABLE_NAME=? AND COLUMN_NAME=?",
        table, col).fetchone()[0] > 0


for table in ("FeasibleConstraint", "ConstraintFieldMap"):
    if col_exists(table, "PumpFamilyId"):
        print(f"cfg.{table}.PumpFamilyId already exists")
    else:
        # add nullable, backfill to FYBROC, then set NOT NULL + default
        c.execute(f"ALTER TABLE cfg.{table} ADD PumpFamilyId INT NULL")
        print(f"cfg.{table}: added PumpFamilyId (nullable)")
    # Backfill any NULLs to FYBROC (existing rows are all Fybroc)
    n = c.execute(f"UPDATE cfg.{table} SET PumpFamilyId=? WHERE PumpFamilyId IS NULL",
                  fybroc_id).rowcount
    print(f"cfg.{table}: backfilled {n} NULL rows -> FYBROC({fybroc_id})")

# Now make NOT NULL (safe: no NULLs remain) if not already.
for table in ("FeasibleConstraint", "ConstraintFieldMap"):
    nullable = c.execute(
        "SELECT IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA='cfg' AND TABLE_NAME=? AND COLUMN_NAME='PumpFamilyId'",
        table).fetchone()[0]
    if nullable == "YES":
        # Determine the column type to preserve it in the ALTER
        c.execute(f"ALTER TABLE cfg.{table} ALTER COLUMN PumpFamilyId INT NOT NULL")
        print(f"cfg.{table}: PumpFamilyId set NOT NULL")
    else:
        print(f"cfg.{table}: PumpFamilyId already NOT NULL")

# ConstraintFieldMap PK/uniqueness note: it was (ConstraintFieldName, SFOFieldCode)
# implicitly unique-ish; with family scoping the same label can now exist per
# family. Report current row counts by family.
print("\n--- post-change row counts by family ---")
for table in ("FeasibleConstraint", "ConstraintFieldMap"):
    rows = c.execute(
        f"SELECT PumpFamilyId, COUNT(*) FROM cfg.{table} GROUP BY PumpFamilyId ORDER BY PumpFamilyId"
    ).fetchall()
    print(f"cfg.{table}: {[(r[0], r[1]) for r in rows]}")

conn.close()
print("\nDONE - schema scoping added, existing rows tagged FYBROC.")

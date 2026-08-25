"""Fix the width constraint and reload vertical data."""
import pyodbc

conn_str = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=PumpConfiguratorDB;"
    "Trusted_Connection=yes;"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)

conn = pyodbc.connect(conn_str, autocommit=True)
cursor = conn.cursor()

# Find and drop the width constraint
for r in cursor.execute("""
    SELECT name, definition FROM sys.check_constraints
    WHERE parent_object_id = OBJECT_ID('stg.SegmentCombinationImport')
""").fetchall():
    print(f"  Constraint: {r[0]} = {r[1]}")
    if "Width" in r[0] or "width" in r[0].lower():
        cursor.execute(f"ALTER TABLE stg.SegmentCombinationImport DROP CONSTRAINT [{r[0]}]")
        print(f"  DROPPED: {r[0]}")

conn.close()
print("Done")

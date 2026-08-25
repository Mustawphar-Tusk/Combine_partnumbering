import pyodbc
conn_str = "DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;"
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

# Check which seal options exist in combo table
for opt in ["custom", "no seal (single", "no seal (double", "no seal (no seal", "customer supplied"]:
    row = cursor.execute(
        "SELECT TOP 1 SegmentValue FROM cfg.vw_SegmentCombinationLookup "
        "WHERE SegmentCode='SEAL_ASSEMBLY' AND LOWER(SelectionsJson) LIKE ?",
        f"%{opt}%"
    ).fetchone()
    print(f"  '{opt}': {row[0] if row else 'NOT FOUND'}")

# Test the actual lookup the code does for "installed by fybroc" + "cro double inside"
print()
t1 = "Mechanical Seal Included"
t2 = "CRO Double Inside"
row2 = cursor.execute(
    "SELECT TOP 1 SegmentValue FROM cfg.vw_SegmentCombinationLookup "
    "WHERE SegmentCode='SEAL_ASSEMBLY' AND LOWER(SelectionsJson) LIKE ? AND LOWER(SelectionsJson) LIKE ?",
    f"%{t1.lower()}%", f"%{t2.lower()}%"
).fetchone()
print(f"Mechanical Seal + CRO: {row2[0] if row2 else 'NOT FOUND'}")

# Try 8-1T
t3 = "8-1T Double Inside"
row3 = cursor.execute(
    "SELECT TOP 1 SegmentValue FROM cfg.vw_SegmentCombinationLookup "
    "WHERE SegmentCode='SEAL_ASSEMBLY' AND LOWER(SelectionsJson) LIKE ? AND LOWER(SelectionsJson) LIKE ?",
    f"%{t1.lower()}%", f"%{t3.lower()}%"
).fetchone()
print(f"Mechanical Seal + 8-1T: {row3[0] if row3 else 'NOT FOUND'}")

conn.close()

"""Fix VocabularyMap gaps for vertical series seal and motor."""
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

# Check 5530 seal and motor options
print("5530 SEAL_OPTION:")
for r in cursor.execute(
    "SELECT DISTINCT OptionValue FROM cfg.SeriesFieldOption "
    "WHERE MetadataPublicationId=2 AND FieldCode='SEAL_OPTION' AND SeriesCode='5530'"
).fetchall():
    sfo = r[0]
    mapped = cursor.execute(
        "SELECT ComboValue FROM cfg.VocabularyMap WHERE FieldCode='SEAL_OPTION' AND LOWER(SFOValue)=?",
        sfo.lower(),
    ).fetchone()
    status = mapped[0] if mapped else "NO MAPPING"
    print(f"  {sfo!r:40} -> {status}")

print("\n5530 SEAL_TYPE:")
for r in cursor.execute(
    "SELECT DISTINCT OptionValue FROM cfg.SeriesFieldOption "
    "WHERE MetadataPublicationId=2 AND FieldCode='SEAL_TYPE' AND SeriesCode='5530'"
).fetchall():
    sfo = r[0]
    mapped = cursor.execute(
        "SELECT ComboValue FROM cfg.VocabularyMap WHERE FieldCode='SEAL_TYPE' AND LOWER(SFOValue)=?",
        sfo.lower(),
    ).fetchone()
    status = mapped[0] if mapped else "NO MAPPING"
    print(f"  {sfo!r:40} -> {status}")

print("\n5530 MOTOR_OPTION:")
for r in cursor.execute(
    "SELECT DISTINCT OptionValue FROM cfg.SeriesFieldOption "
    "WHERE MetadataPublicationId=2 AND FieldCode='MOTOR_OPTION' AND SeriesCode='5530'"
).fetchall():
    sfo = r[0]
    mapped = cursor.execute(
        "SELECT ComboValue FROM cfg.VocabularyMap WHERE FieldCode='MOTOR_OPTION' AND LOWER(SFOValue)=?",
        sfo.lower(),
    ).fetchone()
    status = mapped[0] if mapped else "NO MAPPING"
    print(f"  {sfo!r:40} -> {status}")

# Add any missing motor mappings
missing = [
    ("MOTOR_OPTION", "Motor Included", "supplied by fybroc"),
    ("MOTOR_OPTION", "Customer Supplied", "by others"),
]
for fc, cv, sv in missing:
    try:
        cursor.execute(
            "INSERT INTO cfg.VocabularyMap (FieldCode, ComboValue, SFOValue) VALUES (?,?,?)",
            fc, cv, sv,
        )
        print(f"\n  ADDED: {fc}: {sv} -> {cv}")
    except:
        pass

conn.close()

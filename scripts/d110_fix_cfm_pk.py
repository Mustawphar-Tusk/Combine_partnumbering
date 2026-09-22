"""D110: make cfg.ConstraintFieldMap PK composite (ConstraintFieldName,
PumpFamilyId) so the same constraint label can exist per family (e.g. 'Seal
Option' for both FYBROC and DEAN). The old PK was on ConstraintFieldName alone,
which blocks Dean labels that Fybroc also uses. Idempotent."""
import pyodbc

cs = ('DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;'
      'DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;Encrypt=yes;'
      'TrustServerCertificate=yes;')
c = pyodbc.connect(cs, autocommit=True).cursor()

# current PK name + columns
pk = c.execute("""
    SELECT i.name, STRING_AGG(col.name, ',') WITHIN GROUP (ORDER BY ic.key_ordinal)
    FROM sys.indexes i
    JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id
    JOIN sys.columns col ON col.object_id=i.object_id AND col.column_id=ic.column_id
    JOIN sys.objects o ON o.object_id=i.object_id
    JOIN sys.schemas s ON s.schema_id=o.schema_id
    WHERE s.name='cfg' AND o.name='ConstraintFieldMap' AND i.is_primary_key=1
    GROUP BY i.name
""").fetchone()

if pk and pk[1].lower() == "constraintfieldname,pumpfamilyid":
    print("PK already composite (ConstraintFieldName, PumpFamilyId)")
elif pk:
    print(f"current PK {pk[0]} on ({pk[1]}) -> recreating as composite")
    c.execute(f"ALTER TABLE cfg.ConstraintFieldMap DROP CONSTRAINT [{pk[0]}]")
    c.execute("ALTER TABLE cfg.ConstraintFieldMap "
              "ADD CONSTRAINT PK_ConstraintFieldMap "
              "PRIMARY KEY (ConstraintFieldName, PumpFamilyId)")
    print("composite PK created: PK_ConstraintFieldMap (ConstraintFieldName, PumpFamilyId)")
else:
    print("no PK found (unexpected) - adding composite PK")
    c.execute("ALTER TABLE cfg.ConstraintFieldMap "
              "ADD CONSTRAINT PK_ConstraintFieldMap "
              "PRIMARY KEY (ConstraintFieldName, PumpFamilyId)")

print("DONE")

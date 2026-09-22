"""D110 step: add a 4th leg (Option4Field/Option4Value, nullable) to
cfg.FeasibleConstraint so the single Dean 4-field codependency
(Table100: Seal Option x Gland Type x Flush Plan x Barrier Plan) can be modeled
as one joint allowed-tuple. Idempotent. Nullable => existing Fybroc 2/3-leg rows
are unaffected (Option4* stays NULL, treated as absent leg)."""
import pyodbc

cs = ('DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;'
      'DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;Encrypt=yes;'
      'TrustServerCertificate=yes;')
c = pyodbc.connect(cs, autocommit=True).cursor()


def col_exists(col):
    return c.execute(
        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA='cfg' AND TABLE_NAME='FeasibleConstraint' AND COLUMN_NAME=?",
        col).fetchone()[0] > 0


for col, ddl in [
    ("Option4Field", "ALTER TABLE cfg.FeasibleConstraint ADD Option4Field varchar(100) NULL"),
    ("Option4Value", "ALTER TABLE cfg.FeasibleConstraint ADD Option4Value nvarchar(500) NULL"),
]:
    if col_exists(col):
        print(f"cfg.FeasibleConstraint.{col} already exists")
    else:
        c.execute(ddl)
        print(f"cfg.FeasibleConstraint: added {col} (nullable)")

# sanity: existing rows have NULL Option4* (no accidental data)
n = c.execute("SELECT COUNT(*) FROM cfg.FeasibleConstraint WHERE Option4Field IS NOT NULL").fetchone()[0]
print(f"rows with non-null Option4Field: {n} (expected 0 before Dean load)")
print("DONE")

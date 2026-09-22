"""D110-STDX step: add a nullable SizeCode column to cfg.SeriesFieldOption so Dean
option applicability can be modeled PER MODEL (series + size), which the workbook
'Pump Options' sheet defines and which varies by size in 27/37 Dean series.

Backward-compatible + Fybroc-safe:
  * SizeCode is NULLABLE. All existing rows (Fybroc family + the current Dean
    load) keep SizeCode = NULL. No existing row is rewritten.
  * A series-level row (SizeCode NULL) means "applies to every size of the
    series" - this is exactly Fybroc's current semantics, so Fybroc behavior is
    unchanged. Dean will publish size-specific rows (SizeCode = e.g. '1x1.5x6').
  * The option-projection queries use (SizeCode IS NULL OR SizeCode = @size), so
    NULL rows always project (Fybroc) and size rows project only for that size.

Adds a supporting index on (MetadataPublicationId, PumpFamilyId, SeriesCode,
SizeCode, FieldCode) to keep the size-scoped reads fast.

Idempotent. Verifies Fybroc row count + SizeCode-NULL invariant before/after.
"""
import pyodbc

CS = ('DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;'
      'DATABASE=PumpConfiguratorDB;Trusted_Connection=yes;Encrypt=yes;'
      'TrustServerCertificate=yes;')
c = pyodbc.connect(CS, autocommit=True).cursor()


def col_exists(col):
    return c.execute(
        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA='cfg' AND TABLE_NAME='SeriesFieldOption' AND COLUMN_NAME=?",
        col).fetchone()[0] > 0


def index_exists(name):
    return c.execute(
        "SELECT COUNT(*) FROM sys.indexes WHERE name=? "
        "AND object_id=OBJECT_ID('cfg.SeriesFieldOption')", name).fetchone()[0] > 0


# --- pre-state (Fybroc = non-DEAN) ---
dean = c.execute("SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode='DEAN'").fetchone()[0]
fy_before = c.execute(
    "SELECT COUNT(*) FROM cfg.SeriesFieldOption WHERE PumpFamilyId<>?", dean).fetchone()[0]
print(f"DEAN family id={dean}  Fybroc(non-DEAN) SeriesFieldOption rows: {fy_before}")

# --- add column ---
if col_exists("SizeCode"):
    print("cfg.SeriesFieldOption.SizeCode already exists")
else:
    c.execute("ALTER TABLE cfg.SeriesFieldOption ADD SizeCode varchar(60) NULL")
    print("cfg.SeriesFieldOption: added SizeCode (nullable)")

# --- supporting index ---
IDX = "IX_SeriesFieldOption_SizeScope"
if index_exists(IDX):
    print(f"index {IDX} already exists")
else:
    c.execute(
        f"CREATE INDEX {IDX} ON cfg.SeriesFieldOption "
        "(MetadataPublicationId, PumpFamilyId, SeriesCode, SizeCode, FieldCode) "
        "INCLUDE (OptionValue, IsStandard)")
    print(f"created index {IDX}")

# --- widen the active-uniqueness index to include SizeCode ---------------------
# The active row uniqueness index was (MetadataPublicationId, PumpFamilyId,
# FieldCode, SeriesCode, OptionValue) WHERE IsActive=1. Dean now publishes the
# SAME (field, series, value) for multiple SIZES of a series, so SizeCode must be
# a key column or those per-size rows collide. Adding SizeCode as a 6th key is
# Fybroc-safe: Fybroc rows all have SizeCode=NULL, so their existing 5-tuple
# uniqueness is preserved exactly (constant NULL 6th column adds no ambiguity).
UX = "UX_SeriesFieldOption_ActiveRelation"


def ux_has_sizecode():
    return c.execute(
        "SELECT COUNT(*) FROM sys.index_columns ic "
        "JOIN sys.columns col ON col.object_id=ic.object_id AND col.column_id=ic.column_id "
        "WHERE ic.object_id=OBJECT_ID('cfg.SeriesFieldOption') "
        "AND ic.index_id=(SELECT index_id FROM sys.indexes "
        "                 WHERE object_id=OBJECT_ID('cfg.SeriesFieldOption') AND name=?) "
        "AND col.name='SizeCode'", UX).fetchone()[0] > 0


if not index_exists(UX):
    print(f"[warn] {UX} not found; skipping widen")
elif ux_has_sizecode():
    print(f"{UX} already includes SizeCode")
else:
    c.execute(f"DROP INDEX {UX} ON cfg.SeriesFieldOption")
    c.execute(
        f"CREATE UNIQUE INDEX {UX} ON cfg.SeriesFieldOption "
        "(MetadataPublicationId, PumpFamilyId, FieldCode, SeriesCode, SizeCode, OptionValue) "
        "WHERE IsActive=1")
    print(f"rebuilt {UX} to include SizeCode (Fybroc rows keep NULL SizeCode)")

# --- invariants: every existing row (esp. Fybroc) has SizeCode NULL, count unchanged ---
fy_after = c.execute(
    "SELECT COUNT(*) FROM cfg.SeriesFieldOption WHERE PumpFamilyId<>?", dean).fetchone()[0]
non_null = c.execute(
    "SELECT COUNT(*) FROM cfg.SeriesFieldOption WHERE SizeCode IS NOT NULL").fetchone()[0]
assert fy_before == fy_after, f"Fybroc row count changed {fy_before}->{fy_after}!"
print(f"Fybroc rows unchanged: {fy_after}")
print(f"rows with non-null SizeCode: {non_null} (expected 0 before size-aware Dean load)")
print("DONE")

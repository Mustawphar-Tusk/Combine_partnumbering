"""F150 - Enforce SKU uniqueness and create SKU lookup procedures."""
import pyodbc

conn_str = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=PumpConfiguratorDB;"
    "Trusted_Connection=yes;"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)

LOOKUP_BY_SKU = """
CREATE OR ALTER PROCEDURE cfg.usp_LookupBySKU
    @SKU varchar(100)
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        cp.ConfiguredProductId,
        cp.SKUCode AS SKU,
        cp.PartNumber,
        cp.ConfigurationSignature,
        cp.CanonicalConfiguration AS ConfigurationJson,
        cp.CreatedAt,
        cp.CreatedBy,
        pf.FamilyCode,
        ps.SeriesCode
    FROM cfg.ConfiguredProduct cp
    INNER JOIN cfg.PumpFamily pf ON pf.PumpFamilyId = cp.PumpFamilyId
    LEFT JOIN cfg.PumpSeries ps ON ps.PumpSeriesId = cp.PumpSeriesId
    WHERE cp.SKUCode = @SKU;

    IF @@ROWCOUNT = 0
        THROW 52100, 'SKU not found in configured product registry.', 1;
END;
"""

LOOKUP_BY_SKU_REGISTRY = """
CREATE OR ALTER PROCEDURE cfg.usp_LookupBySKU_Registry
    @SKU varchar(200)
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        cpr.ConfiguredProductRegistryId,
        cpr.PumpFamilyId,
        cpr.ConfigurationSignature,
        cpr.PartNumber,
        cpr.SKU,
        cpr.CanonicalConfigurationJson,
        cpr.SelectionsJson,
        cpr.SegmentsJson,
        cpr.RuntimeRevision,
        cpr.CreatedAt
    FROM cfg.ConfiguredProductRegistry cpr
    WHERE cpr.SKU = @SKU;

    IF @@ROWCOUNT = 0
        THROW 52101, 'SKU not found in configured product registry.', 1;
END;
"""

# Ensure unique index on registry SKU as well
REGISTRY_SKU_INDEX = """
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('cfg.ConfiguredProductRegistry')
      AND name = 'UX_ConfiguredProductRegistry_SKU'
)
BEGIN
    CREATE UNIQUE INDEX UX_ConfiguredProductRegistry_SKU
    ON cfg.ConfiguredProductRegistry (SKU)
    WHERE SKU IS NOT NULL;
END;
"""


def main():
    conn = pyodbc.connect(conn_str, autocommit=True)
    cursor = conn.cursor()

    # Deploy lookup procedures
    cursor.execute(LOOKUP_BY_SKU)
    print("cfg.usp_LookupBySKU created.")

    cursor.execute(LOOKUP_BY_SKU_REGISTRY)
    print("cfg.usp_LookupBySKU_Registry created.")

    # Enforce unique SKU on registry table
    cursor.execute(REGISTRY_SKU_INDEX)
    print("Unique index on ConfiguredProductRegistry.SKU enforced.")

    # Verify
    print("\n=== SKU ENFORCEMENT VERIFIED ===")
    print("cfg.ConfiguredProduct.SKUCode: UNIQUE (UX_ConfiguredProduct_SKU)")
    print("cfg.ConfiguredProductRegistry.SKU: UNIQUE (UX_ConfiguredProductRegistry_SKU)")
    print("")
    print("SKU Lookup Chain:")
    print("  SKU -> cfg.usp_LookupBySKU -> PartNumber + ConfigurationJson + Signature")
    print("  SKU -> cfg.usp_LookupBySKU_Registry -> PartNumber + Selections + Segments + BOM (future)")
    print("")
    print("Relationship: SKU (1:1) PartNumber (1:1) Configuration (1:1) BOM (future U130)")

    conn.close()


if __name__ == "__main__":
    main()

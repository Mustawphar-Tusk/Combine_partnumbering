"""Fix the identifier lookup to handle asterisk-suffixed standard values."""
import pyodbc
import json

conn_str = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=PumpConfiguratorDB;"
    "Trusted_Connection=yes;"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)

FN_SQL = """
CREATE OR ALTER FUNCTION cfg.fn_LookupIdentifierCode
(
    @MetadataPublicationId bigint,
    @PumpFamilyId int,
    @FieldCode varchar(100),
    @DisplayValue nvarchar(500)
)
RETURNS varchar(100)
AS
BEGIN
    DECLARE @Code varchar(100);

    -- Exact match first
    SELECT @Code = IdentifierCode
    FROM cfg.AttributeValue
    WHERE MetadataPublicationId = @MetadataPublicationId
      AND PumpFamilyId = @PumpFamilyId
      AND FieldCode = @FieldCode
      AND DisplayValue = @DisplayValue
      AND IsActive = 1;

    -- Fallback: try with asterisk suffix (standard material indicator)
    IF @Code IS NULL
    BEGIN
        SELECT @Code = IdentifierCode
        FROM cfg.AttributeValue
        WHERE MetadataPublicationId = @MetadataPublicationId
          AND PumpFamilyId = @PumpFamilyId
          AND FieldCode = @FieldCode
          AND DisplayValue = CONCAT(@DisplayValue, NCHAR(42))
          AND IsActive = 1;
    END;

    -- Fallback: try without asterisk (if input has it but DB doesn't)
    IF @Code IS NULL AND RIGHT(@DisplayValue, 1) = NCHAR(42)
    BEGIN
        SELECT @Code = IdentifierCode
        FROM cfg.AttributeValue
        WHERE MetadataPublicationId = @MetadataPublicationId
          AND PumpFamilyId = @PumpFamilyId
          AND FieldCode = @FieldCode
          AND DisplayValue = LEFT(@DisplayValue, LEN(@DisplayValue) - 1)
          AND IsActive = 1;
    END;

    RETURN @Code;
END;
"""


def main():
    conn = pyodbc.connect(conn_str, autocommit=True)
    cursor = conn.cursor()

    cursor.execute(FN_SQL)
    print("cfg.fn_LookupIdentifierCode updated with asterisk fallback.")

    # Test
    config = json.dumps({
        "SERIES": "1500", "FLANGE_TYPE": "ANSI", "SIZE": "1x1.5x6",
        "PUMP_MATERIAL": "VR-1", "IMPELLER_TRIM": "6.000",
        "PUMP_OPTIONS_CODE": "0001", "SEAL_MFG_CODE": "S", "SEAL_ASSY_CODE": "01",
        "OPTIONS_CODE": "01", "FRAME_SIZE_CODE": "01", "MOTOR_ASSY_CODE": "001",
        "MOTOR_MODS_CODE": "XXX", "TESTING_CODE": "00",
    })
    cursor.execute(
        "DECLARE @PN varchar(200); "
        "EXEC cfg.usp_GeneratePartNumber @FamilyCode=?, @ConfigurationJson=?, @PartNumber=@PN OUTPUT; "
        "SELECT @PN;",
        "FYBROC", config,
    )
    pn = cursor.fetchone()[0]
    print(f"SQL PN for 1500/ANSI/1x1.5x6/VR-1/6.000: {pn}")
    print(f"Expected prefix: FA11CA")
    print(f"Match: {'YES' if pn.startswith('FA11CA') else 'NO'}")

    conn.close()


if __name__ == "__main__":
    main()

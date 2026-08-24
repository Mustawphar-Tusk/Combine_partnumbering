"""F150 - Apply SQL Identifier Generation procedures and test."""
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

PROC_SQL = """
CREATE OR ALTER PROCEDURE cfg.usp_GeneratePartNumber
    @FamilyCode varchar(50),
    @ConfigurationJson nvarchar(max),
    @PartNumber varchar(200) OUTPUT
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @PumpFamilyId int, @MetaPubId bigint;

    SELECT @PumpFamilyId = PumpFamilyId
    FROM cfg.PumpFamily WHERE FamilyCode = @FamilyCode AND IsActive = 1;
    IF @PumpFamilyId IS NULL THROW 52000, 'Active pump family not found.', 1;

    SELECT TOP 1 @MetaPubId = MetadataPublicationId
    FROM cfg.MetadataPublication WHERE Status = 'Active'
    ORDER BY ActivatedAt DESC;
    IF @MetaPubId IS NULL THROW 52001, 'No active metadata publication.', 1;

    DECLARE @Brand varchar(10) = 'F',
            @SeriesFlange varchar(10),
            @Size varchar(10),
            @Material varchar(10),
            @Trim varchar(10),
            @PumpOptions varchar(10),
            @SealMfg varchar(10),
            @SealAssy varchar(10),
            @Options varchar(10),
            @FrameSize varchar(10),
            @MotorAssy varchar(10),
            @MotorMods varchar(10),
            @Testing varchar(10);

    DECLARE @Series varchar(100) = JSON_VALUE(@ConfigurationJson, '$.SERIES'),
            @Flange varchar(100) = JSON_VALUE(@ConfigurationJson, '$.FLANGE_TYPE');

    -- Series+Flange lookup: stored as "1500 (ANSI)" format
    DECLARE @SeriesKey nvarchar(500) = CONCAT(@Series, ' (', @Flange, ')');
    SET @SeriesFlange = cfg.fn_LookupIdentifierCode(@MetaPubId, @PumpFamilyId, 'SERIES', @SeriesKey);
    -- Fallback: try series alone (for series without flange like 2530)
    IF @SeriesFlange IS NULL
        SET @SeriesFlange = cfg.fn_LookupIdentifierCode(@MetaPubId, @PumpFamilyId, 'SERIES', @Series);

    SET @Size = cfg.fn_LookupIdentifierCode(@MetaPubId, @PumpFamilyId, 'SIZE',
        JSON_VALUE(@ConfigurationJson, '$.SIZE'));
    SET @Material = cfg.fn_LookupIdentifierCode(@MetaPubId, @PumpFamilyId, 'PUMP_MATERIAL',
        JSON_VALUE(@ConfigurationJson, '$.PUMP_MATERIAL'));
    SET @Trim = cfg.fn_LookupIdentifierCode(@MetaPubId, @PumpFamilyId, 'IMPELLER_TRIM',
        JSON_VALUE(@ConfigurationJson, '$.IMPELLER_TRIM'));

    -- Composite segment codes (pre-resolved by runtime)
    SET @PumpOptions = JSON_VALUE(@ConfigurationJson, '$.PUMP_OPTIONS_CODE');
    SET @SealMfg = JSON_VALUE(@ConfigurationJson, '$.SEAL_MFG_CODE');
    SET @SealAssy = JSON_VALUE(@ConfigurationJson, '$.SEAL_ASSY_CODE');
    SET @Options = JSON_VALUE(@ConfigurationJson, '$.OPTIONS_CODE');
    SET @FrameSize = JSON_VALUE(@ConfigurationJson, '$.FRAME_SIZE_CODE');
    SET @MotorAssy = JSON_VALUE(@ConfigurationJson, '$.MOTOR_ASSY_CODE');
    SET @MotorMods = JSON_VALUE(@ConfigurationJson, '$.MOTOR_MODS_CODE');
    SET @Testing = JSON_VALUE(@ConfigurationJson, '$.TESTING_CODE');

    -- Construct Part Number
    SET @PartNumber = CONCAT(
        @Brand,
        ISNULL(@SeriesFlange, '?'),
        ISNULL(@Size, '?'),
        ISNULL(@Material, '?'),
        ISNULL(@Trim, '??'),
        '-',
        ISNULL(@PumpOptions, '????'),
        '-',
        ISNULL(@SealMfg, '?'),
        ISNULL(@SealAssy, '??'),
        '-',
        ISNULL(@Options, '??'),
        '-',
        ISNULL(@FrameSize, '??'),
        ISNULL(@MotorAssy, '???'),
        '-',
        ISNULL(@MotorMods, '???'),
        '-',
        ISNULL(@Testing, '??')
    );
END;
"""


def main():
    conn = pyodbc.connect(conn_str, autocommit=True)
    cursor = conn.cursor()

    # Deploy the updated Part Number procedure
    cursor.execute(PROC_SQL)
    print("cfg.usp_GeneratePartNumber updated.")

    # Deploy the corrected SKU procedure (new format: F<Series>-<8char><VersionLetter>)
    cursor.execute("""
CREATE OR ALTER PROCEDURE cfg.usp_GenerateSKU
    @FamilyCode varchar(50),
    @SeriesCode varchar(100),
    @ConfigurationSignature char(64),
    @SKU varchar(100) OUTPUT
AS
BEGIN
    SET NOCOUNT ON;

    -- SKU format: <FamilyPrefix><Series>-<8-char token><VersionLetter>
    -- VersionLetter: A=first version, B=second, etc. (same for Fybroc and Dean)
    -- 8-char token is derived deterministically from the SHA-256 signature

    DECLARE @Version int = 1,
            @VersionLetter char(1),
            @Token varchar(8),
            @FamilyPrefix char(1);

    -- Family prefix: F for Fybroc, D for Dean
    SET @FamilyPrefix = CASE
        WHEN @FamilyCode = 'FYBROC' THEN 'F'
        WHEN @FamilyCode = 'DEAN' THEN 'D'
        ELSE LEFT(@FamilyCode, 1)
    END;

    -- Check if this signature already exists (reuse)
    IF EXISTS (
        SELECT 1 FROM cfg.ConfiguredProduct
        WHERE ConfigurationSignature = @ConfigurationSignature
    )
    BEGIN
        SELECT @SKU = SKUCode
        FROM cfg.ConfiguredProduct
        WHERE ConfigurationSignature = @ConfigurationSignature;
        RETURN;
    END;

    -- Generate 8-char deterministic token from signature
    SET @Token = UPPER(SUBSTRING(@ConfigurationSignature, 1, 8));

    -- Version letter: A=1, B=2, etc.
    SET @VersionLetter = CHAR(64 + @Version);  -- ASCII 65=A, 66=B...

    -- Build SKU: <FamilyPrefix><Series>-<Token><VersionLetter>
    SET @SKU = CONCAT(@FamilyPrefix, @SeriesCode, '-', @Token, @VersionLetter);
END;
""")
    print("cfg.usp_GenerateSKU updated (new format: F<Series>-<8char><VersionLetter>).")

    # Test with the V6 Smart Number example
    test_config = json.dumps({
        "SERIES": "1500",
        "FLANGE_TYPE": "ANSI",
        "SIZE": "1x2x10",
        "PUMP_MATERIAL": "VR-1A",
        "IMPELLER_TRIM": "9.250",
        "PUMP_OPTIONS_CODE": "1VC1",
        "SEAL_MFG_CODE": "S",
        "SEAL_ASSY_CODE": "03",
        "OPTIONS_CODE": "3G",
        "FRAME_SIZE_CODE": "04",
        "MOTOR_ASSY_CODE": "XXX",
        "MOTOR_MODS_CODE": "XXX",
        "TESTING_CODE": "00",
    })

    cursor.execute(
        "DECLARE @PN varchar(200); "
        "EXEC cfg.usp_GeneratePartNumber @FamilyCode=?, @ConfigurationJson=?, @PartNumber=@PN OUTPUT; "
        "SELECT @PN;",
        "FYBROC", test_config,
    )
    pn = cursor.fetchone()[0]
    print(f"\nGenerated PN: {pn}")
    print(f"Expected:     FA35FC-1VC1-S03-3G-04XXX-XXX-00")
    print(f"Match:        {'YES' if pn == 'FA35FC-1VC1-S03-3G-04XXX-XXX-00' else 'NO'}")

    # Test SKU with new format
    sig = "A1B2C3D4E5F6A7B8C9D0E1F2A3B4C5D6E7F8A9B0C1D2E3F4A5B6C7D8E9F0A1B2"
    cursor.execute(
        "DECLARE @SKU varchar(100); "
        "EXEC cfg.usp_GenerateSKU @FamilyCode=?, @SeriesCode=?, @ConfigurationSignature=?, @SKU=@SKU OUTPUT; "
        "SELECT @SKU;",
        "FYBROC", "1500", sig,
    )
    sku = cursor.fetchone()[0]
    expected_sku = "F1500-A1B2C3D4A"
    print(f"\nGenerated SKU: {sku}")
    print(f"Expected:      {expected_sku}")
    print(f"Match:         {'YES' if sku == expected_sku else 'NO'}")
    print(f"Format:        F<Series>-<8char><VersionLetter=A>")

    conn.close()


if __name__ == "__main__":
    main()

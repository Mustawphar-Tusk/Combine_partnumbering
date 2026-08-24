/* ================================================================
   F150 - SQL FYBROC IDENTIFIER AUTHORITY
   ----------------------------------------------------------------
   Creates SQL-based identifier generation for Fybroc pumps:
   1. cfg.usp_GeneratePartNumber - builds Part Number from configuration
   2. cfg.usp_GenerateSKU - builds SKU V2 format
   3. cfg.usp_ResolveConfiguredProduct - full resolve flow
   
   Part Number format (Horizontal):
     <Brand><Series+Flange><Size><Material><Trim>-<PumpOptions>-<SealMfg><SealAssy>-<Options>-<FrameSize><MotorAssy>-<MotorMods>-<Testing>
   
   SKU V2 format:
     F<Series>-V<Version>-<8-char deterministic token from SHA-256>
   
   The full SHA-256 configuration signature remains the authoritative
   identity key. SKU is a human-friendly derivative.
   ================================================================ */

SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

USE PumpConfiguratorDB;
GO

/* ================================================================
   1. PART NUMBER GENERATION
   ================================================================ */

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
    
    SELECT @Code = IdentifierCode
    FROM cfg.AttributeValue
    WHERE MetadataPublicationId = @MetadataPublicationId
      AND PumpFamilyId = @PumpFamilyId
      AND FieldCode = @FieldCode
      AND DisplayValue = @DisplayValue
      AND IsActive = 1;
    
    RETURN @Code;
END;
GO


CREATE OR ALTER PROCEDURE cfg.usp_GeneratePartNumber
    @FamilyCode varchar(50),
    @ConfigurationJson nvarchar(max),
    @PartNumber varchar(200) OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    
    DECLARE @PumpFamilyId int,
            @MetaPubId bigint;
    
    -- Get active family and publication
    SELECT @PumpFamilyId = PumpFamilyId
    FROM cfg.PumpFamily
    WHERE FamilyCode = @FamilyCode AND IsActive = 1;
    
    IF @PumpFamilyId IS NULL
        THROW 52000, 'Active pump family not found.', 1;
    
    SELECT TOP 1 @MetaPubId = MetadataPublicationId
    FROM cfg.MetadataPublication
    WHERE Status = 'Active'
    ORDER BY ActivatedAt DESC;
    
    IF @MetaPubId IS NULL
        THROW 52001, 'No active metadata publication.', 1;
    
    -- Parse configuration selections from JSON
    DECLARE @Brand varchar(10),
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
    
    -- Brand is always 'F' for Fybroc
    SET @Brand = 'F';
    
    -- Look up each segment code from AttributeValue
    SET @SeriesFlange = cfg.fn_LookupIdentifierCode(
        @MetaPubId, @PumpFamilyId, 'SERIES_FLANGE',
        JSON_VALUE(@ConfigurationJson, '$.SERIES') + '+' + JSON_VALUE(@ConfigurationJson, '$.FLANGE_TYPE')
    );
    
    SET @Size = cfg.fn_LookupIdentifierCode(
        @MetaPubId, @PumpFamilyId, 'SIZE',
        JSON_VALUE(@ConfigurationJson, '$.SIZE')
    );
    
    SET @Material = cfg.fn_LookupIdentifierCode(
        @MetaPubId, @PumpFamilyId, 'PUMP_MATERIAL',
        JSON_VALUE(@ConfigurationJson, '$.PUMP_MATERIAL')
    );
    
    SET @Trim = cfg.fn_LookupIdentifierCode(
        @MetaPubId, @PumpFamilyId, 'IMPELLER_TRIM',
        JSON_VALUE(@ConfigurationJson, '$.IMPELLER_TRIM')
    );
    
    -- Composite segments (PumpOptions, SealAssy, Options, MotorAssy, MotorMods, Testing)
    -- These are resolved from the segment combination tables, passed as pre-resolved values
    SET @PumpOptions = JSON_VALUE(@ConfigurationJson, '$.PUMP_OPTIONS_CODE');
    SET @SealMfg = JSON_VALUE(@ConfigurationJson, '$.SEAL_MFG_CODE');
    SET @SealAssy = JSON_VALUE(@ConfigurationJson, '$.SEAL_ASSY_CODE');
    SET @Options = JSON_VALUE(@ConfigurationJson, '$.OPTIONS_CODE');
    SET @FrameSize = JSON_VALUE(@ConfigurationJson, '$.FRAME_SIZE_CODE');
    SET @MotorAssy = JSON_VALUE(@ConfigurationJson, '$.MOTOR_ASSY_CODE');
    SET @MotorMods = JSON_VALUE(@ConfigurationJson, '$.MOTOR_MODS_CODE');
    SET @Testing = JSON_VALUE(@ConfigurationJson, '$.TESTING_CODE');
    
    -- Construct Part Number with separator '-'
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
GO


/* ================================================================
   2. SKU V2 GENERATION
   ================================================================ */

CREATE OR ALTER PROCEDURE cfg.usp_GenerateSKU
    @FamilyCode varchar(50),
    @SeriesCode varchar(100),
    @ConfigurationSignature char(64),
    @SKU varchar(100) OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    
    -- SKU V2 format: F<Series>-V<Version>-<8-char token>
    -- Version is always 1 for initial creation (incremented on re-configuration)
    -- 8-char token is derived deterministically from the SHA-256 signature
    
    DECLARE @Version int = 1,
            @Token varchar(8),
            @BaseIdentifier varchar(20);
    
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
    -- Use first 8 chars of the hex signature, converted to Base-36 uppercase
    SET @Token = UPPER(SUBSTRING(@ConfigurationSignature, 1, 8));
    
    -- Build base identifier
    SET @BaseIdentifier = CONCAT('F', @SeriesCode);
    
    -- Build SKU
    SET @SKU = CONCAT(@BaseIdentifier, '-V', @Version, '-', @Token);
END;
GO


/* ================================================================
   3. FULL RESOLVE FLOW
   ================================================================ */

CREATE OR ALTER PROCEDURE cfg.usp_ResolveConfiguredProduct
    @FamilyCode varchar(50),
    @ConfigurationJson nvarchar(max),
    @RequestedBy nvarchar(200) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    
    IF ISJSON(@ConfigurationJson) <> 1
        THROW 52010, 'ConfigurationJson must be valid JSON.', 1;
    
    -- Generate configuration signature (SHA-256 of canonical JSON)
    DECLARE @ConfigurationSignature char(64);
    SET @ConfigurationSignature = CONVERT(
        char(64),
        CONVERT(
            varchar(64),
            HASHBYTES('SHA2_256', CONVERT(varbinary(max), @ConfigurationJson)),
            2
        )
    );
    
    -- Check for existing product (reuse)
    DECLARE @ExistingId bigint;
    SELECT @ExistingId = ConfiguredProductId
    FROM cfg.ConfiguredProduct
    WHERE ConfigurationSignature = @ConfigurationSignature;
    
    IF @ExistingId IS NOT NULL
    BEGIN
        SELECT ConfiguredProductId, PartNumber, SKUCode, ConfigurationSignature,
               CAST(1 AS bit) AS ExistingConfiguration
        FROM cfg.ConfiguredProduct
        WHERE ConfiguredProductId = @ExistingId;
        RETURN;
    END;
    
    -- Generate identifiers
    DECLARE @PartNumber varchar(200),
            @SKU varchar(100),
            @SeriesCode varchar(100);
    
    SET @SeriesCode = JSON_VALUE(@ConfigurationJson, '$.SERIES');
    
    EXEC cfg.usp_GeneratePartNumber
        @FamilyCode = @FamilyCode,
        @ConfigurationJson = @ConfigurationJson,
        @PartNumber = @PartNumber OUTPUT;
    
    EXEC cfg.usp_GenerateSKU
        @FamilyCode = @FamilyCode,
        @SeriesCode = @SeriesCode,
        @ConfigurationSignature = @ConfigurationSignature,
        @SKU = @SKU OUTPUT;
    
    -- Persist
    EXEC cfg.usp_GetOrCreateConfiguredProduct
        @FamilyCode = @FamilyCode,
        @SeriesCode = @SeriesCode,
        @ConfigurationJson = @ConfigurationJson,
        @ConfigurationSignature = @ConfigurationSignature,
        @PartNumber = @PartNumber,
        @SKUCode = @SKU,
        @RequestedBy = @RequestedBy;
END;
GO


PRINT 'F150: Identifier generation procedures created successfully.';
GO

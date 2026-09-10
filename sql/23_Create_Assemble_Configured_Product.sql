/* ================================================================
   F150 - SQL-AUTHORITATIVE ASSEMBLY + IDENTITY (Option B)
   ----------------------------------------------------------------
   cfg.usp_AssembleConfiguredProduct is the single authority that:
     1. Assembles the final Part Number string in SQL from the RESOLVED
        segment codes (the API resolves composite segments respecting all
        constraint corrections, then passes them here as JSON).
     2. Computes the configuration signature in SQL (HASHBYTES SHA2_256).
     3. Generates the SKU (cfg.usp_GenerateSKU).
     4. Detects reuse and persists via cfg.usp_GetOrCreateConfiguredProduct
        (single store: cfg.ConfiguredProduct).
   The Python endpoint keeps the SAME assembly as a PARITY ORACLE only.

   Part Number formats:
     Horizontal: F{series}{size}{material}{trim}-{pumpOpts}-{sealMfg}{sealAssy}-{options}-{frame}{motorAssy}-{motorMods}-{testing}
     Vertical  : F{series}{size}{material}{trim}-{pumpOpts}-{options}-{frame}{motorAssy}-{motorMods}-{testing}   (no seal segment)

   @SegmentsJson keys (all pre-resolved strings):
     brand, series_code, size_code, material_code, trim_code,
     pump_options, seal_mfg, seal_assy, options, frame_size,
     motor_assy, motor_mods, testing
   @CanonicalJson  : the canonical configuration JSON the signature is taken over
                     (the API sends the exact same bytes it would have hashed, so
                     Python and SQL signatures match).
   ================================================================ */

SET NOCOUNT ON;
SET XACT_ABORT ON;
GO
USE PumpConfiguratorDB;
GO

CREATE OR ALTER PROCEDURE cfg.usp_AssembleConfiguredProduct
    @FamilyCode      varchar(50),
    @SeriesCode      varchar(100),
    @IsVertical      bit,
    @SegmentsJson    nvarchar(max),
    @CanonicalJson   nvarchar(max),
    @RequestedBy     nvarchar(200) = NULL,
    @Persist         bit = 1
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF ISJSON(@SegmentsJson) <> 1
        THROW 53000, 'SegmentsJson must be valid JSON.', 1;
    IF ISJSON(@CanonicalJson) <> 1
        THROW 53001, 'CanonicalJson must be valid JSON.', 1;

    /* --- pull resolved segment codes --- */
    DECLARE
        @brand    varchar(10) = JSON_VALUE(@SegmentsJson, '$.brand'),
        @seriesC  varchar(20) = JSON_VALUE(@SegmentsJson, '$.series_code'),
        @sizeC    varchar(20) = JSON_VALUE(@SegmentsJson, '$.size_code'),
        @matC     varchar(20) = JSON_VALUE(@SegmentsJson, '$.material_code'),
        @trimC    varchar(20) = JSON_VALUE(@SegmentsJson, '$.trim_code'),
        @pumpOpts varchar(20) = JSON_VALUE(@SegmentsJson, '$.pump_options'),
        @sealMfg  varchar(20) = JSON_VALUE(@SegmentsJson, '$.seal_mfg'),
        @sealAssy varchar(20) = JSON_VALUE(@SegmentsJson, '$.seal_assy'),
        @options  varchar(20) = JSON_VALUE(@SegmentsJson, '$.options'),
        @frame    varchar(20) = JSON_VALUE(@SegmentsJson, '$.frame_size'),
        @motorA   varchar(20) = JSON_VALUE(@SegmentsJson, '$.motor_assy'),
        @motorM   varchar(20) = JSON_VALUE(@SegmentsJson, '$.motor_mods'),
        @testing  varchar(20) = JSON_VALUE(@SegmentsJson, '$.testing');

    /* --- assemble the authoritative Part Number --- */
    DECLARE @PartNumber varchar(200);
    DECLARE @lead varchar(60) =
        CONCAT(@brand, @seriesC, @sizeC, @matC, @trimC);

    IF @IsVertical = 1
        SET @PartNumber = CONCAT(
            @lead, '-', @pumpOpts, '-', @options, '-',
            @frame, @motorA, '-', @motorM, '-', @testing);
    ELSE
        SET @PartNumber = CONCAT(
            @lead, '-', @pumpOpts, '-', @sealMfg, @sealAssy, '-',
            @options, '-', @frame, @motorA, '-', @motorM, '-', @testing);

    /* --- signature in SQL (SHA2_256 over the canonical JSON, hex upper) --- */
    DECLARE @Signature char(64) =
        CONVERT(char(64),
            HASHBYTES('SHA2_256', CONVERT(varbinary(max), @CanonicalJson)), 2);

    /* --- SKU (reuse the existing generator) --- */
    DECLARE @SKU varchar(100);
    EXEC cfg.usp_GenerateSKU
        @FamilyCode = @FamilyCode,
        @SeriesCode = @SeriesCode,
        @ConfigurationSignature = @Signature,
        @SKU = @SKU OUTPUT;

    /* --- reuse + persist (single store: cfg.ConfiguredProduct) --- */
    DECLARE @ExistingId bigint = NULL, @Existing bit = 0;

    IF @Persist = 1
    BEGIN
        -- get-or-create returns a result set; capture it into a temp table.
        DECLARE @res TABLE (
            ConfiguredProductId bigint,
            PartNumber varchar(200),
            SKUCode varchar(100),
            ConfigurationSignature char(64),
            ExistingConfiguration bit
        );
        -- Pass @SeriesCode=NULL to the persister: cfg.ConfiguredProduct.PumpSeriesId
        -- is a nullable FK and cfg.PumpSeries is not fully populated for every
        -- Fybroc series. The series is already captured in the canonical JSON,
        -- Part Number, and SKU, so a NULL series link does not lose information
        -- and avoids a spurious "pump series was not found" failure. (If/when
        -- cfg.PumpSeries is fully populated, this can pass @SeriesCode through.)
        INSERT INTO @res
        EXEC cfg.usp_GetOrCreateConfiguredProduct
            @FamilyCode = @FamilyCode,
            @SeriesCode = NULL,
            @ConfigurationJson = @CanonicalJson,
            @ConfigurationSignature = @Signature,
            @PartNumber = @PartNumber,
            @SKUCode = @SKU,
            @RequestedBy = @RequestedBy;

        SELECT TOP 1
            @ExistingId = ConfiguredProductId,
            @Existing = ExistingConfiguration,
            @PartNumber = PartNumber,   -- if reused, return the stored PN/SKU
            @SKU = SKUCode
        FROM @res;
    END
    ELSE
    BEGIN
        SELECT @ExistingId = ConfiguredProductId, @Existing = 1
        FROM cfg.ConfiguredProduct
        WHERE ConfigurationSignature = @Signature;
        SET @Existing = CASE WHEN @ExistingId IS NULL THEN 0 ELSE 1 END;
    END;

    /* --- authoritative result --- */
    SELECT
        @PartNumber           AS PartNumber,
        @SKU                  AS SKU,
        @Signature            AS ConfigurationSignature,
        @Existing             AS ExistingConfiguration,
        @ExistingId           AS ConfiguredProductId;
END;
GO

PRINT 'F150: cfg.usp_AssembleConfiguredProduct created.';
GO

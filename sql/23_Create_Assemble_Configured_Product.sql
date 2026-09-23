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
     FYBROC: brand, series_code, size_code, material_code, trim_code,
       pump_options, seal_mfg, seal_assy, options, frame_size,
       motor_assy, motor_mods, testing
     DEAN (D130, additive branch): base_identifier (=D<A#>), wet_end,
       impeller_trim, impeller_options, power_frame_options,
       flush_plan, barrier_plan, cooling_plan, frame_size, baseplate_options,
       motor, motor_options, additional_options, testing, documentation
       (seal is OMITTED from the Dean PN - external seal DB authority only;
        seal_options may still be passed but is ignored here.)
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

    DECLARE @PartNumber varchar(200);

    IF UPPER(@FamilyCode) = 'DEAN'
    BEGIN
        /* ============================================================
           D130 - DEAN identifier assembly (ADDITIVE branch).
           The Fybroc path below is byte-for-byte unchanged. The API
           resolves each Dean segment code (A#->D#, wet-end, trim, etc.)
           against the loaded numbering maps and passes them here; SQL
           concatenates the authoritative Dean Part Number per the
           workbook Smart Number!B5 + J5 formulas:

             D<A#>-<WetEnd(4)>-<Trim(2)><ImpOpts(2)>-<PowerEnd(3)>
               -<Seal(5)>-<Flush(2)><Barrier><Cooling(2)>
               -<Frame(2)><Baseplate(3)>-<Motor(4)><MotorOpts(2)>
               -<AddlOpts(2)>-<Testing(2)><Doc(4)>

           (B5 assembles through AddlOpts; J5 appends Testing+Doc as the
           final suffix - the full stored Part Number is B5 + J5 content.)
           ============================================================ */
        DECLARE
            @d_base   varchar(20) = JSON_VALUE(@SegmentsJson, '$.base_identifier'), -- D<A#>
            @d_wet    varchar(20) = JSON_VALUE(@SegmentsJson, '$.wet_end'),
            @d_trim   varchar(20) = JSON_VALUE(@SegmentsJson, '$.impeller_trim'),
            @d_impopt varchar(20) = JSON_VALUE(@SegmentsJson, '$.impeller_options'),
            @d_power  varchar(20) = JSON_VALUE(@SegmentsJson, '$.power_frame_options'),
            @d_flush  varchar(20) = JSON_VALUE(@SegmentsJson, '$.flush_plan'),
            @d_barr   varchar(20) = JSON_VALUE(@SegmentsJson, '$.barrier_plan'),
            @d_cool   varchar(20) = JSON_VALUE(@SegmentsJson, '$.cooling_plan'),
            @d_frame  varchar(20) = JSON_VALUE(@SegmentsJson, '$.frame_size'),
            @d_basep  varchar(20) = JSON_VALUE(@SegmentsJson, '$.baseplate_options'),
            @d_motor  varchar(20) = JSON_VALUE(@SegmentsJson, '$.motor'),
            @d_motopt varchar(20) = JSON_VALUE(@SegmentsJson, '$.motor_options'),
            @d_addl   varchar(20) = JSON_VALUE(@SegmentsJson, '$.additional_options'),
            @d_test   varchar(20) = JSON_VALUE(@SegmentsJson, '$.testing'),
            @d_doc    varchar(20) = JSON_VALUE(@SegmentsJson, '$.documentation');

        -- Seal segment (@d_seal) is OMITTED from the Dean PN: the seal code is
        -- authored only in the external "Seal Numbering.accdb" (getSealOptions),
        -- which is not available, so the workbook itself only ever emits the
        -- placeholder 00000/TBD__. Rather than embed a placeholder in the PN, the
        -- Dean PN excludes seal. Seal STATUS is still surfaced in the API
        -- segment_debug. (D130 decision, 2026-08-26.)
        SET @PartNumber = CONCAT(
            @d_base,
            '-', @d_wet,
            '-', @d_trim, @d_impopt,
            '-', @d_power,
            '-', @d_flush, @d_barr, @d_cool,
            '-', @d_frame, @d_basep,
            '-', @d_motor, @d_motopt,
            '-', @d_addl,
            '-', @d_test, @d_doc);
    END
    ELSE
    BEGIN
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
    END

    /* --- signature in SQL (SHA2_256 over the canonical JSON, hex upper) --- */
    DECLARE @Signature char(64) =
        CONVERT(char(64),
            HASHBYTES('SHA2_256', CONVERT(varbinary(max), @CanonicalJson)), 2);

    /* --- SKU (PN-DERIVED: SKU <-> PN is 1:1) --- */
    DECLARE @SKU varchar(100);
    EXEC cfg.usp_GenerateSKU
        @FamilyCode = @FamilyCode,
        @SeriesCode = @SeriesCode,
        @PartNumber = @PartNumber,
        @SKU = @SKU OUTPUT,
        @ConfigurationSignature = @Signature;

    /* --- reuse + persist (single store: cfg.ConfiguredProduct) ---
       IDENTITY RULE: reuse is keyed on the PART NUMBER. The Part Number is the
       product identity; the SKU is 1:1 with it. So if this PN already exists we
       return that row (existing=True) with its stored PN/SKU/signature, and we
       NEVER attempt a second insert for the same PN (which would violate
       UNIQUE(PartNumber)). Two configurations that resolve to the same PN are,
       by definition of the Part Number, the same configured product. */
    DECLARE @ExistingId bigint = NULL, @Existing bit = 0;

    -- PN-based reuse: does this Part Number already exist?
    DECLARE @StoredSig char(64) = NULL;
    SELECT @ExistingId = ConfiguredProductId,
           @SKU        = SKUCode,       -- return the PN's canonical SKU
           @StoredSig  = ConfigurationSignature
    FROM cfg.ConfiguredProduct
    WHERE PumpFamilyId = (SELECT PumpFamilyId FROM cfg.PumpFamily
                          WHERE FamilyCode = @FamilyCode AND IsActive = 1)
      AND PartNumber = @PartNumber;

    IF @ExistingId IS NOT NULL
    BEGIN
        -- Reuse the stored product. Report its stored signature (the signature
        -- is a detail/audit field; the PN is the identity).
        SET @Existing = 1;
        SET @Signature = @StoredSig;
    END
    ELSE IF @Persist = 1
    BEGIN
        -- New Part Number: create it. get-or-create keys on signature but since
        -- the PN is new (checked above), this is an insert. Pass @SeriesCode=NULL
        -- (cfg.ConfiguredProduct.PumpSeriesId is a nullable FK and cfg.PumpSeries
        -- is not fully populated for every Fybroc series; the series is already
        -- captured in the canonical JSON, Part Number, and SKU).
        DECLARE @res TABLE (
            ConfiguredProductId bigint,
            PartNumber varchar(200),
            SKUCode varchar(100),
            ConfigurationSignature char(64),
            ExistingConfiguration bit
        );
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
            @PartNumber = PartNumber,
            @SKU = SKUCode
        FROM @res;
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

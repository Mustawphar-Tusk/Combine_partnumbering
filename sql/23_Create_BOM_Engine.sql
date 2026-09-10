/* ================================================================
   U130 - REUSABLE BOM ENGINE
   ----------------------------------------------------------------
   BOM (Bill of Materials) links to configured products.
   Repeated identical configurations reuse the same BOM.
   
   Tables:
     cfg.BOMHeader - one per configured product (linked by signature)
     cfg.BOMLine - individual line items within a BOM
   
   Key principle: SKU -> ConfiguredProduct -> BOM
   ================================================================ */

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

USE PumpConfiguratorDB;
GO

/* ================================================================
   1. BOM HEADER
   ================================================================ */

IF OBJECT_ID('cfg.BOMHeader', 'U') IS NULL
BEGIN
    CREATE TABLE cfg.BOMHeader
    (
        BOMHeaderId bigint IDENTITY(1,1) PRIMARY KEY,
        ConfiguredProductId bigint NOT NULL,
        BOMVersion int NOT NULL DEFAULT 1,
        Status varchar(20) NOT NULL DEFAULT 'Draft',
        CreatedAt datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
        CreatedBy nvarchar(200) NULL,
        ApprovedAt datetime2(0) NULL,
        ApprovedBy nvarchar(200) NULL,

        CONSTRAINT FK_BOMHeader_ConfiguredProduct
            FOREIGN KEY (ConfiguredProductId)
            REFERENCES cfg.ConfiguredProduct(ConfiguredProductId),

        CONSTRAINT CK_BOMHeader_Status
            CHECK (Status IN ('Draft', 'Active', 'Superseded', 'Retired')),

        CONSTRAINT UQ_BOMHeader_Product_Version
            UNIQUE (ConfiguredProductId, BOMVersion)
    );
END;
GO

/* --- U130 identity: the canonical BOM signature (physical-build identity).
   Computed over the STRUCTURAL BOM lines only (component code + attributes + qty
   + uom), EXCLUDING price. Same configuration -> same BOM signature -> same
   configured product -> same PN -> same SKU. Added idempotently so existing
   deployments pick it up. --- */
IF COL_LENGTH('cfg.BOMHeader', 'BOMSignature') IS NULL
BEGIN
    ALTER TABLE cfg.BOMHeader ADD BOMSignature char(64) NULL;
END;
GO
-- One Active BOM per configured product (the current, generated BOM).
-- Filtered index requires QUOTED_IDENTIFIER/ANSI_NULLS ON at create time.
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UX_BOMHeader_Product_Active')
BEGIN
    CREATE UNIQUE INDEX UX_BOMHeader_Product_Active
        ON cfg.BOMHeader(ConfiguredProductId) WHERE Status = 'Active';
END;
GO

/* ================================================================
   2. BOM LINE ITEMS
   ================================================================ */

IF OBJECT_ID('cfg.BOMLine', 'U') IS NULL
BEGIN
    CREATE TABLE cfg.BOMLine
    (
        BOMLineId bigint IDENTITY(1,1) PRIMARY KEY,
        BOMHeaderId bigint NOT NULL,
        LineNumber int NOT NULL,
        ComponentCode varchar(100) NOT NULL,
        ComponentDescription nvarchar(500) NOT NULL,
        PartNumber varchar(200) NULL,
        Quantity decimal(10,3) NOT NULL DEFAULT 1,
        UnitOfMeasure varchar(20) NOT NULL DEFAULT 'EA',
        UnitCost decimal(19,4) NULL,
        ExtendedCost decimal(19,4) NULL,
        SourceWorkbook nvarchar(300) NULL,
        SourceReference nvarchar(200) NULL,
        IsActive bit NOT NULL DEFAULT 1,

        CONSTRAINT FK_BOMLine_BOMHeader
            FOREIGN KEY (BOMHeaderId)
            REFERENCES cfg.BOMHeader(BOMHeaderId),

        CONSTRAINT UQ_BOMLine_Header_Line
            UNIQUE (BOMHeaderId, LineNumber)
    );
END;
GO

/* ================================================================
   3. BOM REUSE PROCEDURE
   ================================================================ */

CREATE OR ALTER PROCEDURE cfg.usp_GetOrCreateBOM
    @ConfiguredProductId bigint,
    @CreatedBy nvarchar(200) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @BOMHeaderId bigint;

    -- Check for existing active BOM
    SELECT @BOMHeaderId = BOMHeaderId
    FROM cfg.BOMHeader
    WHERE ConfiguredProductId = @ConfiguredProductId
      AND Status = 'Active';

    IF @BOMHeaderId IS NOT NULL
    BEGIN
        -- Reuse existing BOM
        SELECT BOMHeaderId, ConfiguredProductId, BOMVersion, Status, 
               CAST(1 AS bit) AS ExistingBOM
        FROM cfg.BOMHeader
        WHERE BOMHeaderId = @BOMHeaderId;
        RETURN;
    END;

    -- Create new BOM
    INSERT INTO cfg.BOMHeader (ConfiguredProductId, BOMVersion, Status, CreatedBy)
    VALUES (@ConfiguredProductId, 1, 'Draft', @CreatedBy);

    SET @BOMHeaderId = SCOPE_IDENTITY();

    SELECT BOMHeaderId, ConfiguredProductId, BOMVersion, Status,
           CAST(0 AS bit) AS ExistingBOM
    FROM cfg.BOMHeader
    WHERE BOMHeaderId = @BOMHeaderId;
END;
GO

/* ================================================================
   3b. GENERATE BOM (Option 1 - grounded, deterministic from configuration)
   ----------------------------------------------------------------
   Builds the BOM lines for a configured product from:
     - STRUCTURAL lines derived from the resolved PN segments (identity-bearing)
     - PRICED lines (BASE_PUMP, SEAL) with real UnitCost + lineage, supplied by
       the caller in @PricedJson (the resolve endpoint already looks these up).
   Computes the canonical BOM signature over the STRUCTURAL lines only (component
   code + attributes + qty + uom, price EXCLUDED) and persists an Active BOM.
   Idempotent: if the configured product already has an Active BOM with the same
   signature, it is reused (no duplicate insert).

   @SegmentsJson keys (resolved segment codes): series_code, size_code,
     material_code, trim_code, pump_options, seal_mfg, seal_assy, options,
     frame_size, motor_assy, motor_mods, testing
   @PricedJson (optional): JSON array of {component_code, description, unit_cost,
     source_reference} priced lines to merge onto matching structural lines.
   ================================================================ */
CREATE OR ALTER PROCEDURE cfg.usp_GenerateBOM
    @ConfiguredProductId bigint,
    @IsVertical bit,
    @SegmentsJson nvarchar(max),
    @PricedJson nvarchar(max) = NULL,
    @CreatedBy nvarchar(200) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF ISJSON(@SegmentsJson) <> 1
        THROW 52210, 'SegmentsJson must be valid JSON.', 1;
    IF @PricedJson IS NOT NULL AND ISJSON(@PricedJson) <> 1
        THROW 52211, 'PricedJson must be valid JSON when supplied.', 1;

    DECLARE
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

    -- Build the STRUCTURAL lines (deterministic, identity-bearing).
    -- LineNumber fixes display order; the signature ignores it.
    DECLARE @lines TABLE (
        LineNumber int,
        ComponentCode varchar(100),
        Attributes varchar(200),
        ComponentDescription nvarchar(500),
        Quantity decimal(10,3),
        UnitOfMeasure varchar(20)
    );

    INSERT INTO @lines (LineNumber, ComponentCode, Attributes, ComponentDescription, Quantity, UnitOfMeasure)
    VALUES
        (10, 'PUMP_ASSEMBLY', CONCAT(@seriesC, @sizeC, @matC, @trimC),
             CONCAT('Pump assembly ', @seriesC, @sizeC, @matC, @trimC), 1, 'EA'),
        (20, 'PUMP_OPTIONS',  @pumpOpts, CONCAT('Pump options ', @pumpOpts), 1, 'EA');

    -- Seal assembly only for horizontal (vertical omits the seal segment).
    IF @IsVertical = 0
        INSERT INTO @lines VALUES
        (30, 'SEAL_ASSEMBLY', CONCAT(@sealMfg, @sealAssy),
             CONCAT('Seal assembly ', @sealMfg, @sealAssy), 1, 'EA');

    INSERT INTO @lines VALUES
        (40, 'OPTIONS',        @options, CONCAT('Options ', @options), 1, 'EA'),
        (50, 'MOTOR_ASSEMBLY', CONCAT(@frame, @motorA), CONCAT('Motor assembly ', @frame, @motorA), 1, 'EA'),
        (60, 'MOTOR_MODS',     @motorM,  CONCAT('Motor modifications ', @motorM), 1, 'EA'),
        (70, 'TESTING',        @testing, CONCAT('Testing ', @testing), 1, 'EA');

    -- Canonical BOM signature over STRUCTURAL lines only (price excluded).
    -- line_key = lower('code|attributes|qty|uom'); body = sorted keys joined by \n.
    DECLARE @body nvarchar(max);
    SELECT @body = STRING_AGG(
        CONVERT(nvarchar(max),
            LOWER(CONCAT(ComponentCode, '|', ISNULL(Attributes,''), '|',
                         CONVERT(varchar(20), Quantity), '|', UnitOfMeasure))),
        NCHAR(10)) WITHIN GROUP (ORDER BY
            LOWER(CONCAT(ComponentCode, '|', ISNULL(Attributes,''), '|',
                         CONVERT(varchar(20), Quantity), '|', UnitOfMeasure)))
    FROM @lines;

    -- Hash over varchar (single-byte) bytes so the digest matches the Python
    -- parity oracle's UTF-8 hash. BOM tokens are ASCII, so varchar is lossless
    -- here; nvarchar (UTF-16LE) would produce a different digest. (Same
    -- convention as the PN-derived SKU hash.)
    DECLARE @BOMSignature char(64) =
        CONVERT(char(64), HASHBYTES('SHA2_256', CONVERT(varbinary(max), CONVERT(varchar(max), @body))), 2);

    -- Idempotent reuse: existing Active BOM with the same signature for this product?
    DECLARE @BOMHeaderId bigint, @Existing bit = 0;
    SELECT @BOMHeaderId = BOMHeaderId
    FROM cfg.BOMHeader
    WHERE ConfiguredProductId = @ConfiguredProductId
      AND Status = 'Active' AND BOMSignature = @BOMSignature;

    IF @BOMHeaderId IS NOT NULL
    BEGIN
        SET @Existing = 1;
    END
    ELSE
    BEGIN
        BEGIN TRANSACTION;
        -- Retire any prior Active BOM for this product (config/BOM changed).
        UPDATE cfg.BOMHeader SET Status = 'Superseded'
        WHERE ConfiguredProductId = @ConfiguredProductId AND Status = 'Active';

        INSERT INTO cfg.BOMHeader (ConfiguredProductId, BOMVersion, Status, BOMSignature, CreatedBy)
        VALUES (@ConfiguredProductId,
                ISNULL((SELECT MAX(BOMVersion) FROM cfg.BOMHeader
                        WHERE ConfiguredProductId = @ConfiguredProductId), 0) + 1,
                'Active', @BOMSignature, @CreatedBy);
        SET @BOMHeaderId = SCOPE_IDENTITY();

        -- Insert structural lines, merging priced UnitCost/lineage where the
        -- component code matches (BASE_PUMP -> PUMP_ASSEMBLY, SEAL -> SEAL_ASSEMBLY).
        INSERT INTO cfg.BOMLine
            (BOMHeaderId, LineNumber, ComponentCode, ComponentDescription,
             Quantity, UnitOfMeasure, UnitCost, ExtendedCost, SourceReference, IsActive)
        SELECT
            @BOMHeaderId, l.LineNumber, l.ComponentCode, l.ComponentDescription,
            l.Quantity, l.UnitOfMeasure,
            p.unit_cost,
            CASE WHEN p.unit_cost IS NULL THEN NULL ELSE p.unit_cost * l.Quantity END,
            p.source_reference, 1
        FROM @lines l
        OUTER APPLY (
            SELECT TOP 1 j.unit_cost, j.source_reference
            FROM OPENJSON(ISNULL(@PricedJson, '[]'))
                WITH (component_code varchar(100) '$.component_code',
                      unit_cost decimal(19,4) '$.unit_cost',
                      source_reference nvarchar(200) '$.source_reference') j
            WHERE j.component_code =
                  CASE l.ComponentCode
                       WHEN 'PUMP_ASSEMBLY' THEN 'BASE_PUMP'
                       WHEN 'SEAL_ASSEMBLY' THEN 'SEAL'
                       ELSE l.ComponentCode END
        ) p;

        COMMIT;
    END;

    SELECT @BOMHeaderId AS BOMHeaderId,
           @BOMSignature AS BOMSignature,
           @Existing AS ExistingBOM,
           (SELECT COUNT(*) FROM cfg.BOMLine WHERE BOMHeaderId = @BOMHeaderId AND IsActive = 1) AS LineCount;
END;
GO

/* ================================================================
   4. LOOKUP BOM BY SKU
   ================================================================ */

CREATE OR ALTER PROCEDURE cfg.usp_GetBOMBySKU
    @SKU varchar(100)
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        bh.BOMHeaderId,
        bh.BOMVersion,
        bh.Status AS BOMStatus,
        cp.SKUCode AS SKU,
        cp.PartNumber,
        cp.ConfigurationSignature,
        bl.LineNumber,
        bl.ComponentCode,
        bl.ComponentDescription,
        bl.PartNumber AS ComponentPartNumber,
        bl.Quantity,
        bl.UnitOfMeasure,
        bl.UnitCost,
        bl.ExtendedCost
    FROM cfg.ConfiguredProduct cp
    INNER JOIN cfg.BOMHeader bh 
        ON bh.ConfiguredProductId = cp.ConfiguredProductId
        AND bh.Status = 'Active'
    LEFT JOIN cfg.BOMLine bl
        ON bl.BOMHeaderId = bh.BOMHeaderId
        AND bl.IsActive = 1
    WHERE cp.SKUCode = @SKU
    ORDER BY bl.LineNumber;

    IF @@ROWCOUNT = 0
        THROW 52200, 'No active BOM found for this SKU.', 1;
END;
GO

PRINT 'U130: BOM Engine tables and procedures created.';
GO

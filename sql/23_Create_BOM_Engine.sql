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

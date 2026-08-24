/* ================================================================
   U140 - QUOTE ENGINE
   ----------------------------------------------------------------
   QuoteHeader + QuoteLine linked to configured products.
   Each QuoteLine references a configured product (via SKU/PN).
   ================================================================ */

SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

USE PumpConfiguratorDB;
GO

IF OBJECT_ID('quote.QuoteHeader', 'U') IS NULL
BEGIN
    CREATE TABLE quote.QuoteHeader
    (
        QuoteHeaderId bigint IDENTITY(1,1) PRIMARY KEY,
        QuoteNumber varchar(50) NOT NULL,
        CustomerName nvarchar(300) NULL,
        CustomerAccount nvarchar(100) NULL,
        SiteCode varchar(10) NOT NULL,
        Status varchar(20) NOT NULL DEFAULT 'Draft',
        CreatedAt datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
        CreatedBy nvarchar(200) NULL,
        ExpiresAt datetime2(0) NULL,
        Notes nvarchar(max) NULL,

        CONSTRAINT UQ_QuoteHeader_Number UNIQUE (QuoteNumber),
        CONSTRAINT CK_QuoteHeader_Status
            CHECK (Status IN ('Draft', 'Submitted', 'Approved', 'Expired', 'Cancelled')),
        CONSTRAINT CK_QuoteHeader_Site
            CHECK (SiteCode IN ('TEL', 'IND'))
    );
END;
GO

IF OBJECT_ID('quote.QuoteLine', 'U') IS NULL
BEGIN
    CREATE TABLE quote.QuoteLine
    (
        QuoteLineId bigint IDENTITY(1,1) PRIMARY KEY,
        QuoteHeaderId bigint NOT NULL,
        LineNumber int NOT NULL,
        ConfiguredProductId bigint NULL,
        FamilyCode varchar(50) NOT NULL,
        SiteCode varchar(10) NOT NULL,
        PartNumber varchar(200) NOT NULL,
        SKU varchar(100) NOT NULL,
        ConfigurationJson nvarchar(max) NULL,
        Quantity int NOT NULL DEFAULT 1,
        UnitPrice decimal(19,4) NOT NULL,
        ExtendedPrice decimal(19,4) NOT NULL,
        PricingLineage nvarchar(max) NULL,
        PublicationVersion varchar(50) NULL,
        CreatedAt datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME(),

        CONSTRAINT FK_QuoteLine_Header
            FOREIGN KEY (QuoteHeaderId)
            REFERENCES quote.QuoteHeader(QuoteHeaderId),
        CONSTRAINT FK_QuoteLine_ConfiguredProduct
            FOREIGN KEY (ConfiguredProductId)
            REFERENCES cfg.ConfiguredProduct(ConfiguredProductId),
        CONSTRAINT UQ_QuoteLine_Header_Line
            UNIQUE (QuoteHeaderId, LineNumber),
        CONSTRAINT CK_QuoteLine_Site
            CHECK (SiteCode IN ('TEL', 'IND'))
    );
END;
GO

/* ================================================================
   CREATE QUOTE PROCEDURE
   ================================================================ */

CREATE OR ALTER PROCEDURE quote.usp_CreateQuote
    @QuoteNumber varchar(50),
    @CustomerName nvarchar(300) = NULL,
    @SiteCode varchar(10),
    @CreatedBy nvarchar(200) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO quote.QuoteHeader (QuoteNumber, CustomerName, SiteCode, CreatedBy)
    VALUES (@QuoteNumber, @CustomerName, @SiteCode, @CreatedBy);

    SELECT QuoteHeaderId, QuoteNumber, Status, SiteCode, CreatedAt
    FROM quote.QuoteHeader
    WHERE QuoteHeaderId = SCOPE_IDENTITY();
END;
GO

CREATE OR ALTER PROCEDURE quote.usp_AddQuoteLine
    @QuoteHeaderId bigint,
    @SKU varchar(100),
    @Quantity int = 1,
    @UnitPrice decimal(19,4),
    @PricingLineage nvarchar(max) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @ConfiguredProductId bigint,
            @PartNumber varchar(200),
            @FamilyCode varchar(50),
            @SiteCode varchar(10),
            @ConfigJson nvarchar(max),
            @LineNumber int;

    -- Resolve SKU to configured product
    SELECT @ConfiguredProductId = cp.ConfiguredProductId,
           @PartNumber = cp.PartNumber,
           @FamilyCode = pf.FamilyCode,
           @ConfigJson = cp.CanonicalConfiguration
    FROM cfg.ConfiguredProduct cp
    INNER JOIN cfg.PumpFamily pf ON pf.PumpFamilyId = cp.PumpFamilyId
    WHERE cp.SKUCode = @SKU;

    IF @ConfiguredProductId IS NULL
        THROW 52300, 'SKU not found in configured product registry.', 1;

    -- Get site from quote header
    SELECT @SiteCode = SiteCode FROM quote.QuoteHeader WHERE QuoteHeaderId = @QuoteHeaderId;
    IF @SiteCode IS NULL
        THROW 52301, 'Quote not found.', 1;

    -- Next line number
    SELECT @LineNumber = ISNULL(MAX(LineNumber), 0) + 1
    FROM quote.QuoteLine WHERE QuoteHeaderId = @QuoteHeaderId;

    INSERT INTO quote.QuoteLine
    (QuoteHeaderId, LineNumber, ConfiguredProductId, FamilyCode, SiteCode,
     PartNumber, SKU, ConfigurationJson, Quantity, UnitPrice, ExtendedPrice, PricingLineage)
    VALUES
    (@QuoteHeaderId, @LineNumber, @ConfiguredProductId, @FamilyCode, @SiteCode,
     @PartNumber, @SKU, @ConfigJson, @Quantity, @UnitPrice, @Quantity * @UnitPrice, @PricingLineage);

    SELECT QuoteLineId, LineNumber, PartNumber, SKU, Quantity, UnitPrice, ExtendedPrice
    FROM quote.QuoteLine WHERE QuoteLineId = SCOPE_IDENTITY();
END;
GO

PRINT 'U140: Quote Engine tables and procedures created.';
GO

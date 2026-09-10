/* ================================================================
   U140 - QUOTE ENGINE  (single canonical quote schema)
   ----------------------------------------------------------------
   A quote is a header + lines. Each line is anchored to a configured
   product (cfg.ConfiguredProduct) AND its Active BOM (cfg.BOMHeader),
   and persists everything needed to REPRODUCE the quote:
     configured product, family, site, Part Number, SKU,
     ConfigurationJson, BOM (id + signature), quantity, unit price,
     extended price, pricing lineage, publication lineage.

   Identity spine (established F150/U130): configuration -> BOM -> PN -> SKU.
   A quote line references the configured product by id and carries its
   BOM signature so the line is reproducible even if catalog data changes.

   This file is AUTHORITATIVE for quote.QuoteHeader / quote.QuoteLine.
   (sql/02 previously also defined them with an incompatible shape; that
   duplicate was removed. quote.QuoteTemplate/QuoteTemplateMapping remain
   in sql/02 as the future Excel render target.)

   Pricing honesty: unit price is the sum of the components we can price
   today (BASE_PUMP + SEAL). PricingStatus records whether the line is
   fully priced ('found'), partially priced ('partial'), or needs a quote
   ('call_for_price'). Full component pricing (coupling/baseplate/motor/
   adders) is a later extraction milestone.
   ================================================================ */

SET NOCOUNT ON;
SET XACT_ABORT ON;
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

USE PumpConfiguratorDB;
GO

/* --- Clean rebuild to the canonical shape. Both tables are transient
   (no customer data yet); drop lines first (FK), then header. --- */
IF OBJECT_ID('quote.QuoteLine', 'U') IS NOT NULL DROP TABLE quote.QuoteLine;
GO
IF OBJECT_ID('quote.QuoteHeader', 'U') IS NOT NULL DROP TABLE quote.QuoteHeader;
GO

CREATE TABLE quote.QuoteHeader
(
    QuoteHeaderId bigint IDENTITY(1,1) PRIMARY KEY,
    QuoteNumber   varchar(50) NOT NULL,
    CustomerName  nvarchar(300) NULL,
    CustomerAccount nvarchar(100) NULL,
    SiteCode      varchar(10) NOT NULL,
    CurrencyCode  char(3) NOT NULL DEFAULT 'USD',
    Status        varchar(20) NOT NULL DEFAULT 'Draft',
    CreatedAt     datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
    CreatedBy     nvarchar(200) NULL,
    ExpiresAt     datetime2(0) NULL,
    Notes         nvarchar(max) NULL,

    CONSTRAINT UQ_QuoteHeader_Number UNIQUE (QuoteNumber),
    CONSTRAINT CK_QuoteHeader_Status
        CHECK (Status IN ('Draft','Submitted','Approved','Expired','Cancelled')),
    CONSTRAINT CK_QuoteHeader_Site CHECK (SiteCode IN ('TEL','IND'))
);
GO

CREATE TABLE quote.QuoteLine
(
    QuoteLineId   bigint IDENTITY(1,1) PRIMARY KEY,
    QuoteHeaderId bigint NOT NULL,
    LineNumber    int NOT NULL,

    -- configured product (identity spine)
    ConfiguredProductId bigint NOT NULL,
    FamilyCode    varchar(50) NOT NULL,
    SiteCode      varchar(10) NOT NULL,
    PartNumber    varchar(200) NOT NULL,
    SKU           varchar(100) NOT NULL,
    ConfigurationJson nvarchar(max) NULL,

    -- BOM link (physical build of the line)
    BOMHeaderId   bigint NULL,
    BOMSignature  char(64) NULL,

    -- commercials
    Quantity      int NOT NULL DEFAULT 1,
    UnitPrice     decimal(19,4) NOT NULL DEFAULT 0,
    ExtendedPrice decimal(19,4) NOT NULL DEFAULT 0,

    -- lineage (reproducibility)
    PricingStatus     varchar(30) NOT NULL DEFAULT 'not_found',
    PricingLineage    nvarchar(max) NULL,   -- JSON: priced components + amounts
    PublicationVersion varchar(50) NULL,    -- config/metadata publication id
    PriceBookVersion  varchar(50) NULL,     -- price book version code
    CreatedAt     datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME(),

    CONSTRAINT FK_QuoteLine_Header
        FOREIGN KEY (QuoteHeaderId) REFERENCES quote.QuoteHeader(QuoteHeaderId),
    CONSTRAINT FK_QuoteLine_ConfiguredProduct
        FOREIGN KEY (ConfiguredProductId) REFERENCES cfg.ConfiguredProduct(ConfiguredProductId),
    CONSTRAINT FK_QuoteLine_BOMHeader
        FOREIGN KEY (BOMHeaderId) REFERENCES cfg.BOMHeader(BOMHeaderId),
    CONSTRAINT UQ_QuoteLine_Header_Line UNIQUE (QuoteHeaderId, LineNumber),
    CONSTRAINT CK_QuoteLine_Site CHECK (SiteCode IN ('TEL','IND')),
    CONSTRAINT CK_QuoteLine_PricingStatus
        CHECK (PricingStatus IN ('found','partial','call_for_price','not_found'))
);
GO

/* ================================================================
   CREATE QUOTE
   ================================================================ */
CREATE OR ALTER PROCEDURE quote.usp_CreateQuote
    @SiteCode     varchar(10),
    @CustomerName nvarchar(300) = NULL,
    @CustomerAccount nvarchar(100) = NULL,
    @CurrencyCode char(3) = 'USD',
    @CreatedBy    nvarchar(200) = NULL,
    @QuoteNumber  varchar(50) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    -- Auto quote number 'Q-000001' if not supplied (based on next identity).
    DECLARE @next bigint = ISNULL((SELECT MAX(QuoteHeaderId) FROM quote.QuoteHeader), 0) + 1;
    IF @QuoteNumber IS NULL
        SET @QuoteNumber = 'Q-' + RIGHT('000000' + CONVERT(varchar(20), @next), 6);

    INSERT INTO quote.QuoteHeader (QuoteNumber, CustomerName, CustomerAccount, SiteCode, CurrencyCode, CreatedBy)
    VALUES (@QuoteNumber, @CustomerName, @CustomerAccount, @SiteCode, @CurrencyCode, @CreatedBy);

    SELECT QuoteHeaderId, QuoteNumber, SiteCode, CurrencyCode, Status, CreatedAt
    FROM quote.QuoteHeader WHERE QuoteHeaderId = SCOPE_IDENTITY();
END;
GO

/* ================================================================
   ADD QUOTE LINE  (consumes the resolve output)
   ----------------------------------------------------------------
   Anchors the line to a configured product (by id, or by SKU) and its
   Active BOM, and persists commercials + pricing/publication lineage.
   UnitPrice is supplied by the caller (the resolve endpoint's base+seal
   total); the proc does not invent pricing.
   ================================================================ */
CREATE OR ALTER PROCEDURE quote.usp_AddQuoteLine
    @QuoteHeaderId bigint,
    @ConfiguredProductId bigint = NULL,
    @SKU varchar(100) = NULL,
    @Quantity int = 1,
    @UnitPrice decimal(19,4) = 0,
    @PricingStatus varchar(30) = 'not_found',
    @PricingLineage nvarchar(max) = NULL,
    @PublicationVersion varchar(50) = NULL,
    @PriceBookVersion varchar(50) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @PartNumber varchar(200), @SKUCode varchar(100), @FamilyCode varchar(50),
            @ConfigJson nvarchar(max), @SiteCode varchar(10), @BOMHeaderId bigint,
            @BOMSignature char(64), @LineNumber int;

    SELECT @SiteCode = SiteCode FROM quote.QuoteHeader WHERE QuoteHeaderId = @QuoteHeaderId;
    IF @SiteCode IS NULL THROW 52301, 'Quote not found.', 1;

    -- Resolve the configured product (by id preferred, else by SKU).
    SELECT @ConfiguredProductId = cp.ConfiguredProductId,
           @PartNumber = cp.PartNumber, @SKUCode = cp.SKUCode,
           @FamilyCode = pf.FamilyCode, @ConfigJson = cp.CanonicalConfiguration
    FROM cfg.ConfiguredProduct cp
    JOIN cfg.PumpFamily pf ON pf.PumpFamilyId = cp.PumpFamilyId
    WHERE (@ConfiguredProductId IS NOT NULL AND cp.ConfiguredProductId = @ConfiguredProductId)
       OR (@ConfiguredProductId IS NULL AND cp.SKUCode = @SKU);

    IF @ConfiguredProductId IS NULL
        THROW 52300, 'Configured product not found (by id or SKU).', 1;

    -- Link the product's current Active BOM (physical build of the line).
    SELECT @BOMHeaderId = BOMHeaderId, @BOMSignature = BOMSignature
    FROM cfg.BOMHeader
    WHERE ConfiguredProductId = @ConfiguredProductId AND Status = 'Active';

    SELECT @LineNumber = ISNULL(MAX(LineNumber), 0) + 1
    FROM quote.QuoteLine WHERE QuoteHeaderId = @QuoteHeaderId;

    INSERT INTO quote.QuoteLine
        (QuoteHeaderId, LineNumber, ConfiguredProductId, FamilyCode, SiteCode,
         PartNumber, SKU, ConfigurationJson, BOMHeaderId, BOMSignature,
         Quantity, UnitPrice, ExtendedPrice,
         PricingStatus, PricingLineage, PublicationVersion, PriceBookVersion)
    VALUES
        (@QuoteHeaderId, @LineNumber, @ConfiguredProductId, @FamilyCode, @SiteCode,
         @PartNumber, @SKUCode, @ConfigJson, @BOMHeaderId, @BOMSignature,
         @Quantity, @UnitPrice, @Quantity * @UnitPrice,
         @PricingStatus, @PricingLineage, @PublicationVersion, @PriceBookVersion);

    SELECT QuoteLineId, LineNumber, PartNumber, SKU, BOMHeaderId, BOMSignature,
           Quantity, UnitPrice, ExtendedPrice, PricingStatus
    FROM quote.QuoteLine WHERE QuoteLineId = SCOPE_IDENTITY();
END;
GO

/* ================================================================
   GET QUOTE  (header + lines, everything needed to render)
   ----------------------------------------------------------------
   Returns two result sets: (1) the header, (2) the lines (ordered).
   ================================================================ */
CREATE OR ALTER PROCEDURE quote.usp_GetQuote
    @QuoteHeaderId bigint
AS
BEGIN
    SET NOCOUNT ON;

    IF NOT EXISTS (SELECT 1 FROM quote.QuoteHeader WHERE QuoteHeaderId = @QuoteHeaderId)
        THROW 52302, 'Quote not found.', 1;

    SELECT QuoteHeaderId, QuoteNumber, CustomerName, CustomerAccount,
           SiteCode, CurrencyCode, Status, CreatedAt, CreatedBy, ExpiresAt, Notes
    FROM quote.QuoteHeader WHERE QuoteHeaderId = @QuoteHeaderId;

    SELECT QuoteLineId, LineNumber, ConfiguredProductId, FamilyCode, SiteCode,
           PartNumber, SKU, ConfigurationJson, BOMHeaderId, BOMSignature,
           Quantity, UnitPrice, ExtendedPrice,
           PricingStatus, PricingLineage, PublicationVersion, PriceBookVersion, CreatedAt
    FROM quote.QuoteLine
    WHERE QuoteHeaderId = @QuoteHeaderId
    ORDER BY LineNumber;
END;
GO

PRINT 'U140: Quote Engine (canonical schema + procs) created.';
GO

/* ================================================================
   CPQ ADJUSTMENTS A1 - EDITABLE / RESUMABLE DRAFT QUOTE LINES
   ----------------------------------------------------------------
   ADDITIVE ONLY. Two new procs so a distributor can edit a draft
   quote line in place (re-resolve its configuration and write the new
   PN/SKU/BOM/pricing back to the SAME line) and remove a draft line.
   No existing proc/table is altered. Draft-only: a quote whose Status
   is not 'Draft' is immutable here (submitted/approved revisions follow
   the review/revision workflow, never an in-place overwrite).

   Mirrors quote.usp_AddQuoteLine's persistence exactly (same columns,
   same ExtendedPrice = Quantity*UnitPrice). The API re-resolves the
   configuration through the authoritative resolve flow (identity + BOM
   + pricing) and passes the resolved product id + pricing here, so the
   authoritative numbering/pricing services remain the single source.

   Fybroc frozen / Dean untouched: operates only on quote.QuoteLine for
   the given draft quote; reads cfg.ConfiguredProduct / cfg.BOMHeader
   read-only (same as add-line).
   ================================================================ */

SET NOCOUNT ON;
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

USE PumpConfiguratorDB;
GO

/* ---------------------------------------------------------------
   usp_UpdateQuoteLine - re-point an existing DRAFT line to a (re-
   resolved) configured product + refreshed pricing, in place.
   --------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE quote.usp_UpdateQuoteLine
    @QuoteLineId         bigint,
    @ConfiguredProductId bigint = NULL,
    @SKU                 varchar(100) = NULL,
    @Quantity            int = 1,
    @UnitPrice           decimal(19,4) = 0,
    @PricingStatus       varchar(30) = 'not_found',
    @PricingLineage      nvarchar(max) = NULL,
    @PublicationVersion  varchar(50) = NULL,
    @PriceBookVersion    varchar(50) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @QuoteHeaderId bigint, @QuoteStatus varchar(30), @SiteCode varchar(10),
            @PartNumber varchar(200), @SKUCode varchar(100), @FamilyCode varchar(50),
            @ConfigJson nvarchar(max), @BOMHeaderId bigint, @BOMSignature char(64);

    SELECT @QuoteHeaderId = ql.QuoteHeaderId
    FROM quote.QuoteLine ql WHERE ql.QuoteLineId = @QuoteLineId;
    IF @QuoteHeaderId IS NULL THROW 52310, 'Quote line not found.', 1;

    SELECT @QuoteStatus = Status, @SiteCode = SiteCode
    FROM quote.QuoteHeader WHERE QuoteHeaderId = @QuoteHeaderId;
    IF @QuoteStatus <> 'Draft'
        THROW 52311, 'Only draft quote lines can be edited.', 1;

    -- Resolve the (re-resolved) configured product by id preferred, else SKU.
    SELECT @ConfiguredProductId = cp.ConfiguredProductId,
           @PartNumber = cp.PartNumber, @SKUCode = cp.SKUCode,
           @FamilyCode = pf.FamilyCode, @ConfigJson = cp.CanonicalConfiguration
    FROM cfg.ConfiguredProduct cp
    JOIN cfg.PumpFamily pf ON pf.PumpFamilyId = cp.PumpFamilyId
    WHERE (@ConfiguredProductId IS NOT NULL AND cp.ConfiguredProductId = @ConfiguredProductId)
       OR (@ConfiguredProductId IS NULL AND cp.SKUCode = @SKU);
    IF @ConfiguredProductId IS NULL
        THROW 52300, 'Configured product not found (by id or SKU).', 1;

    SELECT @BOMHeaderId = BOMHeaderId, @BOMSignature = BOMSignature
    FROM cfg.BOMHeader
    WHERE ConfiguredProductId = @ConfiguredProductId AND Status = 'Active';

    UPDATE quote.QuoteLine
    SET ConfiguredProductId = @ConfiguredProductId,
        FamilyCode = @FamilyCode,
        PartNumber = @PartNumber,
        SKU = @SKUCode,
        ConfigurationJson = @ConfigJson,
        BOMHeaderId = @BOMHeaderId,
        BOMSignature = @BOMSignature,
        Quantity = @Quantity,
        UnitPrice = @UnitPrice,
        ExtendedPrice = @Quantity * @UnitPrice,
        PricingStatus = @PricingStatus,
        PricingLineage = @PricingLineage,
        PublicationVersion = @PublicationVersion,
        PriceBookVersion = @PriceBookVersion
    WHERE QuoteLineId = @QuoteLineId;

    SELECT QuoteLineId, LineNumber, PartNumber, SKU, BOMHeaderId, BOMSignature,
           Quantity, UnitPrice, ExtendedPrice, PricingStatus
    FROM quote.QuoteLine WHERE QuoteLineId = @QuoteLineId;
END;
GO

/* ---------------------------------------------------------------
   usp_RemoveQuoteLine - delete a DRAFT line and compact LineNumbers.
   --------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE quote.usp_RemoveQuoteLine
    @QuoteLineId bigint
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @QuoteHeaderId bigint, @QuoteStatus varchar(30);
    SELECT @QuoteHeaderId = QuoteHeaderId FROM quote.QuoteLine WHERE QuoteLineId = @QuoteLineId;
    IF @QuoteHeaderId IS NULL THROW 52310, 'Quote line not found.', 1;

    SELECT @QuoteStatus = Status FROM quote.QuoteHeader WHERE QuoteHeaderId = @QuoteHeaderId;
    IF @QuoteStatus <> 'Draft'
        THROW 52311, 'Only draft quote lines can be removed.', 1;

    BEGIN TRAN;
    DELETE FROM quote.QuoteLine WHERE QuoteLineId = @QuoteLineId;

    -- Re-sequence remaining lines 1..N by their existing order.
    ;WITH ordered AS (
        SELECT QuoteLineId,
               ROW_NUMBER() OVER (ORDER BY LineNumber, QuoteLineId) AS rn
        FROM quote.QuoteLine WHERE QuoteHeaderId = @QuoteHeaderId
    )
    UPDATE ql SET ql.LineNumber = o.rn
    FROM quote.QuoteLine ql JOIN ordered o ON o.QuoteLineId = ql.QuoteLineId;
    COMMIT TRAN;

    SELECT @QuoteHeaderId AS QuoteHeaderId,
           (SELECT COUNT(*) FROM quote.QuoteLine WHERE QuoteHeaderId = @QuoteHeaderId) AS RemainingLines;
END;
GO

PRINT 'CPQ A1: quote.usp_UpdateQuoteLine + usp_RemoveQuoteLine created (additive).';
GO

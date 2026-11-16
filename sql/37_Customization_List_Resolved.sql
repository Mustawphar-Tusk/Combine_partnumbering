/* ================================================================
   DEAN REVISION - expose the RESOLVED custom code on customization lists
   ----------------------------------------------------------------
   ADDITIVE ONLY. Re-defines the two A2 list procs (CREATE OR ALTER) to
   APPEND ResolvedCustomCode / ResolvedSpecKey / ResolvedAt as trailing
   columns, so the engineer UI (and later the distributor) can see the
   reusable code the engineer minted for a request. Existing columns and
   their order are unchanged (positional readers keep working).
   ================================================================ */
SET NOCOUNT ON;
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

USE PumpConfiguratorDB;
GO

CREATE OR ALTER PROCEDURE quote.usp_ListQuoteLineCustomizations
    @QuoteLineId BIGINT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT CustomizationId, QuoteLineId, Grouping, FieldCode, CurrentValue,
           RequestedChange, Notes, RevisionNo, CreatedAt,
           ResolvedCustomCode, ResolvedSpecKey, ResolvedAt
    FROM quote.QuoteLineCustomization
    WHERE QuoteLineId = @QuoteLineId
    ORDER BY CustomizationId;
END;
GO

CREATE OR ALTER PROCEDURE quote.usp_ListQuoteCustomizations
    @QuoteHeaderId BIGINT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT c.CustomizationId, c.QuoteLineId, ql.LineNumber, c.Grouping, c.FieldCode,
           c.CurrentValue, c.RequestedChange, c.Notes, c.RevisionNo, c.CreatedAt,
           c.ResolvedCustomCode, c.ResolvedSpecKey, c.ResolvedAt
    FROM quote.QuoteLineCustomization c
    JOIN quote.QuoteLine ql ON ql.QuoteLineId = c.QuoteLineId
    WHERE ql.QuoteHeaderId = @QuoteHeaderId
    ORDER BY ql.LineNumber, c.CustomizationId;
END;
GO

PRINT 'sql/37: customization list procs now return resolved code (additive).';
GO

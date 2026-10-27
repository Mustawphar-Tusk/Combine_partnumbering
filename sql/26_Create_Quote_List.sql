/* ================================================================
   PHASE C (CPQ Quotes UI) - LIST QUOTES
   ----------------------------------------------------------------
   Additive only: a new read-only proc quote.usp_ListQuotes. No table
   changes, no change to existing procs (usp_CreateQuote /
   usp_AddQuoteLine / usp_GetQuote are untouched). Powers the Quotes
   page list in the UI (GET /api/v2/families/{family}/quotes).

   Returns one row per quote header with a LineCount and a TotalPrice
   (sum of line ExtendedPrice), newest first. Pure aggregate over the
   existing quote.QuoteHeader / quote.QuoteLine tables - safe for both
   families; it does not read or alter any Fybroc/Dean config data.
   ================================================================ */

SET NOCOUNT ON;
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

USE PumpConfiguratorDB;
GO

CREATE OR ALTER PROCEDURE quote.usp_ListQuotes
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        h.QuoteHeaderId,
        h.QuoteNumber,
        h.CustomerName,
        h.CustomerAccount,
        h.SiteCode,
        h.CurrencyCode,
        h.Status,
        h.CreatedAt,
        h.CreatedBy,
        ISNULL(l.LineCount, 0)   AS LineCount,
        ISNULL(l.TotalPrice, 0)  AS TotalPrice
    FROM quote.QuoteHeader AS h
    OUTER APPLY (
        SELECT COUNT(*) AS LineCount, SUM(ql.ExtendedPrice) AS TotalPrice
        FROM quote.QuoteLine AS ql
        WHERE ql.QuoteHeaderId = h.QuoteHeaderId
    ) AS l
    ORDER BY h.QuoteHeaderId DESC;
END;
GO

PRINT 'Phase C: quote.usp_ListQuotes created.';
GO

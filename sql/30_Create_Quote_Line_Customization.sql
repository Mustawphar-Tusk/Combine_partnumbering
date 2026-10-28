/* ================================================================
   CPQ ADJUSTMENTS A2 - PER-GROUPING CUSTOMIZATION REQUESTS
   ----------------------------------------------------------------
   ADDITIVE ONLY. New table quote.QuoteLineCustomization: multiple
   customization requests per quote line, each tied to a grouping +
   (optional) field, with the current value, the requested change, and
   notes. Editable/removable while the quote is a Draft; visible on
   reopen and to engineering. No existing object altered.

   Not part of the authoritative PN. These are free-text engineering
   requests the distributor records; A4 (governed custom-code model)
   later resolves affected groupings into mirrored custom codes without
   touching this table's role. Fybroc frozen / Dean untouched (quote
   schema only).
   ================================================================ */

SET NOCOUNT ON;
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

USE PumpConfiguratorDB;
GO

IF OBJECT_ID('quote.QuoteLineCustomization', 'U') IS NULL
BEGIN
    CREATE TABLE quote.QuoteLineCustomization (
        CustomizationId   BIGINT IDENTITY(1,1) NOT NULL
            CONSTRAINT PK_quote_QuoteLineCustomization PRIMARY KEY,
        QuoteLineId       BIGINT NOT NULL,
        Grouping          NVARCHAR(80) NOT NULL,   -- e.g. WET_END, IMPELLER, MOTOR, POWER_FRAME
        FieldCode         NVARCHAR(80) NULL,       -- optional specific field within the grouping
        CurrentValue      NVARCHAR(400) NULL,      -- current selected value, where applicable
        RequestedChange   NVARCHAR(1000) NOT NULL, -- what the distributor wants customized
        Notes             NVARCHAR(1000) NULL,
        RevisionNo        INT NOT NULL
            CONSTRAINT DF_quote_QLC_Rev DEFAULT (1),
        CreatedAt         DATETIME2(3) NOT NULL
            CONSTRAINT DF_quote_QLC_CreatedAt DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT FK_quote_QLC_Line
            FOREIGN KEY (QuoteLineId) REFERENCES quote.QuoteLine (QuoteLineId)
    );
    CREATE INDEX IX_quote_QLC_Line ON quote.QuoteLineCustomization (QuoteLineId);
END
GO

/* --- helper: is the line's quote a Draft? (customizations are draft-editable) */
/* usp_AddQuoteLineCustomization ------------------------------------------- */
CREATE OR ALTER PROCEDURE quote.usp_AddQuoteLineCustomization
    @QuoteLineId     BIGINT,
    @Grouping        NVARCHAR(80),
    @FieldCode       NVARCHAR(80) = NULL,
    @CurrentValue    NVARCHAR(400) = NULL,
    @RequestedChange NVARCHAR(1000),
    @Notes           NVARCHAR(1000) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @QuoteHeaderId BIGINT, @Status VARCHAR(30);
    SELECT @QuoteHeaderId = QuoteHeaderId FROM quote.QuoteLine WHERE QuoteLineId = @QuoteLineId;
    IF @QuoteHeaderId IS NULL THROW 52320, 'Quote line not found.', 1;
    SELECT @Status = Status FROM quote.QuoteHeader WHERE QuoteHeaderId = @QuoteHeaderId;
    IF @Status <> 'Draft' THROW 52321, 'Customizations can only be edited on a draft quote.', 1;

    INSERT INTO quote.QuoteLineCustomization
        (QuoteLineId, Grouping, FieldCode, CurrentValue, RequestedChange, Notes)
    VALUES (@QuoteLineId, @Grouping, @FieldCode, @CurrentValue, @RequestedChange, @Notes);

    SELECT CustomizationId, QuoteLineId, Grouping, FieldCode, CurrentValue,
           RequestedChange, Notes, RevisionNo, CreatedAt
    FROM quote.QuoteLineCustomization WHERE CustomizationId = SCOPE_IDENTITY();
END;
GO

/* usp_UpdateQuoteLineCustomization ---------------------------------------- */
CREATE OR ALTER PROCEDURE quote.usp_UpdateQuoteLineCustomization
    @CustomizationId BIGINT,
    @Grouping        NVARCHAR(80),
    @FieldCode       NVARCHAR(80) = NULL,
    @CurrentValue    NVARCHAR(400) = NULL,
    @RequestedChange NVARCHAR(1000),
    @Notes           NVARCHAR(1000) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @QuoteLineId BIGINT, @QuoteHeaderId BIGINT, @Status VARCHAR(30);
    SELECT @QuoteLineId = QuoteLineId FROM quote.QuoteLineCustomization WHERE CustomizationId = @CustomizationId;
    IF @QuoteLineId IS NULL THROW 52322, 'Customization not found.', 1;
    SELECT @QuoteHeaderId = QuoteHeaderId FROM quote.QuoteLine WHERE QuoteLineId = @QuoteLineId;
    SELECT @Status = Status FROM quote.QuoteHeader WHERE QuoteHeaderId = @QuoteHeaderId;
    IF @Status <> 'Draft' THROW 52321, 'Customizations can only be edited on a draft quote.', 1;

    UPDATE quote.QuoteLineCustomization
    SET Grouping = @Grouping, FieldCode = @FieldCode, CurrentValue = @CurrentValue,
        RequestedChange = @RequestedChange, Notes = @Notes
    WHERE CustomizationId = @CustomizationId;

    SELECT CustomizationId, QuoteLineId, Grouping, FieldCode, CurrentValue,
           RequestedChange, Notes, RevisionNo, CreatedAt
    FROM quote.QuoteLineCustomization WHERE CustomizationId = @CustomizationId;
END;
GO

/* usp_RemoveQuoteLineCustomization ---------------------------------------- */
CREATE OR ALTER PROCEDURE quote.usp_RemoveQuoteLineCustomization
    @CustomizationId BIGINT
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @QuoteLineId BIGINT, @QuoteHeaderId BIGINT, @Status VARCHAR(30);
    SELECT @QuoteLineId = QuoteLineId FROM quote.QuoteLineCustomization WHERE CustomizationId = @CustomizationId;
    IF @QuoteLineId IS NULL THROW 52322, 'Customization not found.', 1;
    SELECT @QuoteHeaderId = QuoteHeaderId FROM quote.QuoteLine WHERE QuoteLineId = @QuoteLineId;
    SELECT @Status = Status FROM quote.QuoteHeader WHERE QuoteHeaderId = @QuoteHeaderId;
    IF @Status <> 'Draft' THROW 52321, 'Customizations can only be edited on a draft quote.', 1;

    DELETE FROM quote.QuoteLineCustomization WHERE CustomizationId = @CustomizationId;
    SELECT @QuoteLineId AS QuoteLineId,
           (SELECT COUNT(*) FROM quote.QuoteLineCustomization WHERE QuoteLineId = @QuoteLineId) AS Remaining;
END;
GO

/* usp_ListQuoteLineCustomizations (by line) ------------------------------- */
CREATE OR ALTER PROCEDURE quote.usp_ListQuoteLineCustomizations
    @QuoteLineId BIGINT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT CustomizationId, QuoteLineId, Grouping, FieldCode, CurrentValue,
           RequestedChange, Notes, RevisionNo, CreatedAt
    FROM quote.QuoteLineCustomization
    WHERE QuoteLineId = @QuoteLineId
    ORDER BY CustomizationId;
END;
GO

/* usp_ListQuoteCustomizations (all lines of a quote) ---------------------- */
CREATE OR ALTER PROCEDURE quote.usp_ListQuoteCustomizations
    @QuoteHeaderId BIGINT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT c.CustomizationId, c.QuoteLineId, ql.LineNumber, c.Grouping, c.FieldCode,
           c.CurrentValue, c.RequestedChange, c.Notes, c.RevisionNo, c.CreatedAt
    FROM quote.QuoteLineCustomization c
    JOIN quote.QuoteLine ql ON ql.QuoteLineId = c.QuoteLineId
    WHERE ql.QuoteHeaderId = @QuoteHeaderId
    ORDER BY ql.LineNumber, c.CustomizationId;
END;
GO

PRINT 'CPQ A2: quote.QuoteLineCustomization + CRUD procs created (additive).';
GO

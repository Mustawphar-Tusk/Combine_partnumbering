/* ================================================================
   CPQ SPA U4 - QUOTE CUSTOMER PARTY (contact + ship-to on a quote)
   ----------------------------------------------------------------
   ADDITIVE ONLY. New table quote.QuoteParty + two procs. Lets a quote
   carry structured customer CONTACT details and a SHIP_TO address,
   mirroring acct.Address (sql/27) but linked to a quote (not an
   onboarding application) and with Email + CompanyName added.

   One CONTACT row and one SHIP_TO row per quote (UNIQUE quote+kind).
   Upsert is DRAFT-ONLY, consistent with the A1/A2 line-edit guards.

   No change to quote.QuoteHeader / QuoteLine or any cfg/stg/price
   object. Fybroc (PumpFamilyId 2) untouched.
   ================================================================ */

SET NOCOUNT ON;
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

USE PumpConfiguratorDB;
GO

IF OBJECT_ID('quote.QuoteParty', 'U') IS NULL
BEGIN
    CREATE TABLE quote.QuoteParty (
        QuotePartyId   BIGINT IDENTITY(1,1) NOT NULL
            CONSTRAINT PK_quote_QuoteParty PRIMARY KEY,
        QuoteHeaderId  BIGINT NOT NULL,
        Kind           VARCHAR(10) NOT NULL,
        CompanyName    NVARCHAR(200) NULL,
        FirstName      NVARCHAR(100) NULL,
        LastName       NVARCHAR(100) NULL,
        Address1       NVARCHAR(200) NULL,
        Address2       NVARCHAR(200) NULL,
        City           NVARCHAR(120) NULL,
        State          NVARCHAR(120) NULL,
        PostalCode     NVARCHAR(40)  NULL,
        Country        NVARCHAR(120) NULL,
        Phone          NVARCHAR(60)  NULL,
        Email          NVARCHAR(200) NULL,
        UpdatedAt      DATETIME2(3) NOT NULL
            CONSTRAINT DF_quote_QuoteParty_UpdatedAt DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT FK_quote_QuoteParty_Header
            FOREIGN KEY (QuoteHeaderId) REFERENCES quote.QuoteHeader (QuoteHeaderId),
        CONSTRAINT CK_quote_QuoteParty_Kind
            CHECK (Kind IN ('CONTACT','SHIP_TO')),
        CONSTRAINT UQ_quote_QuoteParty_Quote_Kind
            UNIQUE (QuoteHeaderId, Kind)
    );
END
GO

/* ---------------------------------------------------------------
   usp_UpsertQuoteParty - idempotent upsert of ONE party row (CONTACT
   or SHIP_TO) for a quote. Draft-only: a confirmed/submitted quote's
   customer party cannot be rewritten (THROW 52341), matching the
   A1/A2 draft-only edit guards. Returns the stored row.
   --------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE quote.usp_UpsertQuoteParty
    @QuoteHeaderId BIGINT,
    @Kind          VARCHAR(10),
    @CompanyName   NVARCHAR(200) = NULL,
    @FirstName     NVARCHAR(100) = NULL,
    @LastName      NVARCHAR(100) = NULL,
    @Address1      NVARCHAR(200) = NULL,
    @Address2      NVARCHAR(200) = NULL,
    @City          NVARCHAR(120) = NULL,
    @State         NVARCHAR(120) = NULL,
    @PostalCode    NVARCHAR(40)  = NULL,
    @Country       NVARCHAR(120) = NULL,
    @Phone         NVARCHAR(60)  = NULL,
    @Email         NVARCHAR(200) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF @Kind NOT IN ('CONTACT','SHIP_TO')
        THROW 52340, 'Party kind must be CONTACT or SHIP_TO.', 1;

    DECLARE @Status VARCHAR(20) =
        (SELECT Status FROM quote.QuoteHeader WHERE QuoteHeaderId = @QuoteHeaderId);
    IF @Status IS NULL
        THROW 52342, 'Quote not found.', 1;
    IF @Status <> 'Draft'
        THROW 52341, 'Only draft quotes can have their customer party edited.', 1;

    MERGE quote.QuoteParty AS tgt
    USING (SELECT @QuoteHeaderId AS QuoteHeaderId, @Kind AS Kind) AS src
        ON tgt.QuoteHeaderId = src.QuoteHeaderId AND tgt.Kind = src.Kind
    WHEN MATCHED THEN UPDATE SET
        CompanyName = @CompanyName, FirstName = @FirstName, LastName = @LastName,
        Address1 = @Address1, Address2 = @Address2, City = @City, State = @State,
        PostalCode = @PostalCode, Country = @Country, Phone = @Phone, Email = @Email,
        UpdatedAt = SYSUTCDATETIME()
    WHEN NOT MATCHED THEN INSERT
        (QuoteHeaderId, Kind, CompanyName, FirstName, LastName, Address1, Address2,
         City, State, PostalCode, Country, Phone, Email)
        VALUES
        (@QuoteHeaderId, @Kind, @CompanyName, @FirstName, @LastName, @Address1, @Address2,
         @City, @State, @PostalCode, @Country, @Phone, @Email);

    SELECT QuotePartyId, QuoteHeaderId, Kind, CompanyName, FirstName, LastName,
           Address1, Address2, City, State, PostalCode, Country, Phone, Email, UpdatedAt
    FROM quote.QuoteParty
    WHERE QuoteHeaderId = @QuoteHeaderId AND Kind = @Kind;
END;
GO

/* ---------------------------------------------------------------
   usp_GetQuoteParties - the 0-2 party rows (CONTACT, SHIP_TO) for a
   quote. CONTACT first, then SHIP_TO.
   --------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE quote.usp_GetQuoteParties
    @QuoteHeaderId BIGINT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT QuotePartyId, QuoteHeaderId, Kind, CompanyName, FirstName, LastName,
           Address1, Address2, City, State, PostalCode, Country, Phone, Email, UpdatedAt
    FROM quote.QuoteParty
    WHERE QuoteHeaderId = @QuoteHeaderId
    ORDER BY CASE Kind WHEN 'CONTACT' THEN 0 ELSE 1 END;
END;
GO

PRINT 'CPQ U4: quote.QuoteParty + usp_UpsertQuoteParty + usp_GetQuoteParties created (additive).';
GO

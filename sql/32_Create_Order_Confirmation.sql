/* ================================================================
   CPQ ADJUSTMENTS A6 - ORDER CONFIRMATION (retry-safe) + DOCUMENT
   ----------------------------------------------------------------
   ADDITIVE ONLY. New table quote.OrderConfirmation + procs to confirm
   the exact reviewed revision of a completed review case and read the
   completed order record. Both the distributor and the responsible
   engineer read the SAME persisted record (so the PDF each generates is
   identical). Confirmation is IDEMPOTENT (retry-safe): a unique key on
   (ReviewCaseId, ConfirmedRevisionNo) means repeated clicks return the
   existing order, never a duplicate.

   "Confirm Order" completes the CPQ workflow only; no D365/external order
   creation. The quote number remains the human document id; an additional
   CPQ order id (CpqOrderNumber) is minted for the order record.

   No cfg/price/stg touch; quote + acct schema only. Fybroc frozen.
   ================================================================ */

SET NOCOUNT ON;
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

USE PumpConfiguratorDB;
GO

IF OBJECT_ID('quote.OrderConfirmation', 'U') IS NULL
BEGIN
    CREATE TABLE quote.OrderConfirmation (
        OrderConfirmationId   INT IDENTITY(1,1) NOT NULL
            CONSTRAINT PK_quote_OrderConfirmation PRIMARY KEY,
        CpqOrderNumber        VARCHAR(32) NOT NULL,
        QuoteHeaderId         BIGINT NOT NULL,
        ReviewCaseId          INT NOT NULL,
        ConfirmedRevisionNo   INT NOT NULL,
        ConfirmedByAppUserId  INT NULL,
        ConfirmedAt           DATETIME2(3) NOT NULL
            CONSTRAINT DF_quote_OrderConfirmation_At DEFAULT (SYSUTCDATETIME()),
        LeadTimeDays          INT NULL,
        -- Frozen snapshot of the completed order document (JSON): the exact
        -- reviewed lines + totals + loyalty + lead time at confirmation time, so
        -- later catalog/discount changes never alter the confirmed document.
        DocumentJson          NVARCHAR(MAX) NOT NULL,
        CONSTRAINT UQ_quote_OrderConfirmation_CaseRev
            UNIQUE (ReviewCaseId, ConfirmedRevisionNo),
        CONSTRAINT UQ_quote_OrderConfirmation_CpqOrderNumber
            UNIQUE (CpqOrderNumber)
    );
END
GO

/* ---------------------------------------------------------------
   usp_ConfirmOrder - idempotent confirmation of a COMPLETED case's
   reviewed revision. Repeated calls (same case + revision) return the
   existing order row; they never create a duplicate. The caller passes
   the already-rendered DocumentJson snapshot (built by the API from the
   authoritative quote + reviewed lines), which is frozen into the row.
   --------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE quote.usp_ConfirmOrder
    @ReviewCaseId        INT,
    @ConfirmedByAppUserId INT,
    @DocumentJson        NVARCHAR(MAX)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @QuoteHeaderId BIGINT, @Status VARCHAR(24), @Rev INT, @Lead INT;
    SELECT @QuoteHeaderId = QuoteHeaderId, @Status = Status, @Rev = RevisionNo, @Lead = LeadTimeDays
    FROM acct.ReviewCase WHERE ReviewCaseId = @ReviewCaseId;

    IF @QuoteHeaderId IS NULL THROW 52330, 'Review case not found.', 1;
    IF @Status <> 'COMPLETED'
        THROW 52331, 'Only a completed review can be confirmed.', 1;

    -- Idempotent: return the existing order for this (case, revision).
    DECLARE @ExistingId INT = (
        SELECT OrderConfirmationId FROM quote.OrderConfirmation
        WHERE ReviewCaseId = @ReviewCaseId AND ConfirmedRevisionNo = @Rev);
    IF @ExistingId IS NOT NULL
    BEGIN
        SELECT OrderConfirmationId, CpqOrderNumber, QuoteHeaderId, ReviewCaseId,
               ConfirmedRevisionNo, LeadTimeDays, ConfirmedAt, 1 AS WasExisting
        FROM quote.OrderConfirmation WHERE OrderConfirmationId = @ExistingId;
        RETURN;
    END

    BEGIN TRAN;
    DECLARE @newId INT;
    INSERT INTO quote.OrderConfirmation
        (CpqOrderNumber, QuoteHeaderId, ReviewCaseId, ConfirmedRevisionNo,
         ConfirmedByAppUserId, LeadTimeDays, DocumentJson)
    VALUES ('CPQ-PENDING', @QuoteHeaderId, @ReviewCaseId, @Rev,
            @ConfirmedByAppUserId, @Lead, @DocumentJson);
    SET @newId = SCOPE_IDENTITY();
    -- Deterministic CPQ order number from the identity.
    UPDATE quote.OrderConfirmation
    SET CpqOrderNumber = 'CPQ-' + RIGHT('000000' + CAST(@newId AS VARCHAR(10)), 6)
    WHERE OrderConfirmationId = @newId;

    -- Notify the responsible engineer(s) that the order is confirmed.
    DECLARE @site VARCHAR(10), @brand VARCHAR(20), @assignee INT;
    SELECT @site = ResponsibleSiteCode, @brand = Brand, @assignee = AssignedToAppUserId
    FROM acct.ReviewCase WHERE ReviewCaseId = @ReviewCaseId;
    IF @assignee IS NOT NULL
        INSERT INTO acct.Notification (RecipientAppUserId, EventType, ResourceType, ResourceId, Message)
        VALUES (@assignee, 'order_confirmed', 'order',
                CAST(@newId AS VARCHAR(64)),
                N'Distributor confirmed the ' + @brand + N' order (case ' +
                CAST(@ReviewCaseId AS NVARCHAR(10)) + N').');
    INSERT INTO acct.Notification (RecipientRole, EventType, ResourceType, ResourceId, Message)
    VALUES ('engineering:' + @site, 'order_confirmed', 'order',
            CAST(@newId AS VARCHAR(64)),
            N'Order confirmed for a ' + @brand + N' quote (case ' +
            CAST(@ReviewCaseId AS NVARCHAR(10)) + N').');
    COMMIT TRAN;

    SELECT OrderConfirmationId, CpqOrderNumber, QuoteHeaderId, ReviewCaseId,
           ConfirmedRevisionNo, LeadTimeDays, ConfirmedAt, 0 AS WasExisting
    FROM quote.OrderConfirmation WHERE OrderConfirmationId = @newId;
END;
GO

/* ---------------------------------------------------------------
   usp_GetOrderByCase - the confirmed order record (incl. the frozen
   DocumentJson) for a review case, or no rows if not yet confirmed.
   --------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE quote.usp_GetOrderByCase
    @ReviewCaseId INT
AS
BEGIN
    SET NOCOUNT ON;
    SELECT TOP (1) OrderConfirmationId, CpqOrderNumber, QuoteHeaderId, ReviewCaseId,
           ConfirmedRevisionNo, ConfirmedByAppUserId, LeadTimeDays, ConfirmedAt, DocumentJson
    FROM quote.OrderConfirmation
    WHERE ReviewCaseId = @ReviewCaseId
    ORDER BY ConfirmedRevisionNo DESC;
END;
GO

PRINT 'CPQ A6: quote.OrderConfirmation + usp_ConfirmOrder + usp_GetOrderByCase created (additive).';
GO

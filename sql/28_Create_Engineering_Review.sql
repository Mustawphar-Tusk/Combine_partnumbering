/* ================================================================
   CPQ SPA U3 - ENGINEERING REVIEW QUEUE  (schema: acct)
   ----------------------------------------------------------------
   ADDITIVE ONLY. Creates new acct.Review* tables + acct.usp_* procs
   for the engineering review queue with REQUIRED brand/site routing
   (DEAN->IND, FYBROC->TEL). Does NOT drop or alter any existing object
   in cfg / price / quote / stg / acct. Idempotent (IF NOT EXISTS /
   CREATE OR ALTER) - safe to re-run on the populated DB.

   Routing authority: brand is derived SERVER-SIDE from the persisted
   quote's lines (quote.QuoteLine.FamilyCode); the responsible site is
   resolved from acct.BrandSiteRouting (seeded in U1). Never from a
   client-supplied family/site. Missing/ambiguous brand -> a
   routing_exception event + case flagged (never a silent fallback).

   Fybroc is frozen and Dean untouched: this migration only adds to the
   acct schema and READS quote.QuoteLine.FamilyCode; it writes nothing in
   cfg/price/quote config data.
   ================================================================ */

SET NOCOUNT ON;
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

USE PumpConfiguratorDB;
GO

/* ---------------------------------------------------------------
   1. ReviewCase - one engineering review case per submitted quote
   --------------------------------------------------------------- */
IF OBJECT_ID('acct.ReviewCase', 'U') IS NULL
BEGIN
    CREATE TABLE acct.ReviewCase (
        ReviewCaseId         INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_acct_ReviewCase PRIMARY KEY,
        QuoteHeaderId        BIGINT NOT NULL,
        Brand                VARCHAR(20) NOT NULL,
        ResponsibleSiteCode  VARCHAR(10) NOT NULL,
        Status               VARCHAR(24) NOT NULL CONSTRAINT DF_acct_ReviewCase_Status DEFAULT ('PENDING_REVIEW'),
        SubmittedByAppUserId INT NULL,
        SubmittedAt          DATETIME2(3) NOT NULL CONSTRAINT DF_acct_ReviewCase_SubmittedAt DEFAULT (SYSUTCDATETIME()),
        AssignedToAppUserId  INT NULL,
        ClaimedAt            DATETIME2(3) NULL,
        CompletedAt          DATETIME2(3) NULL,
        RevisionNo           INT NOT NULL CONSTRAINT DF_acct_ReviewCase_Rev DEFAULT (1),
        LeadTimeDays         INT NULL,
        ReviewNotes          NVARCHAR(2000) NULL,
        RoutingException     BIT NOT NULL CONSTRAINT DF_acct_ReviewCase_RoutingExc DEFAULT (0),
        CONSTRAINT CK_acct_ReviewCase_Brand CHECK (Brand IN ('DEAN','FYBROC')),
        CONSTRAINT CK_acct_ReviewCase_Site CHECK (ResponsibleSiteCode IN ('IND','TEL')),
        CONSTRAINT CK_acct_ReviewCase_Status
            CHECK (Status IN ('PENDING_REVIEW','CLAIMED','CHANGES_REQUESTED','COMPLETED','CANCELLED','ROUTING_EXCEPTION')),
        CONSTRAINT FK_acct_ReviewCase_SubmittedBy
            FOREIGN KEY (SubmittedByAppUserId) REFERENCES acct.AppUser (AppUserId),
        CONSTRAINT FK_acct_ReviewCase_AssignedTo
            FOREIGN KEY (AssignedToAppUserId) REFERENCES acct.AppUser (AppUserId)
    );
    -- At most one OPEN (non-terminal) case per quote.
    CREATE UNIQUE INDEX UQ_acct_ReviewCase_OpenPerQuote
        ON acct.ReviewCase (QuoteHeaderId)
        WHERE Status IN ('PENDING_REVIEW','CLAIMED','CHANGES_REQUESTED','ROUTING_EXCEPTION');
END
GO

/* ---------------------------------------------------------------
   2. ReviewCaseLine - per-line review detail (C/F items to resolve)
   --------------------------------------------------------------- */
IF OBJECT_ID('acct.ReviewCaseLine', 'U') IS NULL
BEGIN
    CREATE TABLE acct.ReviewCaseLine (
        ReviewCaseLineId    INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_acct_ReviewCaseLine PRIMARY KEY,
        ReviewCaseId        INT NOT NULL,
        QuoteLineId         BIGINT NOT NULL,
        LineNumber          INT NOT NULL,
        PartNumber          VARCHAR(100) NULL,
        PricingStatus       VARCHAR(24) NULL,   -- snapshot at submit
        ResolvedUnitPrice   DECIMAL(18,2) NULL, -- engineer-entered
        CustomSpec          NVARCHAR(1000) NULL,
        EngineerNote        NVARCHAR(1000) NULL,
        ResolvedAt          DATETIME2(3) NULL,
        ResolvedByAppUserId INT NULL,
        CONSTRAINT FK_acct_ReviewCaseLine_Case
            FOREIGN KEY (ReviewCaseId) REFERENCES acct.ReviewCase (ReviewCaseId),
        CONSTRAINT FK_acct_ReviewCaseLine_ResolvedBy
            FOREIGN KEY (ResolvedByAppUserId) REFERENCES acct.AppUser (AppUserId)
    );
END
GO

/* ---------------------------------------------------------------
   3. ReviewEvent - append-only routing/assignment/review history
   --------------------------------------------------------------- */
IF OBJECT_ID('acct.ReviewEvent', 'U') IS NULL
BEGIN
    CREATE TABLE acct.ReviewEvent (
        ReviewEventId   INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_acct_ReviewEvent PRIMARY KEY,
        ReviewCaseId    INT NOT NULL,
        EventType       VARCHAR(30) NOT NULL,
        ActorAppUserId  INT NULL,
        DetailJson      NVARCHAR(2000) NULL,
        CreatedAt       DATETIME2(3) NOT NULL CONSTRAINT DF_acct_ReviewEvent_CreatedAt DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT CK_acct_ReviewEvent_Type
            CHECK (EventType IN ('submitted','routed','claimed','changes_requested',
                                 'line_resolved','completed','reassigned','routing_exception')),
        CONSTRAINT FK_acct_ReviewEvent_Case
            FOREIGN KEY (ReviewCaseId) REFERENCES acct.ReviewCase (ReviewCaseId)
    );
END
GO

PRINT 'CPQ U3: acct review tables created (additive).';
GO

/* ================================================================
   STORED PROCEDURES
   ================================================================ */

/* ---------------------------------------------------------------
   usp_SubmitQuoteForReview - derive brand from the quote's lines,
   resolve the responsible site from acct.BrandSiteRouting, create a
   case + line snapshot + events. One OPEN case per quote (idempotent-ish:
   returns the existing open case). Missing/ambiguous brand or missing
   routing row -> a ROUTING_EXCEPTION case + event (never silent fallback).
   --------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE acct.usp_SubmitQuoteForReview
    @QuoteHeaderId        BIGINT,
    @SubmittedByAppUserId INT
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    -- Return an already-open case unchanged.
    DECLARE @ExistingCaseId INT = (
        SELECT TOP (1) ReviewCaseId FROM acct.ReviewCase
        WHERE QuoteHeaderId = @QuoteHeaderId
          AND Status IN ('PENDING_REVIEW','CLAIMED','CHANGES_REQUESTED','ROUTING_EXCEPTION')
        ORDER BY ReviewCaseId DESC);
    IF @ExistingCaseId IS NOT NULL
    BEGIN
        SELECT ReviewCaseId, QuoteHeaderId, Brand, ResponsibleSiteCode, Status,
               RoutingException, 1 AS WasExisting
        FROM acct.ReviewCase WHERE ReviewCaseId = @ExistingCaseId;
        RETURN;
    END

    -- Quote must exist and have at least one line.
    IF NOT EXISTS (SELECT 1 FROM quote.QuoteHeader WHERE QuoteHeaderId = @QuoteHeaderId)
    BEGIN
        RAISERROR('Quote not found.', 16, 1);
        RETURN;
    END

    -- Derive brand from the persisted quote lines (NEVER a client param).
    DECLARE @distinctBrands INT = (
        SELECT COUNT(DISTINCT UPPER(FamilyCode)) FROM quote.QuoteLine
        WHERE QuoteHeaderId = @QuoteHeaderId);
    DECLARE @Brand VARCHAR(20) = (
        SELECT TOP (1) UPPER(FamilyCode) FROM quote.QuoteLine
        WHERE QuoteHeaderId = @QuoteHeaderId);

    BEGIN TRAN;

    DECLARE @caseId INT, @site VARCHAR(10), @status VARCHAR(24), @routingExc BIT = 0;

    IF @distinctBrands IS NULL OR @distinctBrands = 0 OR @Brand IS NULL
    BEGIN
        -- No lines / no brand: cannot route.
        SET @routingExc = 1; SET @status = 'ROUTING_EXCEPTION'; SET @Brand = 'DEAN'; SET @site = 'IND';
    END
    ELSE IF @distinctBrands > 1
    BEGIN
        -- Mixed-brand quote (D7 says single-brand): route exception for admin.
        SET @routingExc = 1; SET @status = 'ROUTING_EXCEPTION'; SET @site = 'IND';
    END
    ELSE
    BEGIN
        SET @site = (SELECT SiteCode FROM acct.BrandSiteRouting
                     WHERE Brand = @Brand AND IsActive = 1);
        IF @site IS NULL
        BEGIN
            -- Missing routing metadata for this brand.
            SET @routingExc = 1; SET @status = 'ROUTING_EXCEPTION'; SET @site = 'IND';
        END
        ELSE
            SET @status = 'PENDING_REVIEW';
    END

    INSERT INTO acct.ReviewCase
        (QuoteHeaderId, Brand, ResponsibleSiteCode, Status, SubmittedByAppUserId, RoutingException)
    VALUES (@QuoteHeaderId, @Brand, @site, @status, @SubmittedByAppUserId, @routingExc);
    SET @caseId = SCOPE_IDENTITY();

    -- Snapshot the quote lines for review.
    INSERT INTO acct.ReviewCaseLine
        (ReviewCaseId, QuoteLineId, LineNumber, PartNumber, PricingStatus)
    SELECT @caseId, ql.QuoteLineId, ql.LineNumber, ql.PartNumber, ql.PricingStatus
    FROM quote.QuoteLine ql
    WHERE ql.QuoteHeaderId = @QuoteHeaderId;

    INSERT INTO acct.ReviewEvent (ReviewCaseId, EventType, ActorAppUserId, DetailJson)
    VALUES (@caseId, 'submitted', @SubmittedByAppUserId,
            (SELECT @Brand AS brand, @site AS site FOR JSON PATH, WITHOUT_ARRAY_WRAPPER));

    IF @routingExc = 1
        INSERT INTO acct.ReviewEvent (ReviewCaseId, EventType, ActorAppUserId, DetailJson)
        VALUES (@caseId, 'routing_exception', @SubmittedByAppUserId,
                (SELECT @distinctBrands AS distinct_brands, @Brand AS brand FOR JSON PATH, WITHOUT_ARRAY_WRAPPER));
    ELSE
    BEGIN
        INSERT INTO acct.ReviewEvent (ReviewCaseId, EventType, ActorAppUserId, DetailJson)
        VALUES (@caseId, 'routed', @SubmittedByAppUserId,
                (SELECT @Brand AS brand, @site AS site FOR JSON PATH, WITHOUT_ARRAY_WRAPPER));
        -- Notify the responsible engineering team (role-scoped notification).
        INSERT INTO acct.Notification (RecipientRole, EventType, ResourceType, ResourceId, Message)
        VALUES ('engineering:' + @site, 'review_submitted', 'review_case',
                CAST(@caseId AS VARCHAR(64)),
                N'New ' + @Brand + N' quote submitted for review (' + @site + N').');
    END

    COMMIT TRAN;

    SELECT @caseId AS ReviewCaseId, @QuoteHeaderId AS QuoteHeaderId, @Brand AS Brand,
           @site AS ResponsibleSiteCode, @status AS Status, @routingExc AS RoutingException,
           0 AS WasExisting;
END;
GO

/* ---------------------------------------------------------------
   usp_ListReviewCases - cases scoped to a brand/site set.
   @SiteCsv = comma list of sites the caller is authorized for (from
   EngineerMembership), or NULL for admin oversight (all). @Brand filter
   is derived from the authorized memberships by the API; here we scope
   strictly by site to match the brand->site routing.
   --------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE acct.usp_ListReviewCases
    @SiteCsv  VARCHAR(100) = NULL,   -- NULL => all (admin oversight)
    @Status   VARCHAR(24) = NULL,
    @AdminAll BIT = 0
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        rc.ReviewCaseId, rc.QuoteHeaderId, rc.Brand, rc.ResponsibleSiteCode,
        rc.Status, rc.RoutingException, rc.SubmittedAt, rc.AssignedToAppUserId,
        rc.LeadTimeDays, rc.RevisionNo,
        qh.QuoteNumber, qh.CustomerName,
        asg.Email AS AssignedToEmail
    FROM acct.ReviewCase rc
    LEFT JOIN quote.QuoteHeader qh ON qh.QuoteHeaderId = rc.QuoteHeaderId
    LEFT JOIN acct.AppUser asg ON asg.AppUserId = rc.AssignedToAppUserId
    WHERE (@AdminAll = 1
           OR (@SiteCsv IS NOT NULL
               AND rc.ResponsibleSiteCode IN
                   (SELECT LTRIM(RTRIM(value)) FROM STRING_SPLIT(@SiteCsv, ','))))
      AND (@Status IS NULL OR rc.Status = @Status)
    ORDER BY rc.ReviewCaseId DESC;
END;
GO

/* ---------------------------------------------------------------
   usp_GetReviewCase - case header + lines, SCOPE-CHECKED. Returns no
   rows if the case's site is not in @SiteCsv (and not admin). Two result
   sets: header, then lines.
   --------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE acct.usp_GetReviewCase
    @ReviewCaseId INT,
    @SiteCsv      VARCHAR(100) = NULL,
    @AdminAll     BIT = 0
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @authorized BIT = 0;
    IF @AdminAll = 1
        SET @authorized = 1;
    ELSE IF @SiteCsv IS NOT NULL AND EXISTS (
        SELECT 1 FROM acct.ReviewCase rc
        WHERE rc.ReviewCaseId = @ReviewCaseId
          AND rc.ResponsibleSiteCode IN
              (SELECT LTRIM(RTRIM(value)) FROM STRING_SPLIT(@SiteCsv, ',')))
        SET @authorized = 1;

    IF @authorized = 0
        RETURN;  -- not found/authorized to this caller

    SELECT rc.ReviewCaseId, rc.QuoteHeaderId, rc.Brand, rc.ResponsibleSiteCode,
           rc.Status, rc.RoutingException, rc.SubmittedAt, rc.SubmittedByAppUserId,
           rc.AssignedToAppUserId, rc.ClaimedAt, rc.CompletedAt, rc.RevisionNo,
           rc.LeadTimeDays, rc.ReviewNotes, qh.QuoteNumber, qh.CustomerName
    FROM acct.ReviewCase rc
    LEFT JOIN quote.QuoteHeader qh ON qh.QuoteHeaderId = rc.QuoteHeaderId
    WHERE rc.ReviewCaseId = @ReviewCaseId;

    SELECT ReviewCaseLineId, QuoteLineId, LineNumber, PartNumber, PricingStatus,
           ResolvedUnitPrice, CustomSpec, EngineerNote, ResolvedAt
    FROM acct.ReviewCaseLine
    WHERE ReviewCaseId = @ReviewCaseId
    ORDER BY LineNumber;
END;
GO

/* ---------------------------------------------------------------
   usp_ClaimReviewCase - scope-checked claim (PENDING_REVIEW/CHANGES ->
   CLAIMED, assign to the engineer). Rejects if not authorized for the
   case's site, or if already completed/cancelled.
   --------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE acct.usp_ClaimReviewCase
    @ReviewCaseId INT,
    @EngineerAppUserId INT,
    @SiteCsv VARCHAR(100)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @site VARCHAR(10), @status VARCHAR(24);
    SELECT @site = ResponsibleSiteCode, @status = Status
    FROM acct.ReviewCase WHERE ReviewCaseId = @ReviewCaseId;

    IF @site IS NULL
    BEGIN RAISERROR('Review case not found.', 16, 1); RETURN; END
    IF @SiteCsv IS NULL OR @site NOT IN (SELECT LTRIM(RTRIM(value)) FROM STRING_SPLIT(@SiteCsv, ','))
    BEGIN RAISERROR('Not authorized for this case site.', 16, 1); RETURN; END
    IF @status NOT IN ('PENDING_REVIEW','CHANGES_REQUESTED')
    BEGIN RAISERROR('Case cannot be claimed in its current status.', 16, 1); RETURN; END

    BEGIN TRAN;
    UPDATE acct.ReviewCase
    SET Status = 'CLAIMED', AssignedToAppUserId = @EngineerAppUserId, ClaimedAt = SYSUTCDATETIME()
    WHERE ReviewCaseId = @ReviewCaseId;
    INSERT INTO acct.ReviewEvent (ReviewCaseId, EventType, ActorAppUserId)
    VALUES (@ReviewCaseId, 'claimed', @EngineerAppUserId);
    COMMIT TRAN;

    SELECT @ReviewCaseId AS ReviewCaseId, 'CLAIMED' AS Status;
END;
GO

/* ---------------------------------------------------------------
   usp_ResolveReviewCaseLine - engineer resolves a C/F / custom line
   (unit price + custom spec + note). Scope-checked via the case site.
   --------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE acct.usp_ResolveReviewCaseLine
    @ReviewCaseId      INT,
    @ReviewCaseLineId  INT,
    @EngineerAppUserId INT,
    @SiteCsv           VARCHAR(100),
    @ResolvedUnitPrice DECIMAL(18,2) = NULL,
    @CustomSpec        NVARCHAR(1000) = NULL,
    @EngineerNote      NVARCHAR(1000) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @site VARCHAR(10);
    SELECT @site = rc.ResponsibleSiteCode
    FROM acct.ReviewCase rc
    JOIN acct.ReviewCaseLine rcl ON rcl.ReviewCaseId = rc.ReviewCaseId
    WHERE rc.ReviewCaseId = @ReviewCaseId AND rcl.ReviewCaseLineId = @ReviewCaseLineId;

    IF @site IS NULL
    BEGIN RAISERROR('Review case line not found.', 16, 1); RETURN; END
    IF @SiteCsv IS NULL OR @site NOT IN (SELECT LTRIM(RTRIM(value)) FROM STRING_SPLIT(@SiteCsv, ','))
    BEGIN RAISERROR('Not authorized for this case site.', 16, 1); RETURN; END

    BEGIN TRAN;
    UPDATE acct.ReviewCaseLine
    SET ResolvedUnitPrice = @ResolvedUnitPrice, CustomSpec = @CustomSpec,
        EngineerNote = @EngineerNote, ResolvedAt = SYSUTCDATETIME(),
        ResolvedByAppUserId = @EngineerAppUserId
    WHERE ReviewCaseLineId = @ReviewCaseLineId;
    INSERT INTO acct.ReviewEvent (ReviewCaseId, EventType, ActorAppUserId, DetailJson)
    VALUES (@ReviewCaseId, 'line_resolved', @EngineerAppUserId,
            (SELECT @ReviewCaseLineId AS line_id, @ResolvedUnitPrice AS price
             FOR JSON PATH, WITHOUT_ARRAY_WRAPPER));
    COMMIT TRAN;

    SELECT @ReviewCaseLineId AS ReviewCaseLineId, 'resolved' AS Result;
END;
GO

/* ---------------------------------------------------------------
   usp_RequestReviewChanges - engineer sends the case back for changes.
   --------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE acct.usp_RequestReviewChanges
    @ReviewCaseId      INT,
    @EngineerAppUserId INT,
    @SiteCsv           VARCHAR(100),
    @Notes             NVARCHAR(2000) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @site VARCHAR(10), @status VARCHAR(24), @submittedBy INT;
    SELECT @site = ResponsibleSiteCode, @status = Status, @submittedBy = SubmittedByAppUserId
    FROM acct.ReviewCase WHERE ReviewCaseId = @ReviewCaseId;

    IF @site IS NULL
    BEGIN RAISERROR('Review case not found.', 16, 1); RETURN; END
    IF @SiteCsv IS NULL OR @site NOT IN (SELECT LTRIM(RTRIM(value)) FROM STRING_SPLIT(@SiteCsv, ','))
    BEGIN RAISERROR('Not authorized for this case site.', 16, 1); RETURN; END

    BEGIN TRAN;
    UPDATE acct.ReviewCase
    SET Status = 'CHANGES_REQUESTED', ReviewNotes = @Notes
    WHERE ReviewCaseId = @ReviewCaseId;
    INSERT INTO acct.ReviewEvent (ReviewCaseId, EventType, ActorAppUserId, DetailJson)
    VALUES (@ReviewCaseId, 'changes_requested', @EngineerAppUserId,
            (SELECT @Notes AS notes FOR JSON PATH, WITHOUT_ARRAY_WRAPPER));
    -- Notify the submitting distributor.
    IF @submittedBy IS NOT NULL
        INSERT INTO acct.Notification (RecipientAppUserId, EventType, ResourceType, ResourceId, Message)
        VALUES (@submittedBy, 'review_changes_requested', 'review_case',
                CAST(@ReviewCaseId AS VARCHAR(64)),
                N'Engineering requested changes on your submitted quote.');
    COMMIT TRAN;

    SELECT @ReviewCaseId AS ReviewCaseId, 'CHANGES_REQUESTED' AS Status;
END;
GO

/* ---------------------------------------------------------------
   usp_CompleteReviewCase - engineer completes the review, sets lead
   time, returns the offer to the owning distributor. Scope-checked.
   --------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE acct.usp_CompleteReviewCase
    @ReviewCaseId      INT,
    @EngineerAppUserId INT,
    @SiteCsv           VARCHAR(100),
    @LeadTimeDays      INT = NULL,
    @Notes             NVARCHAR(2000) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @site VARCHAR(10), @status VARCHAR(24), @submittedBy INT, @brand VARCHAR(20);
    SELECT @site = ResponsibleSiteCode, @status = Status, @submittedBy = SubmittedByAppUserId,
           @brand = Brand
    FROM acct.ReviewCase WHERE ReviewCaseId = @ReviewCaseId;

    IF @site IS NULL
    BEGIN RAISERROR('Review case not found.', 16, 1); RETURN; END
    IF @SiteCsv IS NULL OR @site NOT IN (SELECT LTRIM(RTRIM(value)) FROM STRING_SPLIT(@SiteCsv, ','))
    BEGIN RAISERROR('Not authorized for this case site.', 16, 1); RETURN; END
    IF @status = 'COMPLETED'
    BEGIN RAISERROR('Case already completed.', 16, 1); RETURN; END
    IF @status NOT IN ('CLAIMED','CHANGES_REQUESTED')
    BEGIN RAISERROR('Case must be claimed before completion.', 16, 1); RETURN; END

    BEGIN TRAN;
    UPDATE acct.ReviewCase
    SET Status = 'COMPLETED', LeadTimeDays = @LeadTimeDays, ReviewNotes = COALESCE(@Notes, ReviewNotes),
        CompletedAt = SYSUTCDATETIME()
    WHERE ReviewCaseId = @ReviewCaseId;
    INSERT INTO acct.ReviewEvent (ReviewCaseId, EventType, ActorAppUserId, DetailJson)
    VALUES (@ReviewCaseId, 'completed', @EngineerAppUserId,
            (SELECT @LeadTimeDays AS lead_time_days FOR JSON PATH, WITHOUT_ARRAY_WRAPPER));
    -- Return the completed offer/notification to the owning distributor.
    IF @submittedBy IS NOT NULL
        INSERT INTO acct.Notification (RecipientAppUserId, EventType, ResourceType, ResourceId, Message)
        VALUES (@submittedBy, 'review_completed', 'review_case',
                CAST(@ReviewCaseId AS VARCHAR(64)),
                N'Your ' + @brand + N' quote review is complete'
                + CASE WHEN @LeadTimeDays IS NOT NULL
                       THEN N' (lead time ' + CAST(@LeadTimeDays AS NVARCHAR(10)) + N' days).'
                       ELSE N'.' END);
    COMMIT TRAN;

    SELECT @ReviewCaseId AS ReviewCaseId, 'COMPLETED' AS Status, @LeadTimeDays AS LeadTimeDays;
END;
GO

PRINT 'CPQ U3: acct review stored procedures created (additive).';
GO

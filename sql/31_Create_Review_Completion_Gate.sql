/* ================================================================
   CPQ ADJUSTMENTS A5 - REVIEW COMPLETION GATE + FURTHER-REVIEW LOOP
   ----------------------------------------------------------------
   ADDITIVE ONLY (CREATE OR ALTER of an existing proc + one new proc).
   No table/column change. No cfg/price/stg touch; acct schema only.

   1. usp_CompleteReviewCase gains a COMPLETION GATE: engineering may not
      complete a review while required items are unresolved -
        - lead time must be provided, AND
        - no review-case line may remain a Contact-Factory line
          (snapshot PricingStatus <> 'found') without an engineer-entered
          ResolvedUnitPrice.
      (C/F is never silently accepted as a completed/$0 value.)

   2. usp_RequestFurtherReview (new): the owning distributor sends a
      COMPLETED case back to the SAME responsible brand/site team with
      comments. Status -> CHANGES_REQUESTED, RevisionNo bumped, the team
      is re-notified, history appended (never rewritten).
   ================================================================ */

SET NOCOUNT ON;
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

USE PumpConfiguratorDB;
GO

/* ---------------------------------------------------------------
   usp_CompleteReviewCase (re-defined with the completion gate)
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

    /* ---- COMPLETION GATE (A5) ---- */
    IF @LeadTimeDays IS NULL
    BEGIN RAISERROR('Lead time is required before completing the review.', 16, 1); RETURN; END

    DECLARE @UnresolvedCF INT = (
        SELECT COUNT(*) FROM acct.ReviewCaseLine
        WHERE ReviewCaseId = @ReviewCaseId
          AND ISNULL(PricingStatus, '') <> 'found'
          AND ResolvedUnitPrice IS NULL);
    IF @UnresolvedCF > 0
    BEGIN
        RAISERROR('Cannot complete: %d Contact-Factory line(s) still need a resolved price.', 16, 1, @UnresolvedCF);
        RETURN;
    END

    BEGIN TRAN;
    UPDATE acct.ReviewCase
    SET Status = 'COMPLETED', LeadTimeDays = @LeadTimeDays, ReviewNotes = COALESCE(@Notes, ReviewNotes),
        CompletedAt = SYSUTCDATETIME()
    WHERE ReviewCaseId = @ReviewCaseId;
    INSERT INTO acct.ReviewEvent (ReviewCaseId, EventType, ActorAppUserId, DetailJson)
    VALUES (@ReviewCaseId, 'completed', @EngineerAppUserId,
            (SELECT @LeadTimeDays AS lead_time_days FOR JSON PATH, WITHOUT_ARRAY_WRAPPER));
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

/* ---------------------------------------------------------------
   usp_RequestFurtherReview - distributor returns a COMPLETED case to
   the responsible team for another pass. Ownership-checked against the
   submitting distributor. Bumps RevisionNo; re-notifies the team.
   --------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE acct.usp_RequestFurtherReview
    @ReviewCaseId   INT,
    @AppUserId      INT,
    @Comments       NVARCHAR(2000) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @site VARCHAR(10), @status VARCHAR(24), @submittedBy INT, @brand VARCHAR(20), @rev INT;
    SELECT @site = ResponsibleSiteCode, @status = Status, @submittedBy = SubmittedByAppUserId,
           @brand = Brand, @rev = RevisionNo
    FROM acct.ReviewCase WHERE ReviewCaseId = @ReviewCaseId;

    IF @site IS NULL
    BEGIN RAISERROR('Review case not found.', 16, 1); RETURN; END
    -- Ownership: only the submitting distributor may request further review.
    IF @submittedBy IS NULL OR @submittedBy <> @AppUserId
    BEGIN RAISERROR('Not authorized to request further review on this case.', 16, 1); RETURN; END
    IF @status <> 'COMPLETED'
    BEGIN RAISERROR('Further review can only be requested on a completed case.', 16, 1); RETURN; END

    BEGIN TRAN;
    UPDATE acct.ReviewCase
    SET Status = 'CHANGES_REQUESTED',
        RevisionNo = @rev + 1,
        CompletedAt = NULL,
        ReviewNotes = @Comments
    WHERE ReviewCaseId = @ReviewCaseId;

    INSERT INTO acct.ReviewEvent (ReviewCaseId, EventType, ActorAppUserId, DetailJson)
    VALUES (@ReviewCaseId, 'changes_requested', @AppUserId,
            (SELECT @Comments AS comments, @rev + 1 AS revision FOR JSON PATH, WITHOUT_ARRAY_WRAPPER));

    -- Re-notify the responsible brand/site engineering team.
    INSERT INTO acct.Notification (RecipientRole, EventType, ResourceType, ResourceId, Message)
    VALUES ('engineering:' + @site, 'review_submitted', 'review_case',
            CAST(@ReviewCaseId AS VARCHAR(64)),
            N'Further review requested by distributor on a ' + @brand + N' quote (rev '
            + CAST(@rev + 1 AS NVARCHAR(10)) + N').');

    COMMIT TRAN;

    SELECT @ReviewCaseId AS ReviewCaseId, 'CHANGES_REQUESTED' AS Status, @rev + 1 AS RevisionNo;
END;
GO

PRINT 'CPQ A5: completion gate + usp_RequestFurtherReview created (additive).';
GO

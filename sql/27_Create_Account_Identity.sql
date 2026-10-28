/* ================================================================
   CPQ SPA U1 - ACCOUNT / IDENTITY MODEL  (schema: acct)
   ----------------------------------------------------------------
   ADDITIVE ONLY. This migration creates a brand-new `acct` schema and
   its tables + stored procedures. It does NOT drop or alter any
   existing object in cfg / price / quote / stg / audit. It is fully
   idempotent (guarded with IF NOT EXISTS / CREATE OR ALTER) so it is
   safe to re-run on the populated PumpConfiguratorDB.

   Scope (U1): distributor identity + onboarding application + admin
   approval + loyalty tiers + notifications + brand/site routing seed.
   Audit of these actions REUSES cfg.AuditLog (no new audit table).

   Fybroc is frozen and Dean is untouched: this migration only adds a
   new schema and reads/writes nothing in cfg/price/quote config data.
   ================================================================ */

SET NOCOUNT ON;
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

USE PumpConfiguratorDB;
GO

/* ---------------------------------------------------------------
   1. Schema
   --------------------------------------------------------------- */
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'acct')
    EXEC('CREATE SCHEMA acct AUTHORIZATION dbo;');
GO

/* ---------------------------------------------------------------
   2. LoyaltyTier  (authoritative discount source - D4)
   --------------------------------------------------------------- */
IF OBJECT_ID('acct.LoyaltyTier', 'U') IS NULL
BEGIN
    CREATE TABLE acct.LoyaltyTier (
        LoyaltyTierCode  VARCHAR(20)  NOT NULL CONSTRAINT PK_acct_LoyaltyTier PRIMARY KEY,
        DisplayName      NVARCHAR(80) NOT NULL,
        RateBp           INT          NOT NULL,   -- basis points: 0, 1500, 3000
        IsActive         BIT          NOT NULL CONSTRAINT DF_acct_LoyaltyTier_IsActive DEFAULT (1),
        CreatedAt        DATETIME2(3) NOT NULL CONSTRAINT DF_acct_LoyaltyTier_CreatedAt DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT CK_acct_LoyaltyTier_RateBp CHECK (RateBp BETWEEN 0 AND 10000)
    );
END
GO

/* ---------------------------------------------------------------
   3. AppUser  (identity link; Entra owns authentication)
   --------------------------------------------------------------- */
IF OBJECT_ID('acct.AppUser', 'U') IS NULL
BEGIN
    CREATE TABLE acct.AppUser (
        AppUserId    INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_acct_AppUser PRIMARY KEY,
        IdpIssuer    NVARCHAR(256) NOT NULL,     -- token 'iss'
        IdpSubject   NVARCHAR(256) NOT NULL,     -- token 'sub'/'oid'
        Email        NVARCHAR(256) NULL,
        DisplayName  NVARCHAR(200) NULL,
        IsActive     BIT NOT NULL CONSTRAINT DF_acct_AppUser_IsActive DEFAULT (1),
        CreatedAt    DATETIME2(3) NOT NULL CONSTRAINT DF_acct_AppUser_CreatedAt DEFAULT (SYSUTCDATETIME()),
        LastSeenAt   DATETIME2(3) NULL,
        CONSTRAINT UQ_acct_AppUser_Idp UNIQUE (IdpIssuer, IdpSubject)
    );
END
GO

/* ---------------------------------------------------------------
   4. DistributorAccount
   --------------------------------------------------------------- */
IF OBJECT_ID('acct.DistributorAccount', 'U') IS NULL
BEGIN
    CREATE TABLE acct.DistributorAccount (
        DistributorAccountId INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_acct_DistributorAccount PRIMARY KEY,
        CompanyName          NVARCHAR(200) NOT NULL,
        Status               VARCHAR(24) NOT NULL CONSTRAINT DF_acct_DistributorAccount_Status DEFAULT ('DRAFT'),
        LoyaltyTierCode      VARCHAR(20) NULL,
        CreatedAt            DATETIME2(3) NOT NULL CONSTRAINT DF_acct_DistributorAccount_CreatedAt DEFAULT (SYSUTCDATETIME()),
        CreatedByAppUserId   INT NULL,
        UpdatedAt            DATETIME2(3) NULL,
        CONSTRAINT CK_acct_DistributorAccount_Status
            CHECK (Status IN ('DRAFT','PENDING_APPROVAL','APPROVED','CHANGES_REQUESTED','REJECTED','SUSPENDED')),
        CONSTRAINT FK_acct_DistributorAccount_Loyalty
            FOREIGN KEY (LoyaltyTierCode) REFERENCES acct.LoyaltyTier (LoyaltyTierCode),
        CONSTRAINT FK_acct_DistributorAccount_CreatedBy
            FOREIGN KEY (CreatedByAppUserId) REFERENCES acct.AppUser (AppUserId)
    );
END
GO

/* ---------------------------------------------------------------
   5. AccountMembership  (users belonging to a distributor org)
   --------------------------------------------------------------- */
IF OBJECT_ID('acct.AccountMembership', 'U') IS NULL
BEGIN
    CREATE TABLE acct.AccountMembership (
        AccountMembershipId  INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_acct_AccountMembership PRIMARY KEY,
        DistributorAccountId INT NOT NULL,
        AppUserId            INT NOT NULL,
        MemberRole           VARCHAR(20) NOT NULL CONSTRAINT DF_acct_AccountMembership_Role DEFAULT ('member'),
        CreatedAt            DATETIME2(3) NOT NULL CONSTRAINT DF_acct_AccountMembership_CreatedAt DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT UQ_acct_AccountMembership UNIQUE (DistributorAccountId, AppUserId),
        CONSTRAINT CK_acct_AccountMembership_Role CHECK (MemberRole IN ('owner','member')),
        CONSTRAINT FK_acct_AccountMembership_Account
            FOREIGN KEY (DistributorAccountId) REFERENCES acct.DistributorAccount (DistributorAccountId),
        CONSTRAINT FK_acct_AccountMembership_User
            FOREIGN KEY (AppUserId) REFERENCES acct.AppUser (AppUserId)
    );
END
GO

/* ---------------------------------------------------------------
   6. AccountApplication  (onboarding submission + review trail)
   --------------------------------------------------------------- */
IF OBJECT_ID('acct.AccountApplication', 'U') IS NULL
BEGIN
    CREATE TABLE acct.AccountApplication (
        ApplicationId        INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_acct_AccountApplication PRIMARY KEY,
        DistributorAccountId INT NOT NULL,
        SubmittedByAppUserId INT NOT NULL,
        Status               VARCHAR(24) NOT NULL CONSTRAINT DF_acct_AccountApplication_Status DEFAULT ('PENDING_APPROVAL'),
        IdempotencyKey       NVARCHAR(100) NOT NULL,
        SubmittedAt          DATETIME2(3) NOT NULL CONSTRAINT DF_acct_AccountApplication_SubmittedAt DEFAULT (SYSUTCDATETIME()),
        ReviewedByAppUserId  INT NULL,
        ReviewOutcome        VARCHAR(24) NULL,
        ReviewReason         NVARCHAR(1000) NULL,
        AssignedLoyaltyTier  VARCHAR(20) NULL,
        ReviewedAt           DATETIME2(3) NULL,
        CONSTRAINT UQ_acct_AccountApplication_Idem UNIQUE (IdempotencyKey),
        CONSTRAINT CK_acct_AccountApplication_Status
            CHECK (Status IN ('PENDING_APPROVAL','APPROVED','CHANGES_REQUESTED','REJECTED')),
        CONSTRAINT CK_acct_AccountApplication_Outcome
            CHECK (ReviewOutcome IS NULL OR ReviewOutcome IN ('APPROVED','CHANGES_REQUESTED','REJECTED')),
        CONSTRAINT FK_acct_AccountApplication_Account
            FOREIGN KEY (DistributorAccountId) REFERENCES acct.DistributorAccount (DistributorAccountId),
        CONSTRAINT FK_acct_AccountApplication_SubmittedBy
            FOREIGN KEY (SubmittedByAppUserId) REFERENCES acct.AppUser (AppUserId),
        CONSTRAINT FK_acct_AccountApplication_ReviewedBy
            FOREIGN KEY (ReviewedByAppUserId) REFERENCES acct.AppUser (AppUserId),
        CONSTRAINT FK_acct_AccountApplication_AssignedLoyalty
            FOREIGN KEY (AssignedLoyaltyTier) REFERENCES acct.LoyaltyTier (LoyaltyTierCode)
    );
END
GO

/* ---------------------------------------------------------------
   7. Address  (snapshot of contact / ship-to per application)
   --------------------------------------------------------------- */
IF OBJECT_ID('acct.Address', 'U') IS NULL
BEGIN
    CREATE TABLE acct.Address (
        AddressId     INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_acct_Address PRIMARY KEY,
        ApplicationId INT NOT NULL,
        Kind          VARCHAR(10) NOT NULL,   -- CONTACT | SHIP_TO
        FirstName     NVARCHAR(100) NULL,
        LastName      NVARCHAR(100) NULL,
        Address1      NVARCHAR(200) NULL,
        Address2      NVARCHAR(200) NULL,
        City          NVARCHAR(120) NULL,
        State         NVARCHAR(120) NULL,
        PostalCode    NVARCHAR(40)  NULL,
        Country       NVARCHAR(120) NULL,
        Phone         NVARCHAR(60)  NULL,
        CONSTRAINT CK_acct_Address_Kind CHECK (Kind IN ('CONTACT','SHIP_TO')),
        CONSTRAINT UQ_acct_Address_AppKind UNIQUE (ApplicationId, Kind),
        CONSTRAINT FK_acct_Address_Application
            FOREIGN KEY (ApplicationId) REFERENCES acct.AccountApplication (ApplicationId)
    );
END
GO

/* ---------------------------------------------------------------
   8. LoyaltyAssignment  (audited tier assignment history)
   --------------------------------------------------------------- */
IF OBJECT_ID('acct.LoyaltyAssignment', 'U') IS NULL
BEGIN
    CREATE TABLE acct.LoyaltyAssignment (
        LoyaltyAssignmentId  INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_acct_LoyaltyAssignment PRIMARY KEY,
        DistributorAccountId INT NOT NULL,
        LoyaltyTierCode      VARCHAR(20) NOT NULL,
        AssignedByAppUserId  INT NULL,
        EffectiveAt          DATETIME2(3) NOT NULL CONSTRAINT DF_acct_LoyaltyAssignment_EffectiveAt DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT FK_acct_LoyaltyAssignment_Account
            FOREIGN KEY (DistributorAccountId) REFERENCES acct.DistributorAccount (DistributorAccountId),
        CONSTRAINT FK_acct_LoyaltyAssignment_Tier
            FOREIGN KEY (LoyaltyTierCode) REFERENCES acct.LoyaltyTier (LoyaltyTierCode),
        CONSTRAINT FK_acct_LoyaltyAssignment_AssignedBy
            FOREIGN KEY (AssignedByAppUserId) REFERENCES acct.AppUser (AppUserId)
    );
END
GO

/* ---------------------------------------------------------------
   9. Notification
   --------------------------------------------------------------- */
IF OBJECT_ID('acct.Notification', 'U') IS NULL
BEGIN
    CREATE TABLE acct.Notification (
        NotificationId      INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_acct_Notification PRIMARY KEY,
        RecipientAppUserId  INT NULL,            -- direct recipient (applicant)
        RecipientRole       VARCHAR(20) NULL,    -- role-scoped recipient (e.g. admin queue)
        EventType           VARCHAR(40) NOT NULL,
        ResourceType        VARCHAR(40) NULL,
        ResourceId          VARCHAR(64) NULL,
        Message             NVARCHAR(500) NOT NULL,
        CreatedAt           DATETIME2(3) NOT NULL CONSTRAINT DF_acct_Notification_CreatedAt DEFAULT (SYSUTCDATETIME()),
        ReadAt              DATETIME2(3) NULL,
        CONSTRAINT CK_acct_Notification_Recipient
            CHECK (RecipientAppUserId IS NOT NULL OR RecipientRole IS NOT NULL),
        CONSTRAINT FK_acct_Notification_User
            FOREIGN KEY (RecipientAppUserId) REFERENCES acct.AppUser (AppUserId)
    );
END
GO

/* ---------------------------------------------------------------
   10. BrandSiteRouting  (governed metadata; DEAN->IND, FYBROC->TEL)
   --------------------------------------------------------------- */
IF OBJECT_ID('acct.BrandSiteRouting', 'U') IS NULL
BEGIN
    CREATE TABLE acct.BrandSiteRouting (
        Brand     VARCHAR(20) NOT NULL CONSTRAINT PK_acct_BrandSiteRouting PRIMARY KEY,
        SiteCode  VARCHAR(10) NOT NULL,
        IsActive  BIT NOT NULL CONSTRAINT DF_acct_BrandSiteRouting_IsActive DEFAULT (1),
        CONSTRAINT CK_acct_BrandSiteRouting_Site CHECK (SiteCode IN ('TEL','IND'))
    );
END
GO

/* ---------------------------------------------------------------
   11. EngineerMembership  (engineer user x brand/site)
   --------------------------------------------------------------- */
IF OBJECT_ID('acct.EngineerMembership', 'U') IS NULL
BEGIN
    CREATE TABLE acct.EngineerMembership (
        EngineerMembershipId INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_acct_EngineerMembership PRIMARY KEY,
        AppUserId            INT NOT NULL,
        Brand                VARCHAR(20) NOT NULL,
        SiteCode             VARCHAR(10) NOT NULL,
        CreatedAt            DATETIME2(3) NOT NULL CONSTRAINT DF_acct_EngineerMembership_CreatedAt DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT UQ_acct_EngineerMembership UNIQUE (AppUserId, Brand),
        CONSTRAINT CK_acct_EngineerMembership_Site CHECK (SiteCode IN ('TEL','IND')),
        CONSTRAINT FK_acct_EngineerMembership_User
            FOREIGN KEY (AppUserId) REFERENCES acct.AppUser (AppUserId)
    );
END
GO

/* ---------------------------------------------------------------
   12. Seed data (idempotent MERGE-style upserts)
   --------------------------------------------------------------- */
-- Loyalty tiers (D4): standard 0%, loyalty15 15%, loyalty30 30%
IF NOT EXISTS (SELECT 1 FROM acct.LoyaltyTier WHERE LoyaltyTierCode = 'standard')
    INSERT INTO acct.LoyaltyTier (LoyaltyTierCode, DisplayName, RateBp) VALUES ('standard', 'Standard', 0);
IF NOT EXISTS (SELECT 1 FROM acct.LoyaltyTier WHERE LoyaltyTierCode = 'loyalty15')
    INSERT INTO acct.LoyaltyTier (LoyaltyTierCode, DisplayName, RateBp) VALUES ('loyalty15', 'Loyalty 15%', 1500);
IF NOT EXISTS (SELECT 1 FROM acct.LoyaltyTier WHERE LoyaltyTierCode = 'loyalty30')
    INSERT INTO acct.LoyaltyTier (LoyaltyTierCode, DisplayName, RateBp) VALUES ('loyalty30', 'Loyalty 30%', 3000);
GO

-- Brand/site routing: DEAN->IND, FYBROC->TEL
IF NOT EXISTS (SELECT 1 FROM acct.BrandSiteRouting WHERE Brand = 'DEAN')
    INSERT INTO acct.BrandSiteRouting (Brand, SiteCode) VALUES ('DEAN', 'IND');
IF NOT EXISTS (SELECT 1 FROM acct.BrandSiteRouting WHERE Brand = 'FYBROC')
    INSERT INTO acct.BrandSiteRouting (Brand, SiteCode) VALUES ('FYBROC', 'TEL');
GO

PRINT 'CPQ U1: acct schema, tables, and seed data created (additive).';
GO

/* ================================================================
   STORED PROCEDURES (additive, acct.usp_*)
   All transactional / idempotent where noted. CREATE OR ALTER so the
   file is safely re-runnable.
   ================================================================ */

/* ---------------------------------------------------------------
   usp_UpsertAppUser - resolve-or-create an identity by (issuer, subject)
   Returns the AppUser row. Used by /me on every request.
   --------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE acct.usp_UpsertAppUser
    @IdpIssuer   NVARCHAR(256),
    @IdpSubject  NVARCHAR(256),
    @Email       NVARCHAR(256) = NULL,
    @DisplayName NVARCHAR(200) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    MERGE acct.AppUser AS tgt
    USING (SELECT @IdpIssuer AS IdpIssuer, @IdpSubject AS IdpSubject) AS src
        ON tgt.IdpIssuer = src.IdpIssuer AND tgt.IdpSubject = src.IdpSubject
    WHEN MATCHED THEN
        UPDATE SET
            Email       = COALESCE(@Email, tgt.Email),
            DisplayName = COALESCE(@DisplayName, tgt.DisplayName),
            LastSeenAt  = SYSUTCDATETIME()
    WHEN NOT MATCHED THEN
        INSERT (IdpIssuer, IdpSubject, Email, DisplayName, LastSeenAt)
        VALUES (@IdpIssuer, @IdpSubject, @Email, @DisplayName, SYSUTCDATETIME());

    SELECT AppUserId, IdpIssuer, IdpSubject, Email, DisplayName, IsActive, CreatedAt, LastSeenAt
    FROM acct.AppUser
    WHERE IdpIssuer = @IdpIssuer AND IdpSubject = @IdpSubject;
END;
GO

/* ---------------------------------------------------------------
   usp_GetMyAccount - distributor account + application status for a user
   Returns 0 or 1 account row (the user's owned/member account).
   --------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE acct.usp_GetMyAccount
    @AppUserId INT
AS
BEGIN
    SET NOCOUNT ON;

    SELECT TOP (1)
        da.DistributorAccountId,
        da.CompanyName,
        da.Status,
        da.LoyaltyTierCode,
        da.CreatedAt,
        app.ApplicationId,
        app.Status        AS ApplicationStatus,
        app.ReviewOutcome,
        app.ReviewReason,
        app.ReviewedAt
    FROM acct.AccountMembership m
    JOIN acct.DistributorAccount da ON da.DistributorAccountId = m.DistributorAccountId
    OUTER APPLY (
        SELECT TOP (1) a.ApplicationId, a.Status, a.ReviewOutcome, a.ReviewReason, a.ReviewedAt
        FROM acct.AccountApplication a
        WHERE a.DistributorAccountId = da.DistributorAccountId
        ORDER BY a.ApplicationId DESC
    ) app
    WHERE m.AppUserId = @AppUserId
    ORDER BY da.DistributorAccountId DESC;
END;
GO

/* ---------------------------------------------------------------
   usp_SubmitApplication - idempotent onboarding submit.
   Creates DistributorAccount (DRAFT->PENDING_APPROVAL), owner
   membership, the AccountApplication, both Address rows, and an
   admin-queue notification. Duplicate submit (same IdempotencyKey)
   returns the existing application WITHOUT creating anything new.
   --------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE acct.usp_SubmitApplication
    @AppUserId       INT,
    @IdempotencyKey  NVARCHAR(100),
    @CompanyName     NVARCHAR(200),
    -- contact
    @CFirstName NVARCHAR(100), @CLastName NVARCHAR(100),
    @CAddress1 NVARCHAR(200), @CAddress2 NVARCHAR(200),
    @CCity NVARCHAR(120), @CState NVARCHAR(120), @CPostal NVARCHAR(40),
    @CCountry NVARCHAR(120), @CPhone NVARCHAR(60),
    -- ship-to
    @SFirstName NVARCHAR(100), @SLastName NVARCHAR(100),
    @SAddress1 NVARCHAR(200), @SAddress2 NVARCHAR(200),
    @SCity NVARCHAR(120), @SState NVARCHAR(120), @SPostal NVARCHAR(40),
    @SCountry NVARCHAR(120), @SPhone NVARCHAR(60)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    -- Idempotency: if this key already produced an application, return it.
    DECLARE @ExistingAppId INT =
        (SELECT ApplicationId FROM acct.AccountApplication WHERE IdempotencyKey = @IdempotencyKey);

    IF @ExistingAppId IS NOT NULL
    BEGIN
        SELECT ApplicationId, DistributorAccountId, Status, 1 AS WasDuplicate
        FROM acct.AccountApplication WHERE ApplicationId = @ExistingAppId;
        RETURN;
    END

    BEGIN TRAN;

    DECLARE @AccountId INT;

    INSERT INTO acct.DistributorAccount (CompanyName, Status, CreatedByAppUserId)
    VALUES (@CompanyName, 'PENDING_APPROVAL', @AppUserId);
    SET @AccountId = SCOPE_IDENTITY();

    IF NOT EXISTS (SELECT 1 FROM acct.AccountMembership
                   WHERE DistributorAccountId = @AccountId AND AppUserId = @AppUserId)
        INSERT INTO acct.AccountMembership (DistributorAccountId, AppUserId, MemberRole)
        VALUES (@AccountId, @AppUserId, 'owner');

    DECLARE @AppId INT;
    INSERT INTO acct.AccountApplication
        (DistributorAccountId, SubmittedByAppUserId, Status, IdempotencyKey)
    VALUES (@AccountId, @AppUserId, 'PENDING_APPROVAL', @IdempotencyKey);
    SET @AppId = SCOPE_IDENTITY();

    INSERT INTO acct.Address
        (ApplicationId, Kind, FirstName, LastName, Address1, Address2, City, State, PostalCode, Country, Phone)
    VALUES
        (@AppId, 'CONTACT', @CFirstName, @CLastName, @CAddress1, @CAddress2, @CCity, @CState, @CPostal, @CCountry, @CPhone),
        (@AppId, 'SHIP_TO', @SFirstName, @SLastName, @SAddress1, @SAddress2, @SCity, @SState, @SPostal, @SCountry, @SPhone);

    INSERT INTO acct.Notification (RecipientRole, EventType, ResourceType, ResourceId, Message)
    VALUES ('admin', 'application_submitted', 'application', CAST(@AppId AS VARCHAR(64)),
            N'New distributor application submitted: ' + @CompanyName);

    COMMIT TRAN;

    SELECT @AppId AS ApplicationId, @AccountId AS DistributorAccountId, 'PENDING_APPROVAL' AS Status, 0 AS WasDuplicate;
END;
GO

/* ---------------------------------------------------------------
   usp_ListApplications - admin queue (optional status filter)
   --------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE acct.usp_ListApplications
    @Status VARCHAR(24) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        a.ApplicationId,
        a.DistributorAccountId,
        da.CompanyName,
        a.Status,
        a.SubmittedAt,
        su.Email        AS SubmittedByEmail,
        a.ReviewOutcome,
        a.ReviewReason,
        a.AssignedLoyaltyTier,
        a.ReviewedAt,
        da.LoyaltyTierCode
    FROM acct.AccountApplication a
    JOIN acct.DistributorAccount da ON da.DistributorAccountId = a.DistributorAccountId
    LEFT JOIN acct.AppUser su ON su.AppUserId = a.SubmittedByAppUserId
    WHERE (@Status IS NULL OR a.Status = @Status)
    ORDER BY a.ApplicationId DESC;
END;
GO

/* ---------------------------------------------------------------
   usp_GetApplication - full application detail incl. addresses
   (two result sets: application header, then addresses)
   --------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE acct.usp_GetApplication
    @ApplicationId INT
AS
BEGIN
    SET NOCOUNT ON;

    SELECT
        a.ApplicationId, a.DistributorAccountId, da.CompanyName, a.Status,
        a.SubmittedAt, su.Email AS SubmittedByEmail, su.AppUserId AS SubmittedByAppUserId,
        a.ReviewOutcome, a.ReviewReason, a.AssignedLoyaltyTier, a.ReviewedAt,
        da.LoyaltyTierCode
    FROM acct.AccountApplication a
    JOIN acct.DistributorAccount da ON da.DistributorAccountId = a.DistributorAccountId
    LEFT JOIN acct.AppUser su ON su.AppUserId = a.SubmittedByAppUserId
    WHERE a.ApplicationId = @ApplicationId;

    SELECT AddressId, Kind, FirstName, LastName, Address1, Address2,
           City, State, PostalCode, Country, Phone
    FROM acct.Address
    WHERE ApplicationId = @ApplicationId
    ORDER BY CASE Kind WHEN 'CONTACT' THEN 0 ELSE 1 END;
END;
GO

/* ---------------------------------------------------------------
   usp_ReviewApplication - admin decision.
   Outcome APPROVED | CHANGES_REQUESTED | REJECTED. On APPROVED a
   loyalty tier is assigned (defaults to 'standard' if none supplied),
   the account is moved to APPROVED, a LoyaltyAssignment row is written,
   and the applicant is notified. Transactional + re-entrant: a second
   review is rejected if the application is already terminal-approved.
   --------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE acct.usp_ReviewApplication
    @ApplicationId      INT,
    @ReviewerAppUserId  INT,
    @Outcome            VARCHAR(24),
    @Reason             NVARCHAR(1000) = NULL,
    @LoyaltyTierCode    VARCHAR(20) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF @Outcome NOT IN ('APPROVED','CHANGES_REQUESTED','REJECTED')
    BEGIN
        RAISERROR('Invalid review outcome.', 16, 1);
        RETURN;
    END

    DECLARE @AccountId INT, @CurStatus VARCHAR(24), @SubmittedBy INT;
    SELECT @AccountId = DistributorAccountId, @CurStatus = Status, @SubmittedBy = SubmittedByAppUserId
    FROM acct.AccountApplication WHERE ApplicationId = @ApplicationId;

    IF @AccountId IS NULL
    BEGIN
        RAISERROR('Application not found.', 16, 1);
        RETURN;
    END

    IF @CurStatus = 'APPROVED'
    BEGIN
        RAISERROR('Application already approved.', 16, 1);
        RETURN;
    END

    DECLARE @Tier VARCHAR(20) = COALESCE(@LoyaltyTierCode, 'standard');

    BEGIN TRAN;

    DECLARE @AppStatus VARCHAR(24) =
        CASE @Outcome WHEN 'APPROVED' THEN 'APPROVED'
                      WHEN 'REJECTED' THEN 'REJECTED'
                      ELSE 'CHANGES_REQUESTED' END;

    UPDATE acct.AccountApplication
    SET Status = @AppStatus, ReviewOutcome = @Outcome, ReviewReason = @Reason,
        AssignedLoyaltyTier = CASE WHEN @Outcome = 'APPROVED' THEN @Tier ELSE NULL END,
        ReviewedByAppUserId = @ReviewerAppUserId, ReviewedAt = SYSUTCDATETIME()
    WHERE ApplicationId = @ApplicationId;

    DECLARE @AccountStatus VARCHAR(24) =
        CASE @Outcome WHEN 'APPROVED' THEN 'APPROVED'
                      WHEN 'REJECTED' THEN 'REJECTED'
                      ELSE 'CHANGES_REQUESTED' END;

    UPDATE acct.DistributorAccount
    SET Status = @AccountStatus,
        LoyaltyTierCode = CASE WHEN @Outcome = 'APPROVED' THEN @Tier ELSE LoyaltyTierCode END,
        UpdatedAt = SYSUTCDATETIME()
    WHERE DistributorAccountId = @AccountId;

    IF @Outcome = 'APPROVED'
        INSERT INTO acct.LoyaltyAssignment (DistributorAccountId, LoyaltyTierCode, AssignedByAppUserId)
        VALUES (@AccountId, @Tier, @ReviewerAppUserId);

    DECLARE @Msg NVARCHAR(500) =
        CASE @Outcome
            WHEN 'APPROVED' THEN N'Your distributor account was approved (tier: ' + @Tier + N').'
            WHEN 'REJECTED' THEN N'Your distributor application was rejected.'
            ELSE N'Changes were requested on your distributor application.'
        END;

    INSERT INTO acct.Notification (RecipientAppUserId, EventType, ResourceType, ResourceId, Message)
    VALUES (@SubmittedBy, 'application_' + LOWER(@Outcome), 'application', CAST(@ApplicationId AS VARCHAR(64)), @Msg);

    COMMIT TRAN;

    SELECT @ApplicationId AS ApplicationId, @AccountId AS DistributorAccountId,
           @AppStatus AS Status, @Tier AS LoyaltyTierCode;
END;
GO

/* ---------------------------------------------------------------
   usp_ListNotifications / usp_MarkNotificationRead
   --------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE acct.usp_ListNotifications
    @AppUserId     INT,
    @IncludeRole   VARCHAR(20) = NULL   -- e.g. 'admin' to also pull role-scoped
AS
BEGIN
    SET NOCOUNT ON;

    SELECT NotificationId, EventType, ResourceType, ResourceId, Message, CreatedAt, ReadAt,
           RecipientAppUserId, RecipientRole
    FROM acct.Notification
    WHERE RecipientAppUserId = @AppUserId
       OR (@IncludeRole IS NOT NULL AND RecipientRole = @IncludeRole)
    ORDER BY NotificationId DESC;
END;
GO

CREATE OR ALTER PROCEDURE acct.usp_MarkNotificationRead
    @NotificationId INT,
    @AppUserId      INT,
    @IncludeRole    VARCHAR(20) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE acct.Notification
    SET ReadAt = SYSUTCDATETIME()
    WHERE NotificationId = @NotificationId
      AND ReadAt IS NULL
      AND (RecipientAppUserId = @AppUserId
           OR (@IncludeRole IS NOT NULL AND RecipientRole = @IncludeRole));

    SELECT @@ROWCOUNT AS Updated;
END;
GO

PRINT 'CPQ U1: acct stored procedures created (additive).';
GO

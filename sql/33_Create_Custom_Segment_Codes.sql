/* ================================================================
   CPQ ADJUSTMENTS A4 - GOVERNED PER-GROUPING CUSTOM-CODE MIRROR
   ----------------------------------------------------------------
   ADDITIVE ONLY. Creates a SEPARATE custom-code registry that MIRRORS
   (never edits) the authoritative numbering. It does NOT modify
   stg.SegmentCombinationImport, cfg.usp_AssembleConfiguredProduct,
   dean_identifier, or any real PN. A minted custom code is a parallel
   representation engineering can attach to a grouping's custom spec and
   display ALONGSIDE the authoritative PN.

   Collision-safe "backward read": a new custom code is minted as the
   next base-36 value AFTER the current MAX across BOTH the real
   numbering (stg.SegmentCombinationImport SegmentValue for that family +
   grouping) AND the existing custom codes. Because every grouping's
   SegmentValue is fixed-width base-36 (0-9A-Z), lexical MAX == numeric
   MAX, so customs always sit strictly above every real code and a future
   authoritative reload cannot silently collide (the audit fails closed if
   it ever does). Reuse is by spec-key, FAMILY-WIDE.

   Fybroc frozen: this only adds a new cfg table + procs/functions; the
   Fybroc (and Dean) real numbering is untouched.
   ================================================================ */

SET NOCOUNT ON;
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

USE PumpConfiguratorDB;
GO

/* ---------------------------------------------------------------
   base-36 decode / encode (mirror of docs/style.md encode(n,width))
   --------------------------------------------------------------- */
CREATE OR ALTER FUNCTION cfg.fn_Base36Decode(@code VARCHAR(16))
RETURNS BIGINT
AS
BEGIN
    IF @code IS NULL OR LEN(@code) = 0 RETURN NULL;
    DECLARE @digits CHAR(36) = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
    DECLARE @n BIGINT = 0, @i INT = 1, @c CHAR(1), @v INT;
    SET @code = UPPER(@code);
    WHILE @i <= LEN(@code)
    BEGIN
        SET @c = SUBSTRING(@code, @i, 1);
        SET @v = CHARINDEX(@c, @digits) - 1;     -- 0-based value
        IF @v < 0 RETURN NULL;                    -- non base-36 char
        SET @n = @n * 36 + @v;
        SET @i = @i + 1;
    END
    RETURN @n;
END;
GO

CREATE OR ALTER FUNCTION cfg.fn_Base36Encode(@n BIGINT, @width INT)
RETURNS VARCHAR(16)
AS
BEGIN
    IF @n IS NULL OR @n < 0 RETURN NULL;
    DECLARE @digits CHAR(36) = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
    DECLARE @s VARCHAR(16) = '';
    DECLARE @m BIGINT = @n;
    IF @m = 0 SET @s = '0';
    WHILE @m > 0
    BEGIN
        SET @s = SUBSTRING(@digits, (@m % 36) + 1, 1) + @s;
        SET @m = @m / 36;
    END
    IF LEN(@s) > @width RETURN NULL;              -- overflow -> caller fails closed
    RETURN RIGHT(REPLICATE('0', @width) + @s, @width);
END;
GO

/* ---------------------------------------------------------------
   cfg.CustomSegmentCode - one row per minted custom code, per family +
   grouping (SegmentCode) + spec-key. SpecKey is the stable hash of the
   engineer's custom spec for that grouping => family-wide reuse.
   --------------------------------------------------------------- */
IF OBJECT_ID('cfg.CustomSegmentCode', 'U') IS NULL
BEGIN
    CREATE TABLE cfg.CustomSegmentCode (
        CustomSegmentCodeId INT IDENTITY(1,1) NOT NULL
            CONSTRAINT PK_cfg_CustomSegmentCode PRIMARY KEY,
        FamilyCode     VARCHAR(20) NOT NULL,
        SegmentCode    VARCHAR(40) NOT NULL,   -- grouping, e.g. WET_END_OPTIONS
        Width          INT NOT NULL,
        SpecKey        VARCHAR(64) NOT NULL,   -- SHA-256 hex of the custom spec text
        SegmentValue   VARCHAR(16) NOT NULL,   -- the minted base-36 code (fixed width)
        SpecText       NVARCHAR(2000) NULL,
        SelectionsJson NVARCHAR(MAX) NULL,
        CreatedByAppUserId INT NULL,
        FirstSeenAt    DATETIME2(3) NOT NULL
            CONSTRAINT DF_cfg_CustomSegmentCode_At DEFAULT (SYSUTCDATETIME()),
        -- family-wide reuse key: one code per (family, grouping, spec).
        CONSTRAINT UQ_cfg_CustomSegmentCode_Spec UNIQUE (FamilyCode, SegmentCode, SpecKey),
        -- a minted code is unique within its (family, grouping) space.
        CONSTRAINT UQ_cfg_CustomSegmentCode_Value UNIQUE (FamilyCode, SegmentCode, SegmentValue)
    );
END
GO

/* ---------------------------------------------------------------
   usp_GetOrCreateCustomSegmentCode - reuse by spec-key (family-wide),
   else mint next-after-max(real UNION custom) at the grouping width.
   Serializable + app lock so two callers can't mint the same value.
   Fails closed (THROW) if the width space is exhausted.
   --------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE cfg.usp_GetOrCreateCustomSegmentCode
    @FamilyCode     VARCHAR(20),
    @SegmentCode    VARCHAR(40),
    @SpecKey        VARCHAR(64),
    @SpecText       NVARCHAR(2000) = NULL,
    @SelectionsJson NVARCHAR(MAX) = NULL,
    @CreatedByAppUserId INT = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    -- Reuse (family-wide) if this spec already minted a code for the grouping.
    DECLARE @existing VARCHAR(16) = (
        SELECT SegmentValue FROM cfg.CustomSegmentCode
        WHERE FamilyCode = @FamilyCode AND SegmentCode = @SegmentCode AND SpecKey = @SpecKey);
    IF @existing IS NOT NULL
    BEGIN
        SELECT @existing AS SegmentValue, CAST(1 AS BIT) AS WasExisting, @SegmentCode AS SegmentCode;
        RETURN;
    END

    -- Width for this grouping (authoritative: the real numbering's ExpectedWidth).
    DECLARE @width INT = (
        SELECT TOP (1) ExpectedWidth FROM stg.SegmentCombinationImport
        WHERE FamilyCode = @FamilyCode AND SegmentCode = @SegmentCode AND ExpectedWidth IS NOT NULL);
    IF @width IS NULL
    BEGIN
        RAISERROR('No authoritative width for family %s grouping %s; cannot mint a custom code.', 16, 1,
                  @FamilyCode, @SegmentCode);
        RETURN;
    END

    BEGIN TRAN;
    -- Serialize minting for this (family, grouping).
    DECLARE @lock VARCHAR(255) = CONCAT('customseg:', @FamilyCode, ':', @SegmentCode);
    DECLARE @rc INT;
    EXEC @rc = sp_getapplock @Resource = @lock, @LockMode = 'Exclusive',
                             @LockOwner = 'Transaction', @LockTimeout = 15000;
    IF @rc < 0
    BEGIN
        ROLLBACK TRAN;
        RAISERROR('Could not acquire mint lock for %s.', 16, 1, @lock);
        RETURN;
    END

    -- Re-check reuse under the lock (another caller may have just minted it).
    SET @existing = (
        SELECT SegmentValue FROM cfg.CustomSegmentCode
        WHERE FamilyCode = @FamilyCode AND SegmentCode = @SegmentCode AND SpecKey = @SpecKey);
    IF @existing IS NOT NULL
    BEGIN
        COMMIT TRAN;
        SELECT @existing AS SegmentValue, CAST(1 AS BIT) AS WasExisting, @SegmentCode AS SegmentCode;
        RETURN;
    END

    -- Backward read: numeric max across REAL (fixed-width base-36 => lexical MAX
    -- == numeric MAX) and the custom table.
    DECLARE @realMaxCode VARCHAR(16) = (
        SELECT MAX(SegmentValue) FROM stg.SegmentCombinationImport
        WHERE FamilyCode = @FamilyCode AND SegmentCode = @SegmentCode
          AND LEN(SegmentValue) = @width);
    DECLARE @custMaxCode VARCHAR(16) = (
        SELECT MAX(SegmentValue) FROM cfg.CustomSegmentCode
        WHERE FamilyCode = @FamilyCode AND SegmentCode = @SegmentCode);

    DECLARE @maxN BIGINT = (
        SELECT MAX(v) FROM (VALUES
            (cfg.fn_Base36Decode(@realMaxCode)),
            (cfg.fn_Base36Decode(@custMaxCode))
        ) AS t(v));
    IF @maxN IS NULL SET @maxN = -1;   -- empty space -> first code is 0

    DECLARE @nextN BIGINT = @maxN + 1;
    DECLARE @code VARCHAR(16) = cfg.fn_Base36Encode(@nextN, @width);
    IF @code IS NULL
    BEGIN
        ROLLBACK TRAN;
        RAISERROR('Custom code space exhausted for %s grouping %s at width %d.', 16, 1,
                  @FamilyCode, @SegmentCode, @width);
        RETURN;
    END

    INSERT INTO cfg.CustomSegmentCode
        (FamilyCode, SegmentCode, Width, SpecKey, SegmentValue, SpecText,
         SelectionsJson, CreatedByAppUserId)
    VALUES (@FamilyCode, @SegmentCode, @width, @SpecKey, @code, @SpecText,
            @SelectionsJson, @CreatedByAppUserId);
    COMMIT TRAN;

    SELECT @code AS SegmentValue, CAST(0 AS BIT) AS WasExisting, @SegmentCode AS SegmentCode;
END;
GO

/* ---------------------------------------------------------------
   usp_ListCustomSegmentCodes - the custom-code library (per family).
   --------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE cfg.usp_ListCustomSegmentCodes
    @FamilyCode  VARCHAR(20) = NULL,
    @SegmentCode VARCHAR(40) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SELECT CustomSegmentCodeId, FamilyCode, SegmentCode, Width, SpecKey,
           SegmentValue, SpecText, FirstSeenAt
    FROM cfg.CustomSegmentCode
    WHERE (@FamilyCode IS NULL OR FamilyCode = @FamilyCode)
      AND (@SegmentCode IS NULL OR SegmentCode = @SegmentCode)
    ORDER BY FamilyCode, SegmentCode, SegmentValue;
END;
GO

PRINT 'CPQ A4: cfg.CustomSegmentCode + base-36 fns + mint/list procs created (additive).';
GO

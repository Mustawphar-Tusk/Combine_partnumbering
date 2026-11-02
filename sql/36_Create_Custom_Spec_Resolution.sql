/* ================================================================
   DEAN REVISION D-R2b - CUSTOM-SPEC RESOLUTION (engineer -> reusable code)
   ----------------------------------------------------------------
   ADDITIVE ONLY. Extends quote.QuoteLineCustomization (A2) with the
   RESOLVED result of an engineer's custom spec, and adds a proc that
   mints-or-reuses the governed per-grouping custom code (A4
   cfg.CustomSegmentCode) and links it back to the customization row.

   Lifecycle:
     1. Distributor/engineer selects a grouping's Custom option -> a
        quote.QuoteLineCustomization row (A2) captures the spec request;
        the line is unresolved -> forces engineering review (A3/A5).
     2. Engineer resolves the spec -> usp_ResolveCustomSpec computes/uses
        the spec-key, mints-or-reuses the code via
        cfg.usp_GetOrCreateCustomSegmentCode (family-wide reuse by spec),
        and stamps ResolvedCustomCode/ResolvedSpecKey/ResolvedBy/ResolvedAt
        on the customization row.
     3. The resolved code occupies the grouping's PN segment slot at its
        native width (D-R2a) for this + any identical custom build (reuse).

   No existing object altered destructively; the A2 draft-only CRUD and
   the A4 mirror are unchanged. Fybroc untouched.
   ================================================================ */

SET NOCOUNT ON;
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

USE PumpConfiguratorDB;
GO

/* --- additive columns on quote.QuoteLineCustomization (A2) --- */
IF COL_LENGTH('quote.QuoteLineCustomization', 'ResolvedCustomCode') IS NULL
    ALTER TABLE quote.QuoteLineCustomization ADD ResolvedCustomCode VARCHAR(16) NULL;
GO
IF COL_LENGTH('quote.QuoteLineCustomization', 'ResolvedSpecKey') IS NULL
    ALTER TABLE quote.QuoteLineCustomization ADD ResolvedSpecKey VARCHAR(64) NULL;
GO
IF COL_LENGTH('quote.QuoteLineCustomization', 'ResolvedByAppUserId') IS NULL
    ALTER TABLE quote.QuoteLineCustomization ADD ResolvedByAppUserId INT NULL;
GO
IF COL_LENGTH('quote.QuoteLineCustomization', 'ResolvedAt') IS NULL
    ALTER TABLE quote.QuoteLineCustomization ADD ResolvedAt DATETIME2(3) NULL;
GO

/* ---------------------------------------------------------------
   usp_ResolveCustomSpec - engineer resolves one grouping's custom spec.
   Mints-or-reuses the governed custom code (family-wide reuse by spec)
   and stamps the result onto the customization row. @SpecKey is computed
   by the API (SHA-256 of the normalized spec text, UPPER hex) so it
   matches the A4 mint endpoint exactly (shared reuse key).
   --------------------------------------------------------------- */
CREATE OR ALTER PROCEDURE cfg.usp_ResolveCustomSpec
    @FamilyCode      VARCHAR(20),
    @SegmentCode     VARCHAR(40),
    @SpecKey         VARCHAR(64),
    @SpecText        NVARCHAR(2000),
    @SelectionsJson  NVARCHAR(MAX) = NULL,
    @CustomizationId BIGINT = NULL,       -- optional: link back to the A2 request row
    @AppUserId       INT = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    -- Mint-or-reuse the governed per-grouping custom code (A4). This RAISERRORs
    -- with 'exhausted' / 'no authoritative width' which the API maps to 409/404.
    DECLARE @mint TABLE (SegmentValue VARCHAR(16), WasExisting BIT, SegmentCode VARCHAR(40));
    INSERT INTO @mint
    EXEC cfg.usp_GetOrCreateCustomSegmentCode
        @FamilyCode = @FamilyCode, @SegmentCode = @SegmentCode, @SpecKey = @SpecKey,
        @SpecText = @SpecText, @SelectionsJson = @SelectionsJson,
        @CreatedByAppUserId = @AppUserId;

    DECLARE @code VARCHAR(16), @was BIT;
    SELECT @code = SegmentValue, @was = WasExisting FROM @mint;

    -- Stamp the resolution onto the customization row (if one was supplied).
    IF @CustomizationId IS NOT NULL
        UPDATE quote.QuoteLineCustomization
        SET ResolvedCustomCode = @code,
            ResolvedSpecKey = @SpecKey,
            ResolvedByAppUserId = @AppUserId,
            ResolvedAt = SYSUTCDATETIME()
        WHERE CustomizationId = @CustomizationId;

    SELECT @code AS ResolvedCustomCode, @was AS WasExisting,
           @SegmentCode AS SegmentCode, @SpecKey AS SpecKey;
END;
GO

PRINT 'DEAN D-R2b: QuoteLineCustomization resolved-columns + cfg.usp_ResolveCustomSpec created (additive).';
GO

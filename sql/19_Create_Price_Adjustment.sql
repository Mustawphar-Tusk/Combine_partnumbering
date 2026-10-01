/* ================================================================
   PRICE ADJUSTMENT — targeted percentage price updates
   ----------------------------------------------------------------
   A single stored procedure, price.usp_ApplyPriceAdjustment, applies a
   PERCENT change to price.PriceRule.Amount for the CURRENT published
   price book version, scoped by:

       @ScopeType = 'ALL_FAMILIES'  -> every family's current price book
                    'FAMILY'        -> one family (all its series/components)
                    'SERIES'        -> one family + one series

   and optionally narrowed to a single child component (@ComponentCode,
   e.g. SHAFT_MATERIAL, FLANGE_TYPE, CASING_DRAINS, IMPELLER_TRIM,
   PUMP_MATERIAL_ADDER, BASE_PUMP, SEAL ...). @ComponentCode = NULL means
   the whole pump (every priced component under the scope).

   Model: a pump SERIES (Fybroc 1500, Dean PH2110, ...) is the "parent";
   its priced COMPONENTS are the "children". Updating a FAMILY/SERIES scope
   with @ComponentCode NULL cascades to all child component rows.

   Every apply is fully audited in price.PriceAdjustment (header) +
   price.PriceAdjustmentRow (per-rule old/new amount), so a change is
   traceable and reversible (apply the inverse percentage, or restore from
   the row log).

   @DryRun = 1 (default) PREVIEWS: returns the affected rows + totals and
   writes NOTHING. @DryRun = 0 applies the change in a transaction.

   Family isolation: FAMILY / SERIES scopes touch ONLY that family's price
   book. ALL_FAMILIES is the only scope that spans families (by design).

   Idempotent deploy (CREATE OR ALTER / IF NOT EXISTS). No row is changed
   at deploy time.
   ================================================================ */

SET XACT_ABORT ON;
GO

/* ---------------------------------------------------------------
   1. AUDIT TABLES
   --------------------------------------------------------------- */

IF OBJECT_ID('price.PriceAdjustment', 'U') IS NULL
BEGIN
    CREATE TABLE price.PriceAdjustment
    (
        PriceAdjustmentId   bigint IDENTITY(1,1) NOT NULL
            CONSTRAINT PK_PriceAdjustment PRIMARY KEY,
        ScopeType           varchar(20)  NOT NULL,
        PumpFamilyId        int          NULL
            CONSTRAINT FK_PriceAdjustment_Family REFERENCES cfg.PumpFamily(PumpFamilyId),
        FamilyCode          varchar(50)  NULL,
        SeriesCode          varchar(100) NULL,
        ComponentCode       varchar(100) NULL,          -- NULL = all components
        PercentChange       decimal(9,4) NOT NULL,       -- e.g. 5.0 = +5%, -2.5 = -2.5%
        RowsAffected        int          NOT NULL,
        AmountBeforeTotal   decimal(19,4) NOT NULL,
        AmountAfterTotal    decimal(19,4) NOT NULL,
        Reason              nvarchar(500) NULL,
        AppliedBy           nvarchar(200) NULL,
        AppliedAt           datetime2(7) NOT NULL
            CONSTRAINT DF_PriceAdjustment_AppliedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT CK_PriceAdjustment_Scope
            CHECK (ScopeType IN ('ALL_FAMILIES', 'FAMILY', 'SERIES'))
    );
END;
GO

IF OBJECT_ID('price.PriceAdjustmentRow', 'U') IS NULL
BEGIN
    CREATE TABLE price.PriceAdjustmentRow
    (
        PriceAdjustmentRowId bigint IDENTITY(1,1) NOT NULL
            CONSTRAINT PK_PriceAdjustmentRow PRIMARY KEY,
        PriceAdjustmentId    bigint NOT NULL
            CONSTRAINT FK_PriceAdjustmentRow_Hdr REFERENCES price.PriceAdjustment(PriceAdjustmentId),
        PriceRuleId          bigint NOT NULL
            CONSTRAINT FK_PriceAdjustmentRow_Rule REFERENCES price.PriceRule(PriceRuleId),
        AmountBefore         decimal(19,4) NOT NULL,
        AmountAfter          decimal(19,4) NOT NULL
    );
    CREATE INDEX IX_PriceAdjustmentRow_Hdr
        ON price.PriceAdjustmentRow(PriceAdjustmentId);
END;
GO


/* ---------------------------------------------------------------
   2. THE PROCEDURE
   --------------------------------------------------------------- */

CREATE OR ALTER PROCEDURE price.usp_ApplyPriceAdjustment
    @ScopeType      varchar(20),              -- ALL_FAMILIES | FAMILY | SERIES
    @PercentChange  decimal(9,4),             -- +5 => +5%, -2.5 => -2.5%
    @FamilyCode     varchar(50)  = NULL,      -- required for FAMILY/SERIES
    @SeriesCode     varchar(100) = NULL,      -- required for SERIES
    @ComponentCode  varchar(100) = NULL,      -- NULL = all components
    @Reason         nvarchar(500) = NULL,
    @AppliedBy      nvarchar(200) = NULL,
    @DryRun         bit = 1                   -- default: PREVIEW ONLY
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    ---- validate -------------------------------------------------
    SET @ScopeType = UPPER(LTRIM(RTRIM(@ScopeType)));
    IF @ScopeType NOT IN ('ALL_FAMILIES', 'FAMILY', 'SERIES')
        THROW 52001, 'ScopeType must be ALL_FAMILIES, FAMILY, or SERIES.', 1;

    IF @PercentChange IS NULL
        THROW 52002, 'PercentChange is required (e.g. 5 for +5%).', 1;
    -- Guard against a fat-finger that would zero/negate prices.
    IF @PercentChange <= -100
        THROW 52003, 'PercentChange <= -100% is not allowed (would zero/negate prices).', 1;

    IF @ScopeType IN ('FAMILY', 'SERIES') AND @FamilyCode IS NULL
        THROW 52004, 'FamilyCode is required for FAMILY and SERIES scope.', 1;
    IF @ScopeType = 'SERIES' AND @SeriesCode IS NULL
        THROW 52005, 'SeriesCode is required for SERIES scope.', 1;

    DECLARE @PumpFamilyId int = NULL;
    IF @FamilyCode IS NOT NULL
    BEGIN
        SET @FamilyCode = UPPER(LTRIM(RTRIM(@FamilyCode)));
        SELECT @PumpFamilyId = PumpFamilyId
        FROM cfg.PumpFamily
        WHERE FamilyCode = @FamilyCode AND IsActive = 1;
        IF @PumpFamilyId IS NULL
            THROW 52006, 'Active pump family not found for the given FamilyCode.', 1;
    END;

    DECLARE @factor decimal(19,10) = 1.0 + (@PercentChange / 100.0);

    ---- resolve the target PriceRule set -------------------------
    -- Only the CURRENT published version of each in-scope family's price
    -- book is touched. SeriesCode / ComponentCode narrow within that.
    IF OBJECT_ID('tempdb..#Target') IS NOT NULL DROP TABLE #Target;
    SELECT
        pr.PriceRuleId,
        pr.Amount AS AmountBefore,
        CAST(ROUND(pr.Amount * @factor, 4) AS decimal(19,4)) AS AmountAfter
    INTO #Target
    FROM price.PriceRule pr
    JOIN price.PriceBookVersion pbv
        ON pbv.PriceBookVersionId = pr.PriceBookVersionId AND pbv.IsCurrent = 1
    JOIN price.PriceBook pb
        ON pb.PriceBookId = pbv.PriceBookId AND pb.IsActive = 1
    JOIN cfg.PumpFamily pf
        ON pf.PumpFamilyId = pb.PumpFamilyId AND pf.IsActive = 1
    WHERE pr.IsActive = 1
      -- family scope (ALL_FAMILIES ignores family)
      AND (@ScopeType = 'ALL_FAMILIES' OR pb.PumpFamilyId = @PumpFamilyId)
      -- series scope (SERIES only). SeriesCode on PriceRule may carry a
      -- qualifier like '1530 (ANSI)', so match exact OR prefix 'code%'.
      AND (@ScopeType <> 'SERIES'
           OR pr.SeriesCode = @SeriesCode
           OR pr.SeriesCode LIKE @SeriesCode + ' %'
           OR pr.SeriesCode LIKE @SeriesCode + '(%')
      -- optional component (child) narrowing
      AND (@ComponentCode IS NULL OR pr.ComponentCode = @ComponentCode);

    DECLARE @rows int, @beforeTotal decimal(19,4), @afterTotal decimal(19,4);
    SELECT @rows = COUNT(*),
           @beforeTotal = ISNULL(SUM(AmountBefore), 0),
           @afterTotal  = ISNULL(SUM(AmountAfter), 0)
    FROM #Target;

    IF @rows = 0
        THROW 52007, 'No price rules match the requested scope (nothing to adjust).', 1;

    ---- DRY RUN: preview + leave DB untouched --------------------
    IF @DryRun = 1
    BEGIN
        SELECT
            CAST(0 AS bit)        AS Applied,
            @ScopeType            AS ScopeType,
            @FamilyCode           AS FamilyCode,
            @SeriesCode           AS SeriesCode,
            @ComponentCode        AS ComponentCode,
            @PercentChange        AS PercentChange,
            @rows                 AS RowsAffected,
            @beforeTotal          AS AmountBeforeTotal,
            @afterTotal           AS AmountAfterTotal;
        -- per-component breakdown so a reviewer can sanity-check the target
        SELECT pr.ComponentCode, pr.SeriesCode,
               COUNT(*) AS Rows,
               SUM(t.AmountBefore) AS BeforeTotal,
               SUM(t.AmountAfter)  AS AfterTotal
        FROM #Target t
        JOIN price.PriceRule pr ON pr.PriceRuleId = t.PriceRuleId
        GROUP BY pr.ComponentCode, pr.SeriesCode
        ORDER BY pr.ComponentCode, pr.SeriesCode;
        RETURN;
    END;

    ---- APPLY: transactional update + full audit -----------------
    BEGIN TRAN;

        INSERT INTO price.PriceAdjustment
            (ScopeType, PumpFamilyId, FamilyCode, SeriesCode, ComponentCode,
             PercentChange, RowsAffected, AmountBeforeTotal, AmountAfterTotal,
             Reason, AppliedBy)
        VALUES
            (@ScopeType, @PumpFamilyId, @FamilyCode, @SeriesCode, @ComponentCode,
             @PercentChange, @rows, @beforeTotal, @afterTotal,
             @Reason, @AppliedBy);

        DECLARE @adjId bigint = CONVERT(bigint, SCOPE_IDENTITY());

        INSERT INTO price.PriceAdjustmentRow
            (PriceAdjustmentId, PriceRuleId, AmountBefore, AmountAfter)
        SELECT @adjId, PriceRuleId, AmountBefore, AmountAfter
        FROM #Target;

        UPDATE pr
        SET pr.Amount = t.AmountAfter
        FROM price.PriceRule pr
        JOIN #Target t ON t.PriceRuleId = pr.PriceRuleId;

    COMMIT TRAN;

    SELECT
        CAST(1 AS bit)   AS Applied,
        @adjId           AS PriceAdjustmentId,
        @ScopeType       AS ScopeType,
        @FamilyCode      AS FamilyCode,
        @SeriesCode      AS SeriesCode,
        @ComponentCode   AS ComponentCode,
        @PercentChange   AS PercentChange,
        @rows            AS RowsAffected,
        @beforeTotal     AS AmountBeforeTotal,
        @afterTotal      AS AmountAfterTotal;
END;
GO

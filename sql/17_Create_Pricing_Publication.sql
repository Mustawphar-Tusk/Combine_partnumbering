SET ANSI_NULLS ON;
GO
SET QUOTED_IDENTIFIER ON;
GO
SET ANSI_PADDING ON;
GO
SET ANSI_WARNINGS ON;
GO
SET ARITHABORT ON;
GO
SET CONCAT_NULL_YIELDS_NULL ON;
GO
SET NUMERIC_ROUNDABORT OFF;
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

/* ================================================================
   M021.2 - SHARED VERSIONED PRICING PUBLICATION
   ----------------------------------------------------------------
   Reuses:
       price.PriceBook
       price.PriceBookVersion
       price.PriceRule
       price.PriceCondition

   Adds:
       stg.PricingExtract
       pricing status + lineage columns
       useful indexes
       price.usp_PublishPricingFromStaging
       price.vw_CurrentPricingRules
   ================================================================ */


/* ================================================================
   1. STAGING TABLE
   ================================================================ */

IF OBJECT_ID('stg.PricingExtract', 'U') IS NULL
BEGIN
    CREATE TABLE stg.PricingExtract
    (
        PricingExtractId      bigint IDENTITY(1,1) NOT NULL
            CONSTRAINT PK_PricingExtract PRIMARY KEY,

        LoadBatchId           uniqueidentifier NOT NULL,

        FamilyCode            varchar(30) NOT NULL,
        ComponentCode         varchar(100) NOT NULL,
        SeriesCode            varchar(100) NULL,
        SourceSeriesCode      varchar(100) NULL,

        SizeValue             nvarchar(300) NULL,
        SourceSizeValue       nvarchar(300) NULL,

        OptionFieldCode       varchar(100) NULL,
        OptionValue           nvarchar(1000) NULL,
        SourceOptionValue     nvarchar(1000) NULL,
        ConditionsJson        nvarchar(max) NULL,

        Amount                decimal(19,4) NULL,
        PricingStatus         varchar(30) NOT NULL,
        SourcePriceValue      nvarchar(1000) NULL,

        CurrencyCode          char(3) NOT NULL,

        SourceWorkbook        nvarchar(500) NULL,
        SourceWorksheet       nvarchar(300) NULL,
        SourceTable           nvarchar(300) NULL,
        SourceCell            varchar(50) NULL,

        ExtractedAt           datetime2(7) NOT NULL
            CONSTRAINT DF_PricingExtract_ExtractedAt
            DEFAULT SYSUTCDATETIME(),

        CONSTRAINT CK_PricingExtract_Status
            CHECK
            (
                PricingStatus IN
                (
                    'found',
                    'call_for_price'
                )
            ),

        CONSTRAINT CK_PricingExtract_AmountStatus
            CHECK
            (
                   (PricingStatus = 'found'
                    AND Amount IS NOT NULL
                    AND Amount >= 0)

                OR (PricingStatus = 'call_for_price'
                    AND Amount IS NULL)
            )
    );
END;
GO


IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes
    WHERE
        object_id = OBJECT_ID('stg.PricingExtract')
        AND name = 'IX_PricingExtract_LoadBatch'
)
BEGIN
    CREATE INDEX IX_PricingExtract_LoadBatch
        ON stg.PricingExtract
        (
            LoadBatchId,
            FamilyCode,
            ComponentCode,
            SeriesCode
        );
END;
GO



IF COL_LENGTH(
    'stg.PricingExtract',
    'SourceSeriesCode'
) IS NULL
BEGIN
    ALTER TABLE stg.PricingExtract
        ADD SourceSeriesCode varchar(100) NULL;
END;
GO


IF COL_LENGTH(
    'stg.PricingExtract',
    'ConditionsJson'
) IS NULL
BEGIN
    ALTER TABLE stg.PricingExtract
        ADD ConditionsJson nvarchar(max) NULL;
END;
GO


IF NOT EXISTS
(
    SELECT 1
    FROM sys.check_constraints
    WHERE
        parent_object_id = OBJECT_ID('stg.PricingExtract')
        AND name = 'CK_PricingExtract_ConditionsJson'
)
BEGIN
    ALTER TABLE stg.PricingExtract
        ADD CONSTRAINT CK_PricingExtract_ConditionsJson
        CHECK
        (
            ConditionsJson IS NULL
            OR ISJSON(ConditionsJson) = 1
        );
END;
GO


/* ================================================================
   2. EXTEND price.PriceRule
   ================================================================ */

IF COL_LENGTH(
    'price.PriceRule',
    'ComponentCode'
) IS NULL
BEGIN
    ALTER TABLE price.PriceRule
        ADD ComponentCode varchar(100) NULL;
END;
GO


IF COL_LENGTH(
    'price.PriceRule',
    'SeriesCode'
) IS NULL
BEGIN
    ALTER TABLE price.PriceRule
        ADD SeriesCode varchar(100) NULL;
END;
GO


IF COL_LENGTH(
    'price.PriceRule',
    'PricingStatus'
) IS NULL
BEGIN
    ALTER TABLE price.PriceRule
        ADD PricingStatus varchar(30) NOT NULL
            CONSTRAINT DF_PriceRule_PricingStatus
            DEFAULT ('found')
            WITH VALUES;
END;
GO


IF COL_LENGTH(
    'price.PriceRule',
    'SourceSeriesCode'
) IS NULL
BEGIN
    ALTER TABLE price.PriceRule
        ADD SourceSeriesCode varchar(100) NULL;
END;
GO


IF COL_LENGTH(
    'price.PriceRule',
    'SourceSizeValue'
) IS NULL
BEGIN
    ALTER TABLE price.PriceRule
        ADD SourceSizeValue nvarchar(300) NULL;
END;
GO


IF COL_LENGTH(
    'price.PriceRule',
    'SourceOptionValue'
) IS NULL
BEGIN
    ALTER TABLE price.PriceRule
        ADD SourceOptionValue nvarchar(1000) NULL;
END;
GO


IF COL_LENGTH(
    'price.PriceRule',
    'SourcePriceValue'
) IS NULL
BEGIN
    ALTER TABLE price.PriceRule
        ADD SourcePriceValue nvarchar(1000) NULL;
END;
GO


IF COL_LENGTH(
    'price.PriceRule',
    'SourceWorksheet'
) IS NULL
BEGIN
    ALTER TABLE price.PriceRule
        ADD SourceWorksheet nvarchar(300) NULL;
END;
GO


IF COL_LENGTH(
    'price.PriceRule',
    'SourceTable'
) IS NULL
BEGIN
    ALTER TABLE price.PriceRule
        ADD SourceTable nvarchar(300) NULL;
END;
GO


IF COL_LENGTH(
    'price.PriceRule',
    'SourceCell'
) IS NULL
BEGIN
    ALTER TABLE price.PriceRule
        ADD SourceCell varchar(50) NULL;
END;
GO


/* ================================================================
   3. STATUS CONSTRAINT ON RUNTIME RULES
   ================================================================ */

IF NOT EXISTS
(
    SELECT 1
    FROM sys.check_constraints
    WHERE
        parent_object_id =
            OBJECT_ID('price.PriceRule')
        AND name = 'CK_PriceRule_PricingStatus'
)
BEGIN
    ALTER TABLE price.PriceRule
        ADD CONSTRAINT CK_PriceRule_PricingStatus
        CHECK
        (
            PricingStatus IN
            (
                'found',
                'call_for_price'
            )
        );
END;
GO


/* ================================================================
   4. RUNTIME INDEXES
   ================================================================ */

IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes
    WHERE
        object_id =
            OBJECT_ID('price.PriceRule')
        AND name =
            'IX_PriceRule_Version_Component_Series'
)
BEGIN
    CREATE INDEX
        IX_PriceRule_Version_Component_Series
    ON price.PriceRule
    (
        PriceBookVersionId,
        ComponentCode,
        SeriesCode,
        IsActive,
        Priority
    )
    INCLUDE
    (
        PricingStatus,
        Amount,
        RuleCode
    );
END;
GO


IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes
    WHERE
        object_id =
            OBJECT_ID('price.PriceCondition')
        AND name =
            'IX_PriceCondition_Rule_Field_Value'
)
BEGIN
    CREATE INDEX
        IX_PriceCondition_Rule_Field_Value
    ON price.PriceCondition
    (
        PriceRuleId,
        FieldCode,
        ComparisonValue
    )
    INCLUDE
    (
        SequenceNo,
        ComparisonOperator
    );
END;
GO


/* ================================================================
   5. CURRENT PRICING VIEW
   ================================================================ */

CREATE OR ALTER VIEW price.vw_CurrentPricingRules
AS
SELECT
    pf.PumpFamilyId,
    pf.FamilyCode,

    pb.PriceBookId,
    pb.PriceBookCode,
    pb.PriceBookName,
    pb.CurrencyCode,

    pbv.PriceBookVersionId,
    pbv.VersionCode,
    pbv.EffectiveFrom,
    pbv.EffectiveTo,
    pbv.SourceWorkbook,

    pr.PriceRuleId,
    pr.RuleCode,
    pr.RuleName,
    pr.RuleType,
    pr.ComponentCode,
    pr.SeriesCode,
    pr.SourceSeriesCode,
    pr.Priority,
    pr.Amount,
    pr.PricingStatus,
    pr.IsActive,

    pr.SourceSizeValue,
    pr.SourceOptionValue,
    pr.SourcePriceValue,
    pr.SourceWorksheet,
    pr.SourceTable,
    pr.SourceCell

FROM price.PriceBook pb

INNER JOIN cfg.PumpFamily pf
    ON pf.PumpFamilyId =
       pb.PumpFamilyId

INNER JOIN price.PriceBookVersion pbv
    ON pbv.PriceBookId =
       pb.PriceBookId

INNER JOIN price.PriceRule pr
    ON pr.PriceBookVersionId =
       pbv.PriceBookVersionId

WHERE
    pf.IsActive = 1
    AND pb.IsActive = 1
    AND pbv.IsCurrent = 1
    AND pr.IsActive = 1;
GO


/* ================================================================
   6. PUBLICATION PROCEDURE
   ================================================================ */

CREATE OR ALTER PROCEDURE
    price.usp_PublishPricingFromStaging

    @LoadBatchId     uniqueidentifier,
    @FamilyCode      varchar(30),
    @VersionCode     varchar(50),
    @EffectiveFrom   date,
    @SourceWorkbook  nvarchar(500) = NULL

AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE
        @PumpFamilyId       int,
        @PriceBookId        int,
        @PriceBookVersionId int,
        @PriceBookCode      varchar(100),
        @PriceBookName      nvarchar(300),
        @CurrencyCode       char(3),
        @StageCount         int;

    SET @FamilyCode =
        UPPER(LTRIM(RTRIM(@FamilyCode)));

    SET @PriceBookCode =
        CONCAT(
            @FamilyCode,
            '_STANDARD'
        );

    SET @PriceBookName =
        CONCAT(
            @FamilyCode,
            ' Standard Configuration Pricing'
        );


    /* ------------------------------------------------------------
       Resolve family
       ------------------------------------------------------------ */

    SELECT
        @PumpFamilyId =
            PumpFamilyId
    FROM cfg.PumpFamily
    WHERE
        FamilyCode = @FamilyCode
        AND IsActive = 1;

    IF @PumpFamilyId IS NULL
    BEGIN
        THROW 51001,
            'Active pump family was not found.',
            1;
    END;


    /* ------------------------------------------------------------
       Validate staging
       ------------------------------------------------------------ */

    SELECT
        @StageCount = COUNT(*)
    FROM stg.PricingExtract
    WHERE
        LoadBatchId = @LoadBatchId
        AND FamilyCode = @FamilyCode;

    IF @StageCount = 0
    BEGIN
        THROW 51002,
            'No pricing staging records were found for the load batch.',
            1;
    END;


    IF EXISTS
    (
        SELECT 1
        FROM stg.PricingExtract
        WHERE
            LoadBatchId = @LoadBatchId
            AND FamilyCode = @FamilyCode
            AND PricingStatus NOT IN
                (
                    'found',
                    'call_for_price'
                )
    )
    BEGIN
        THROW 51003,
            'Unsupported pricing status exists in staging.',
            1;
    END;


    IF EXISTS
    (
        SELECT 1
        FROM stg.PricingExtract
        WHERE
            LoadBatchId = @LoadBatchId
            AND FamilyCode = @FamilyCode
            AND
            (
                   (
                       PricingStatus = 'found'
                       AND Amount IS NULL
                   )
                OR (
                       PricingStatus =
                           'call_for_price'
                       AND Amount IS NOT NULL
                   )
            )
    )
    BEGIN
        THROW 51004,
            'Pricing amount/status combination is invalid.',
            1;
    END;


    IF EXISTS
    (
        SELECT
            ComponentCode,
            SeriesCode,
            SizeValue,
            OptionFieldCode,
            OptionValue
        FROM stg.PricingExtract
        WHERE
            LoadBatchId = @LoadBatchId
            AND FamilyCode = @FamilyCode
        GROUP BY
            ComponentCode,
            SeriesCode,
            SizeValue,
            OptionFieldCode,
            OptionValue
        HAVING COUNT(*) > 1
    )
    BEGIN
        THROW 51005,
            'Duplicate pricing keys exist in staging.',
            1;
    END;


    IF
    (
        SELECT COUNT(
            DISTINCT CurrencyCode
        )
        FROM stg.PricingExtract
        WHERE
            LoadBatchId = @LoadBatchId
            AND FamilyCode = @FamilyCode
    ) <> 1
    BEGIN
        THROW 51006,
            'A pricing publication must contain exactly one currency.',
            1;
    END;


    SELECT TOP (1)
        @CurrencyCode =
            CurrencyCode
    FROM stg.PricingExtract
    WHERE
        LoadBatchId = @LoadBatchId
        AND FamilyCode = @FamilyCode;


    BEGIN TRANSACTION;

    /* ------------------------------------------------------------
       Price book
       ------------------------------------------------------------ */

    SELECT
        @PriceBookId =
            PriceBookId
    FROM price.PriceBook
    WHERE
        PumpFamilyId = @PumpFamilyId
        AND PriceBookCode = @PriceBookCode;

    IF @PriceBookId IS NULL
    BEGIN
        INSERT INTO price.PriceBook
        (
            PumpFamilyId,
            PriceBookCode,
            PriceBookName,
            CurrencyCode,
            IsActive
        )
        VALUES
        (
            @PumpFamilyId,
            @PriceBookCode,
            @PriceBookName,
            @CurrencyCode,
            1
        );

        SET @PriceBookId =
            CONVERT(
                int,
                SCOPE_IDENTITY()
            );
    END
    ELSE
    BEGIN
        UPDATE price.PriceBook
        SET
            CurrencyCode = @CurrencyCode,
            IsActive = 1
        WHERE
            PriceBookId = @PriceBookId;
    END;


    /* ------------------------------------------------------------
       Reject duplicate version
       ------------------------------------------------------------ */

    IF EXISTS
    (
        SELECT 1
        FROM price.PriceBookVersion
        WHERE
            PriceBookId = @PriceBookId
            AND VersionCode = @VersionCode
    )
    BEGIN
        ROLLBACK TRANSACTION;

        THROW 51007,
            'The requested pricing version already exists.',
            1;
    END;


    /* ------------------------------------------------------------
       Close prior current publication
       ------------------------------------------------------------ */

    UPDATE price.PriceBookVersion
    SET
        IsCurrent = 0,

        EffectiveTo =
            CASE
                WHEN
                    EffectiveTo IS NULL
                    AND EffectiveFrom <
                        @EffectiveFrom
                THEN DATEADD(
                    DAY,
                    -1,
                    @EffectiveFrom
                )

                ELSE EffectiveTo
            END

    WHERE
        PriceBookId = @PriceBookId
        AND IsCurrent = 1;


    /* ------------------------------------------------------------
       Create new publication/version
       ------------------------------------------------------------ */

    INSERT INTO price.PriceBookVersion
    (
        PriceBookId,
        VersionCode,
        EffectiveFrom,
        EffectiveTo,
        IsCurrent,
        SourceWorkbook
    )
    VALUES
    (
        @PriceBookId,
        @VersionCode,
        @EffectiveFrom,
        NULL,
        1,
        @SourceWorkbook
    );

    SET @PriceBookVersionId =
        CONVERT(
            int,
            SCOPE_IDENTITY()
        );


    /* ------------------------------------------------------------
       Materialize deterministic source rows
       ------------------------------------------------------------ */

    CREATE TABLE #PricingSource
    (
        PricingExtractId     bigint NOT NULL,
        RuleCode             varchar(100) NOT NULL,
        ComponentCode        varchar(100) NOT NULL,
        SeriesCode           varchar(100) NULL,
        SourceSeriesCode     varchar(100) NULL,
        SizeValue            nvarchar(300) NULL,
        SourceSizeValue      nvarchar(300) NULL,
        OptionFieldCode      varchar(100) NULL,
        OptionValue          nvarchar(1000) NULL,
        SourceOptionValue    nvarchar(1000) NULL,
        ConditionsJson       nvarchar(max) NULL,
        Amount               decimal(19,4) NULL,
        PricingStatus        varchar(30) NOT NULL,
        SourcePriceValue     nvarchar(1000) NULL,
        SourceWorksheet      nvarchar(300) NULL,
        SourceTable          nvarchar(300) NULL,
        SourceCell           varchar(50) NULL
    );


    INSERT INTO #PricingSource
    (
        PricingExtractId,
        RuleCode,
        ComponentCode,
        SeriesCode,
        SourceSeriesCode,
        SizeValue,
        SourceSizeValue,
        OptionFieldCode,
        OptionValue,
        SourceOptionValue,
        ConditionsJson,
        Amount,
        PricingStatus,
        SourcePriceValue,
        SourceWorksheet,
        SourceTable,
        SourceCell
    )
    SELECT
        pe.PricingExtractId,

        CONCAT
        (
            'PR_',
            LEFT
            (
                CONVERT
                (
                    varchar(64),
                    HASHBYTES
                    (
                        'SHA2_256',

                        CONCAT
                        (
                            pe.FamilyCode,
                            '|',
                            pe.ComponentCode,
                            '|',
                            ISNULL(
                                pe.SeriesCode,
                                ''
                            ),
                            '|',
                            ISNULL(
                                pe.SizeValue,
                                ''
                            ),
                            '|',
                            ISNULL(
                                pe.OptionFieldCode,
                                ''
                            ),
                            '|',
                            ISNULL(
                                pe.OptionValue,
                                ''
                            )
                        )
                    ),
                    2
                ),
                32
            )
        ),

        pe.ComponentCode,
        pe.SeriesCode,
        pe.SourceSeriesCode,
        pe.SizeValue,
        pe.SourceSizeValue,
        pe.OptionFieldCode,
        pe.OptionValue,
        pe.SourceOptionValue,
        pe.ConditionsJson,
        pe.Amount,
        pe.PricingStatus,
        pe.SourcePriceValue,
        pe.SourceWorksheet,
        pe.SourceTable,
        pe.SourceCell

    FROM stg.PricingExtract pe
    WHERE
        pe.LoadBatchId = @LoadBatchId
        AND pe.FamilyCode = @FamilyCode;


    /* ------------------------------------------------------------
       Create runtime price rules
       ------------------------------------------------------------ */

    INSERT INTO price.PriceRule
    (
        PriceBookVersionId,
        RuleCode,
        RuleName,
        RuleType,
        Priority,
        Amount,
        IsActive,

        ComponentCode,
        SeriesCode,
        PricingStatus,

        SourceSeriesCode,
        SourceSizeValue,
        SourceOptionValue,
        SourcePriceValue,
        SourceWorksheet,
        SourceTable,
        SourceCell
    )
    SELECT
        @PriceBookVersionId,

        src.RuleCode,

        CONCAT
        (
            src.ComponentCode,
            ' / ',
            ISNULL(
                src.SeriesCode,
                '*'
            ),
            ' / ',
            ISNULL(
                src.SizeValue,
                '*'
            ),
            ' / ',
            ISNULL(
                src.OptionValue,
                '*'
            )
        ),

        'LOOKUP',

        100,

        COALESCE(
            src.Amount,
            0
        ),

        1,

        src.ComponentCode,
        src.SeriesCode,
        src.PricingStatus,

        src.SourceSeriesCode,
        src.SourceSizeValue,
        src.SourceOptionValue,
        src.SourcePriceValue,
        src.SourceWorksheet,
        src.SourceTable,
        src.SourceCell

    FROM #PricingSource src;


    /* ------------------------------------------------------------
       Add canonical configuration conditions

       M022:
       ConditionsJson is authoritative for new publications.
       NULL ConditionsJson falls back to the M021 fixed transport.
       ------------------------------------------------------------ */

    INSERT INTO price.PriceCondition
    (
        PriceRuleId,
        SequenceNo,
        FieldCode,
        ComparisonOperator,
        ComparisonValue
    )
    SELECT
        pr.PriceRuleId,
        c.SequenceNo,
        c.FieldCode,
        c.ComparisonOperator,
        c.ComparisonValue
    FROM #PricingSource src
    INNER JOIN price.PriceRule pr
        ON pr.PriceBookVersionId = @PriceBookVersionId
        AND pr.RuleCode = src.RuleCode
    CROSS APPLY OPENJSON(src.ConditionsJson)
    WITH
    (
        SequenceNo         int            '$.sequence_no',
        FieldCode          varchar(100)   '$.field_code',
        ComparisonOperator varchar(30)    '$.comparison_operator',
        ComparisonValue    nvarchar(1000) '$.comparison_value'
    ) c
    WHERE src.ConditionsJson IS NOT NULL;


    INSERT INTO price.PriceCondition
    (
        PriceRuleId,
        SequenceNo,
        FieldCode,
        ComparisonOperator,
        ComparisonValue
    )
    SELECT
        pr.PriceRuleId,
        1,
        'SIZE',
        'EQ',
        src.SizeValue
    FROM #PricingSource src
    INNER JOIN price.PriceRule pr
        ON pr.PriceBookVersionId = @PriceBookVersionId
        AND pr.RuleCode = src.RuleCode
    WHERE
        src.ConditionsJson IS NULL
        AND src.SizeValue IS NOT NULL;


    INSERT INTO price.PriceCondition
    (
        PriceRuleId,
        SequenceNo,
        FieldCode,
        ComparisonOperator,
        ComparisonValue
    )
    SELECT
        pr.PriceRuleId,
        2,
        src.OptionFieldCode,
        'EQ',
        src.OptionValue
    FROM #PricingSource src
    INNER JOIN price.PriceRule pr
        ON pr.PriceBookVersionId = @PriceBookVersionId
        AND pr.RuleCode = src.RuleCode
    WHERE
        src.ConditionsJson IS NULL
        AND src.OptionFieldCode IS NOT NULL
        AND src.OptionValue IS NOT NULL;


    COMMIT TRANSACTION;


    /* ------------------------------------------------------------
       Publication result
       ------------------------------------------------------------ */

    SELECT
        @PriceBookId
            AS PriceBookId,

        @PriceBookVersionId
            AS PriceBookVersionId,

        @VersionCode
            AS VersionCode,

        @FamilyCode
            AS FamilyCode,

        @CurrencyCode
            AS CurrencyCode,

        @StageCount
            AS PublishedRuleCount,

        (
            SELECT COUNT(*)
            FROM price.PriceCondition pc
            INNER JOIN price.PriceRule pr
                ON pr.PriceRuleId =
                   pc.PriceRuleId
            WHERE
                pr.PriceBookVersionId =
                    @PriceBookVersionId
        )
            AS PublishedConditionCount;
END;
GO


PRINT
    'M021.2 pricing publication database objects deployed.';
GO


SET ANSI_NULLS ON;
GO
SET QUOTED_IDENTIFIER ON;
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

/* ================================================================
   M021.4B - PRICING PUBLICATION RECONCILIATION

   Baseline:
       Family                FYBROC
       Price Book            FYBROC_STANDARD
       Version               FYBROC-BASE-20260807-V2
       Rules                 436
       Conditions            872
       found                 421
       call_for_price        15

   Known proof:
       1530 (ANSI)
       1x1.5x6
       VR-1*
       USD 4854

   Known C/F proof:
       3000
       6x8x11
       VR-1*
       call_for_price
   ================================================================ */

DECLARE
    @FamilyCode varchar(30) = 'FYBROC',
    @PriceBookCode varchar(100) = 'FYBROC_STANDARD',
    @VersionCode varchar(50) = 'FYBROC-BASE-20260807-V2',
    @VersionId int,
    @CurrentVersionCount int,
    @RuleCount int,
    @ConditionCount int,
    @FoundCount int,
    @CallForPriceCount int;


/* ---------------------------------------------------------------
   1. Resolve active V2
   --------------------------------------------------------------- */

SELECT
    @VersionId = pbv.PriceBookVersionId
FROM price.PriceBook pb
JOIN cfg.PumpFamily pf
    ON pf.PumpFamilyId = pb.PumpFamilyId
JOIN price.PriceBookVersion pbv
    ON pbv.PriceBookId = pb.PriceBookId
WHERE
    pf.FamilyCode = @FamilyCode
    AND pb.PriceBookCode = @PriceBookCode
    AND pbv.VersionCode = @VersionCode
    AND pbv.IsCurrent = 1
    AND pb.IsActive = 1
    AND pf.IsActive = 1;

IF @VersionId IS NULL
BEGIN
    THROW 52001,
        'M021 reconciliation failed: active V2 pricing publication was not found.',
        1;
END;


/* ---------------------------------------------------------------
   2. Exactly one current version
   --------------------------------------------------------------- */

SELECT
    @CurrentVersionCount = COUNT(*)
FROM price.PriceBook pb
JOIN cfg.PumpFamily pf
    ON pf.PumpFamilyId = pb.PumpFamilyId
JOIN price.PriceBookVersion pbv
    ON pbv.PriceBookId = pb.PriceBookId
WHERE
    pf.FamilyCode = @FamilyCode
    AND pb.PriceBookCode = @PriceBookCode
    AND pbv.IsCurrent = 1;

IF @CurrentVersionCount <> 1
BEGIN
    THROW 52002,
        'M021 reconciliation failed: expected exactly one current pricing version.',
        1;
END;


/* ---------------------------------------------------------------
   3. Rule reconciliation
   --------------------------------------------------------------- */

SELECT
    @RuleCount = COUNT(*)
FROM price.PriceRule
WHERE
    PriceBookVersionId = @VersionId
    AND IsActive = 1;

IF @RuleCount <> 436
BEGIN
    THROW 52003,
        'M021 reconciliation failed: expected 436 active pricing rules.',
        1;
END;


/* ---------------------------------------------------------------
   4. Condition reconciliation
   --------------------------------------------------------------- */

SELECT
    @ConditionCount = COUNT(*)
FROM price.PriceCondition pc
JOIN price.PriceRule pr
    ON pr.PriceRuleId = pc.PriceRuleId
WHERE
    pr.PriceBookVersionId = @VersionId
    AND pr.IsActive = 1;

IF @ConditionCount <> 872
BEGIN
    THROW 52004,
        'M021 reconciliation failed: expected 872 pricing conditions.',
        1;
END;


/* ---------------------------------------------------------------
   5. Pricing status reconciliation
   --------------------------------------------------------------- */

SELECT
    @FoundCount =
        SUM(
            CASE
                WHEN PricingStatus = 'found'
                THEN 1
                ELSE 0
            END
        ),

    @CallForPriceCount =
        SUM(
            CASE
                WHEN PricingStatus = 'call_for_price'
                THEN 1
                ELSE 0
            END
        )

FROM price.PriceRule
WHERE
    PriceBookVersionId = @VersionId
    AND IsActive = 1;

IF ISNULL(@FoundCount, 0) <> 421
BEGIN
    THROW 52005,
        'M021 reconciliation failed: expected 421 found pricing rules.',
        1;
END;

IF ISNULL(@CallForPriceCount, 0) <> 15
BEGIN
    THROW 52006,
        'M021 reconciliation failed: expected 15 call-for-price rules.',
        1;
END;


/* ---------------------------------------------------------------
   6. No duplicate canonical pricing keys
   --------------------------------------------------------------- */

IF EXISTS
(
    SELECT
        pr.SeriesCode,
        sizeCondition.ComparisonValue AS SizeValue,
        optionCondition.FieldCode,
        optionCondition.ComparisonValue AS OptionValue
    FROM price.PriceRule pr

    LEFT JOIN price.PriceCondition sizeCondition
        ON sizeCondition.PriceRuleId = pr.PriceRuleId
        AND sizeCondition.FieldCode = 'SIZE'

    LEFT JOIN price.PriceCondition optionCondition
        ON optionCondition.PriceRuleId = pr.PriceRuleId
        AND optionCondition.FieldCode = 'PUMP_MATERIAL'

    WHERE
        pr.PriceBookVersionId = @VersionId
        AND pr.IsActive = 1

    GROUP BY
        pr.SeriesCode,
        sizeCondition.ComparisonValue,
        optionCondition.FieldCode,
        optionCondition.ComparisonValue

    HAVING COUNT(*) > 1
)
BEGIN
    THROW 52007,
        'M021 reconciliation failed: duplicate canonical pricing keys exist.',
        1;
END;


/* ---------------------------------------------------------------
   7. Known 1530 price
   --------------------------------------------------------------- */

IF NOT EXISTS
(
    SELECT 1
    FROM price.PriceRule pr

    JOIN price.PriceCondition sizeCondition
        ON sizeCondition.PriceRuleId = pr.PriceRuleId
        AND sizeCondition.FieldCode = 'SIZE'
        AND sizeCondition.ComparisonOperator = 'EQ'
        AND sizeCondition.ComparisonValue = '1x1.5x6'

    JOIN price.PriceCondition materialCondition
        ON materialCondition.PriceRuleId = pr.PriceRuleId
        AND materialCondition.FieldCode = 'PUMP_MATERIAL'
        AND materialCondition.ComparisonOperator = 'EQ'
        AND materialCondition.ComparisonValue = 'VR-1*'

    WHERE
        pr.PriceBookVersionId = @VersionId
        AND pr.SeriesCode = '1530 (ANSI)'
        AND pr.SourceSeriesCode = '1530'
        AND pr.Amount = CAST(4854 AS decimal(19,4))
        AND pr.PricingStatus = 'found'
        AND pr.SourceSizeValue = '1X1.5X6'
        AND pr.SourceOptionValue = 'VR-1 (Standard)'
        AND pr.SourceCell = 'U6'
        AND pr.IsActive = 1
)
BEGIN
    THROW 52008,
        'M021 reconciliation failed: known 1530 pricing proof was not found.',
        1;
END;


/* ---------------------------------------------------------------
   8. Known 3000 call-for-price rule
   --------------------------------------------------------------- */

IF NOT EXISTS
(
    SELECT 1
    FROM price.PriceRule pr

    JOIN price.PriceCondition sizeCondition
        ON sizeCondition.PriceRuleId = pr.PriceRuleId
        AND sizeCondition.FieldCode = 'SIZE'
        AND sizeCondition.ComparisonValue = '6x8x11'

    JOIN price.PriceCondition materialCondition
        ON materialCondition.PriceRuleId = pr.PriceRuleId
        AND materialCondition.FieldCode = 'PUMP_MATERIAL'
        AND materialCondition.ComparisonValue = 'VR-1*'

    WHERE
        pr.PriceBookVersionId = @VersionId
        AND pr.SeriesCode = '3000'
        AND pr.SourceSeriesCode = '3000'
        AND pr.Amount = 0
        AND pr.PricingStatus = 'call_for_price'
        AND pr.SourceSizeValue = '6x8x11 (--)'
        AND pr.SourceOptionValue = 'VR-1 (Standard)'
        AND pr.SourceCell = 'FN11'
        AND pr.IsActive = 1
)
BEGIN
    THROW 52009,
        'M021 reconciliation failed: known 3000 call-for-price proof was not found.',
        1;
END;


/* ---------------------------------------------------------------
   9. Verify V1 is no longer current
   --------------------------------------------------------------- */

IF EXISTS
(
    SELECT 1
    FROM price.PriceBook pb
    JOIN price.PriceBookVersion pbv
        ON pbv.PriceBookId = pb.PriceBookId
    WHERE
        pb.PriceBookCode = @PriceBookCode
        AND pbv.VersionCode = 'FYBROC-BASE-20260807-V1'
        AND pbv.IsCurrent = 1
)
BEGIN
    THROW 52010,
        'M021 reconciliation failed: V1 is still current.',
        1;
END;


/* ---------------------------------------------------------------
   RESULT
   --------------------------------------------------------------- */

SELECT
    @VersionId AS PriceBookVersionId,
    @VersionCode AS VersionCode,
    @RuleCount AS RuleCount,
    @ConditionCount AS ConditionCount,
    @FoundCount AS FoundCount,
    @CallForPriceCount AS CallForPriceCount;

PRINT 'M021.4B pricing publication reconciliation PASSED.';
GO

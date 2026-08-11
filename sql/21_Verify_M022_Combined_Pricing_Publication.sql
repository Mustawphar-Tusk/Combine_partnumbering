:setvar ExpectedVersionCode "FYBROC-CONFIG-20260807-V3"

SET NOCOUNT ON;
SET XACT_ABORT ON;

DECLARE
    @ExpectedVersionCode varchar(50) =
        '$(ExpectedVersionCode)',
    @PriceBookVersionId int,
    @PriceBookId int,
    @RuleCount int,
    @ConditionCount int,
    @FoundCount int,
    @CallForPriceCount int,
    @BaseRuleCount int,
    @SealRuleCount int,
    @BaseConditionCount int,
    @SealConditionCount int;

SELECT
    @PriceBookVersionId =
        pbv.PriceBookVersionId,
    @PriceBookId =
        pb.PriceBookId
FROM price.PriceBook pb
INNER JOIN cfg.PumpFamily pf
    ON pf.PumpFamilyId =
       pb.PumpFamilyId
INNER JOIN price.PriceBookVersion pbv
    ON pbv.PriceBookId =
       pb.PriceBookId
WHERE
    pf.FamilyCode = 'FYBROC'
    AND pb.PriceBookCode =
        'FYBROC_STANDARD'
    AND pbv.IsCurrent = 1;

IF @PriceBookVersionId IS NULL
BEGIN
    THROW 52250,
        'No current FYBROC pricing publication exists.',
        1;
END;

IF NOT EXISTS
(
    SELECT 1
    FROM price.PriceBookVersion
    WHERE
        PriceBookVersionId =
            @PriceBookVersionId
        AND VersionCode =
            @ExpectedVersionCode
)
BEGIN
    THROW 52251,
        'Current FYBROC pricing version code is not the expected M022.5 version.',
        1;
END;

SELECT
    @RuleCount =
        COUNT(*),
    @FoundCount =
        SUM(
            CASE
                WHEN PricingStatus =
                    'found'
                THEN 1
                ELSE 0
            END
        ),
    @CallForPriceCount =
        SUM(
            CASE
                WHEN PricingStatus =
                    'call_for_price'
                THEN 1
                ELSE 0
            END
        ),
    @BaseRuleCount =
        SUM(
            CASE
                WHEN ComponentCode =
                    'BASE_PUMP'
                THEN 1
                ELSE 0
            END
        ),
    @SealRuleCount =
        SUM(
            CASE
                WHEN ComponentCode =
                    'SEAL'
                THEN 1
                ELSE 0
            END
        )
FROM price.PriceRule
WHERE
    PriceBookVersionId =
        @PriceBookVersionId;

SELECT
    @ConditionCount =
        COUNT(*),
    @BaseConditionCount =
        SUM(
            CASE
                WHEN pr.ComponentCode =
                    'BASE_PUMP'
                THEN 1
                ELSE 0
            END
        ),
    @SealConditionCount =
        SUM(
            CASE
                WHEN pr.ComponentCode =
                    'SEAL'
                THEN 1
                ELSE 0
            END
        )
FROM price.PriceCondition pc
INNER JOIN price.PriceRule pr
    ON pr.PriceRuleId =
       pc.PriceRuleId
WHERE
    pr.PriceBookVersionId =
        @PriceBookVersionId;

IF @RuleCount <> 2884
BEGIN
    THROW 52252,
        'M022.5 rule-count reconciliation failed.',
        1;
END;

IF @ConditionCount <> 13112
BEGIN
    THROW 52253,
        'M022.5 condition-count reconciliation failed.',
        1;
END;

IF @FoundCount <> 2561
BEGIN
    THROW 52254,
        'M022.5 found-count reconciliation failed.',
        1;
END;

IF @CallForPriceCount <> 323
BEGIN
    THROW 52255,
        'M022.5 call-for-price reconciliation failed.',
        1;
END;

IF @BaseRuleCount <> 436
    OR @SealRuleCount <> 2448
BEGIN
    THROW 52256,
        'M022.5 component rule-count reconciliation failed.',
        1;
END;

IF @BaseConditionCount <> 872
    OR @SealConditionCount <> 12240
BEGIN
    THROW 52257,
        'M022.5 component condition-count reconciliation failed.',
        1;
END;

IF EXISTS
(
    SELECT 1
    FROM
    (
        SELECT
            pr.PriceRuleId,
            pr.ComponentCode,
            COUNT(pc.PriceConditionId)
                AS ConditionCount
        FROM price.PriceRule pr
        LEFT JOIN price.PriceCondition pc
            ON pc.PriceRuleId =
               pr.PriceRuleId
        WHERE
            pr.PriceBookVersionId =
                @PriceBookVersionId
        GROUP BY
            pr.PriceRuleId,
            pr.ComponentCode
    ) x
    WHERE
           (
               x.ComponentCode =
                   'BASE_PUMP'
               AND x.ConditionCount <> 2
           )
        OR (
               x.ComponentCode =
                   'SEAL'
               AND x.ConditionCount <> 5
           )
)
BEGIN
    THROW 52258,
        'M022.5 per-rule condition cardinality reconciliation failed.',
        1;
END;

-- Preserve the historical V2 baseline.
IF NOT EXISTS
(
    SELECT 1
    FROM price.PriceBookVersion pbv
    WHERE
        pbv.PriceBookId =
            @PriceBookId
        AND pbv.VersionCode =
            'FYBROC-BASE-20260807-V2'
        AND pbv.IsCurrent = 0
)
BEGIN
    THROW 52259,
        'Historical FYBROC V2 publication was not preserved as non-current.',
        1;
END;

IF
(
    SELECT COUNT(*)
    FROM price.PriceRule pr
    INNER JOIN price.PriceBookVersion pbv
        ON pbv.PriceBookVersionId =
           pr.PriceBookVersionId
    WHERE
        pbv.PriceBookId =
            @PriceBookId
        AND pbv.VersionCode =
            'FYBROC-BASE-20260807-V2'
) <> 436
BEGIN
    THROW 52260,
        'Historical FYBROC V2 rule baseline changed.',
        1;
END;

IF
(
    SELECT COUNT(*)
    FROM price.PriceCondition pc
    INNER JOIN price.PriceRule pr
        ON pr.PriceRuleId =
           pc.PriceRuleId
    INNER JOIN price.PriceBookVersion pbv
        ON pbv.PriceBookVersionId =
           pr.PriceBookVersionId
    WHERE
        pbv.PriceBookId =
            @PriceBookId
        AND pbv.VersionCode =
            'FYBROC-BASE-20260807-V2'
) <> 872
BEGIN
    THROW 52261,
        'Historical FYBROC V2 condition baseline changed.',
        1;
END;

SELECT
    @PriceBookVersionId
        AS PriceBookVersionId,
    @ExpectedVersionCode
        AS VersionCode,
    @RuleCount
        AS RuleCount,
    @ConditionCount
        AS ConditionCount,
    @FoundCount
        AS FoundCount,
    @CallForPriceCount
        AS CallForPriceCount,
    @BaseRuleCount
        AS BasePumpRules,
    @SealRuleCount
        AS SealRules,
    @BaseConditionCount
        AS BasePumpConditions,
    @SealConditionCount
        AS SealConditions;

PRINT
    'M022.5 combined FYBROC pricing publication reconciliation PASSED.';

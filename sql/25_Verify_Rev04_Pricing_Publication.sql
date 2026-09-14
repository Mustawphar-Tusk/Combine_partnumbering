/* ================================================================
   REV0.4 PRICING PUBLICATION VERIFICATION
   ----------------------------------------------------------------
   Fingerprints the CURRENT Fybroc pricing publication after adopting
   Fybroc Configuration Rev0.4.xlsx as the authoritative source
   (replacing Price Estimator-Fybroc.xlsm).

   Phase A scope: BASE_PUMP + SEAL. Counts are the Phase-A publication
   (FYBROC-REV04-20260914-V1). Phase B will re-publish with the full
   component set and these constants will be regenerated then.

   Also asserts the Price-Estimator publication (FYBROC-CONFIG-20260807-V3)
   is PRESERVED as non-current (non-destructive supersession).
   ================================================================ */
:setvar ExpectedVersionCode "FYBROC-REV04-20260914-V1"

SET NOCOUNT ON;
SET XACT_ABORT ON;

DECLARE
    @ExpectedVersionCode varchar(50) = '$(ExpectedVersionCode)',
    @PriceBookVersionId int,
    @PriceBookId int,
    @RuleCount int, @FoundCount int, @CallForPriceCount int,
    @BaseRuleCount int, @SealRuleCount int;

SELECT @PriceBookVersionId = pbv.PriceBookVersionId, @PriceBookId = pb.PriceBookId
FROM price.PriceBook pb
JOIN cfg.PumpFamily pf ON pf.PumpFamilyId = pb.PumpFamilyId
JOIN price.PriceBookVersion pbv ON pbv.PriceBookId = pb.PriceBookId
WHERE pf.FamilyCode = 'FYBROC' AND pb.PriceBookCode = 'FYBROC_STANDARD'
  AND pbv.IsCurrent = 1;

IF @PriceBookVersionId IS NULL
    THROW 52270, 'No current FYBROC pricing publication exists.', 1;

IF NOT EXISTS (SELECT 1 FROM price.PriceBookVersion
               WHERE PriceBookVersionId = @PriceBookVersionId
                 AND VersionCode = @ExpectedVersionCode)
    THROW 52271, 'Current FYBROC publication is not the expected Rev0.4 version.', 1;

-- Source workbook must be the Rev0.4 configuration workbook.
IF NOT EXISTS (SELECT 1 FROM price.PriceBookVersion
               WHERE PriceBookVersionId = @PriceBookVersionId
                 AND SourceWorkbook = 'Fybroc Configuration Rev0.4.xlsx')
    THROW 52272, 'Current FYBROC publication source is not Rev0.4.', 1;

SELECT @RuleCount = COUNT(*),
       @FoundCount = SUM(CASE WHEN PricingStatus = 'found' THEN 1 ELSE 0 END),
       @CallForPriceCount = SUM(CASE WHEN PricingStatus = 'call_for_price' THEN 1 ELSE 0 END),
       @BaseRuleCount = SUM(CASE WHEN ComponentCode = 'BASE_PUMP' THEN 1 ELSE 0 END),
       @SealRuleCount = SUM(CASE WHEN ComponentCode = 'SEAL' THEN 1 ELSE 0 END)
FROM price.PriceRule WHERE PriceBookVersionId = @PriceBookVersionId;

IF @RuleCount <> 7037
    THROW 52273, 'Rev0.4 Phase A rule-count reconciliation failed (expected 7037).', 1;
IF @BaseRuleCount <> 199 OR @SealRuleCount <> 6838
    THROW 52274, 'Rev0.4 Phase A component rule-count reconciliation failed (BASE_PUMP=199, SEAL=6838).', 1;
IF @FoundCount <> 2228 OR @CallForPriceCount <> 4809
    THROW 52275, 'Rev0.4 Phase A found/call-for-price reconciliation failed (found=2228, c/f=4809).', 1;

-- Non-destructive supersession: the Price-Estimator publication is preserved
-- as non-current.
IF NOT EXISTS (SELECT 1 FROM price.PriceBookVersion pbv
               WHERE pbv.PriceBookId = @PriceBookId
                 AND pbv.VersionCode = 'FYBROC-CONFIG-20260807-V3'
                 AND pbv.IsCurrent = 0)
    THROW 52276, 'Prior Price-Estimator publication (V3) was not preserved as non-current.', 1;

SELECT @PriceBookVersionId AS PriceBookVersionId, @ExpectedVersionCode AS VersionCode,
       @RuleCount AS RuleCount, @FoundCount AS FoundCount,
       @CallForPriceCount AS CallForPriceCount,
       @BaseRuleCount AS BasePumpRules, @SealRuleCount AS SealRules;

PRINT 'Rev0.4 Phase A FYBROC pricing publication reconciliation PASSED.';

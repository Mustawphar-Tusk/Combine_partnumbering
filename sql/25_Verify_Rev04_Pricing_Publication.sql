/* ================================================================
   REV0.4 PRICING PUBLICATION VERIFICATION
   ----------------------------------------------------------------
   Fingerprints the CURRENT Fybroc pricing publication: the MERGED
   Rev0.4 <-> Price-Estimator overlay (option 2b).

   Model: Rev0.4 pricing adopted only for series 1500 & 5500 (Rev0.4
   'found' prices); other series retain their Price-Estimator prices;
   Rev0.4 C/F (Contact Factory) does not overwrite (retain PE where it
   exists, else no priced row / call-for-price default). See
   docs/evidence/REV04_PRICING/REV04_vs_PriceEstimator_DIFF.md.

   Asserts the Price-Estimator publication (FYBROC-CONFIG-20260807-V3)
   is PRESERVED as non-current (non-destructive supersession).
   ================================================================ */
:setvar ExpectedVersionCode "FYBROC-REV04-MERGE-20260914-V1"

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

-- Source workbook must reference the Rev0.4 configuration workbook (the merged
-- publication records both sources: "Fybroc Configuration Rev0.4.xlsx + Price
-- Estimator-Fybroc.xlsm (merged)").
IF NOT EXISTS (SELECT 1 FROM price.PriceBookVersion
               WHERE PriceBookVersionId = @PriceBookVersionId
                 AND SourceWorkbook LIKE '%Rev0.4%')
    THROW 52272, 'Current FYBROC publication source does not reference Rev0.4.', 1;

SELECT @RuleCount = COUNT(*),
       @FoundCount = SUM(CASE WHEN PricingStatus = 'found' THEN 1 ELSE 0 END),
       @CallForPriceCount = SUM(CASE WHEN PricingStatus = 'call_for_price' THEN 1 ELSE 0 END),
       @BaseRuleCount = SUM(CASE WHEN ComponentCode = 'BASE_PUMP' THEN 1 ELSE 0 END),
       @SealRuleCount = SUM(CASE WHEN ComponentCode = 'SEAL' THEN 1 ELSE 0 END)
FROM price.PriceRule WHERE PriceBookVersionId = @PriceBookVersionId;

-- Merged (Rev0.4 overlay for 1500/5500 + retained Price-Estimator for other series).
IF @RuleCount <> 56241
    THROW 52273, 'Rev0.4 merged rule-count reconciliation failed (expected 56241).', 1;
IF @FoundCount <> 56088 OR @CallForPriceCount <> 153
    THROW 52275, 'Rev0.4 merged found/call-for-price reconciliation failed (found=56088, c/f=153).', 1;

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

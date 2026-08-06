SET ANSI_NULLS ON;
GO
SET QUOTED_IDENTIFIER ON;
GO
SET ANSI_PADDING ON;
GO
SET ANSI_WARNINGS ON;
GO
SET CONCAT_NULL_YIELDS_NULL ON;
GO
SET ARITHABORT ON;
GO
SET NUMERIC_ROUNDABORT OFF;
GO
USE PumpConfiguratorDB;
GO
CREATE OR ALTER PROCEDURE cfg.usp_GetCurrentConfigurationVersion
 @FamilyCode varchar(50)
AS
BEGIN
 SET NOCOUNT ON;
 SELECT cv.ConfigurationVersionId,cv.VersionCode,pf.PumpFamilyId,pf.FamilyCode,pf.FamilyName
 FROM cfg.ConfigurationVersion cv
 JOIN cfg.PumpFamily pf ON pf.PumpFamilyId=cv.PumpFamilyId
 WHERE pf.FamilyCode=@FamilyCode AND pf.IsActive=1 AND cv.IsCurrent=1 AND cv.Status='Published';
END;
GO

CREATE OR ALTER PROCEDURE price.usp_GetConfigurationPrice
 @FamilyCode varchar(50),
 @ConfigurationJson nvarchar(max),
 @EffectiveDate date=NULL
AS
BEGIN
 SET NOCOUNT ON;
 IF ISJSON(@ConfigurationJson)<>1 THROW 50010,'ConfigurationJson must be valid JSON.',1;
 SET @EffectiveDate=COALESCE(@EffectiveDate,CAST(SYSUTCDATETIME() AS date));

 DECLARE @PriceBookVersionId int;
 SELECT TOP(1) @PriceBookVersionId=pbv.PriceBookVersionId
 FROM price.PriceBook pb
 JOIN price.PriceBookVersion pbv ON pbv.PriceBookId=pb.PriceBookId
 JOIN cfg.PumpFamily pf ON pf.PumpFamilyId=pb.PumpFamilyId
 WHERE pf.FamilyCode=@FamilyCode AND pb.IsActive=1
   AND pbv.EffectiveFrom<=@EffectiveDate
   AND (pbv.EffectiveTo IS NULL OR pbv.EffectiveTo>=@EffectiveDate)
 ORDER BY pbv.IsCurrent DESC,pbv.EffectiveFrom DESC;

 IF @PriceBookVersionId IS NULL
 BEGIN
  SELECT CAST(0 AS decimal(19,4)) UnitPrice,'not_found' PricingStatus,
         N'No active price book was found; price returned as 0.' PricingMessage;
  RETURN;
 END;

 ;WITH Selected AS(
   SELECT JSON_VALUE(value,'$.fieldCode') FieldCode,
          COALESCE(JSON_VALUE(value,'$.optionCode'),JSON_VALUE(value,'$.value')) SelectedValue
   FROM OPENJSON(@ConfigurationJson)
 ),
 ApplicableRules AS(
   SELECT pr.PriceRuleId,pr.RuleType,pr.Amount
   FROM price.PriceRule pr
   WHERE pr.PriceBookVersionId=@PriceBookVersionId AND pr.IsActive=1
     AND NOT EXISTS(
       SELECT 1 FROM price.PriceCondition pc
       WHERE pc.PriceRuleId=pr.PriceRuleId
         AND NOT EXISTS(
           SELECT 1 FROM Selected s
           WHERE s.FieldCode=pc.FieldCode
             AND pc.ComparisonOperator='equals'
             AND s.SelectedValue=pc.ComparisonValue
         )
     )
 )
 SELECT CAST(COALESCE(MAX(CASE WHEN RuleType='override' THEN Amount END),
          SUM(CASE WHEN RuleType='base' THEN Amount WHEN RuleType='adder' THEN Amount
                   WHEN RuleType='discount' THEN -Amount ELSE 0 END),0) AS decimal(19,4)) UnitPrice,
        CASE WHEN COUNT(*)=0 THEN 'not_found' ELSE 'matched' END PricingStatus,
        CASE WHEN COUNT(*)=0 THEN N'No matching price rule was found; price returned as 0.'
             ELSE N'Matching price rules were applied.' END PricingMessage
 FROM ApplicableRules;
END;
GO

CREATE OR ALTER PROCEDURE cfg.usp_GetOrCreateConfiguredProduct
 @FamilyCode varchar(50),
 @SeriesCode varchar(100)=NULL,
 @ConfigurationJson nvarchar(max),
 @ConfigurationSignature char(64),
 @PartNumber varchar(200),
 @SKUCode varchar(100),
 @RequestedBy nvarchar(200)=NULL
AS
BEGIN
 SET NOCOUNT ON; SET XACT_ABORT ON;
 IF ISJSON(@ConfigurationJson)<>1 THROW 50020,'ConfigurationJson must be valid JSON.',1;
 BEGIN TRANSACTION;
 DECLARE @PumpFamilyId int,@ConfigurationVersionId int,@PumpSeriesId int=NULL,
         @ConfiguredProductId bigint,@Existing bit=0;
 SELECT @PumpFamilyId=pf.PumpFamilyId,@ConfigurationVersionId=cv.ConfigurationVersionId
 FROM cfg.PumpFamily pf
 JOIN cfg.ConfigurationVersion cv ON cv.PumpFamilyId=pf.PumpFamilyId
  AND cv.IsCurrent=1 AND cv.Status='Published'
 WHERE pf.FamilyCode=@FamilyCode AND pf.IsActive=1;
 IF @PumpFamilyId IS NULL THROW 50021,'No active family and published version found.',1;
 IF @SeriesCode IS NOT NULL
 BEGIN
  SELECT @PumpSeriesId=PumpSeriesId FROM cfg.PumpSeries
  WHERE ConfigurationVersionId=@ConfigurationVersionId AND SeriesCode=@SeriesCode AND IsActive=1;
  IF @PumpSeriesId IS NULL THROW 50022,'Requested pump series was not found.',1;
 END;
 SELECT @ConfiguredProductId=ConfiguredProductId
 FROM cfg.ConfiguredProduct WITH(UPDLOCK,HOLDLOCK)
 WHERE PumpFamilyId=@PumpFamilyId AND ConfigurationSignature=@ConfigurationSignature;
 IF @ConfiguredProductId IS NULL
 BEGIN
  INSERT cfg.ConfiguredProduct(PumpFamilyId,ConfigurationVersionId,PumpSeriesId,
   ConfigurationSignature,PartNumber,SKUCode,CanonicalConfiguration,CreatedBy)
  VALUES(@PumpFamilyId,@ConfigurationVersionId,@PumpSeriesId,@ConfigurationSignature,
   @PartNumber,@SKUCode,@ConfigurationJson,@RequestedBy);
  SET @ConfiguredProductId=SCOPE_IDENTITY();
 END
 ELSE SET @Existing=1;
 SELECT ConfiguredProductId,PartNumber,SKUCode,ConfigurationSignature,@Existing ExistingConfiguration
 FROM cfg.ConfiguredProduct WHERE ConfiguredProductId=@ConfiguredProductId;
 COMMIT;
END;
GO


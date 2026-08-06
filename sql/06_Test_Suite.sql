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
IF NOT EXISTS(SELECT 1 FROM cfg.PumpFamily WHERE FamilyCode='DEAN')
 THROW 51001,'DEAN family missing.',1;
IF NOT EXISTS(SELECT 1 FROM cfg.PumpFamily WHERE FamilyCode='FYBROC')
 THROW 51002,'FYBROC family missing.',1;
IF (SELECT COUNT(*) FROM cfg.ConfigurationVersion WHERE IsCurrent=1 AND Status='Published')<>2
 THROW 51003,'Expected two current published versions.',1;

DECLARE @T TABLE(UnitPrice decimal(19,4),PricingStatus varchar(30),PricingMessage nvarchar(500));
INSERT @T EXEC price.usp_GetConfigurationPrice
 @FamilyCode='DEAN',
 @ConfigurationJson=N'[{"fieldCode":"SERIES","optionCode":"DEV"}]',
 @EffectiveDate=NULL;
IF NOT EXISTS(SELECT 1 FROM @T WHERE UnitPrice=0 AND PricingStatus='not_found')
 THROW 51004,'Missing price must return 0 and not_found.',1;

PRINT 'All PumpConfiguratorDB tests passed.';
GO


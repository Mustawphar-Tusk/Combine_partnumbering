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
INSERT cfg.PumpFamily(FamilyCode,FamilyName)
VALUES('DEAN',N'Dean Pump'),('FYBROC',N'Fybroc Pump');

DECLARE @D int=(SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode='DEAN');
DECLARE @F int=(SELECT PumpFamilyId FROM cfg.PumpFamily WHERE FamilyCode='FYBROC');

INSERT cfg.ConfigurationVersion(PumpFamilyId,VersionCode,SourceWorkbook,Status,IsCurrent,PublishedAt)
VALUES(@D,'REV2',N'Dean Data Sheet Rev 2.xlsm','Published',1,SYSUTCDATETIME()),
      (@F,'V5',N'Fybroc Nomenclature_V5.xlsm','Published',1,SYSUTCDATETIME());

INSERT quote.QuoteTemplate(PumpFamilyId,TemplateCode,TemplateName,WorkbookName,WorksheetName)
VALUES(@D,'DEAN_FORMAL_QUOTE',N'Dean Formal Quote',N'Dean Data Sheet Rev 2.xlsm',N'Formal Quote'),
      (@F,'FYBROC_FORMAL_QUOTES',N'Fybroc Formal Quotes',N'Price Estimator-Fybroc.xlsm',N'Formal Quote');

INSERT price.PriceBook(PumpFamilyId,PriceBookCode,PriceBookName,CurrencyCode)
VALUES(@D,'DEAN_STANDARD',N'Dean Standard Price Book','USD'),
      (@F,'FYBROC_STANDARD',N'Fybroc Standard Price Book','USD');

INSERT price.PriceBookVersion(PriceBookId,VersionCode,EffectiveFrom,IsCurrent,SourceWorkbook)
SELECT PriceBookId,'DEV1',CAST(GETDATE() AS date),1,
 CASE WHEN PriceBookCode='DEAN_STANDARD' THEN N'Dean Data Sheet Rev 2.xlsm'
 ELSE N'Price Estimator-Fybroc.xlsm' END
FROM price.PriceBook;
GO


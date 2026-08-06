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
CREATE OR ALTER VIEW cfg.vw_CurrentConfigurationVersion AS
SELECT pf.PumpFamilyId,pf.FamilyCode,pf.FamilyName,cv.ConfigurationVersionId,
       cv.VersionCode,cv.SourceWorkbook,cv.PublishedAt
FROM cfg.PumpFamily pf
JOIN cfg.ConfigurationVersion cv ON cv.PumpFamilyId=pf.PumpFamilyId
WHERE pf.IsActive=1 AND cv.IsCurrent=1 AND cv.Status='Published';
GO
CREATE OR ALTER VIEW cfg.vw_ConfiguredProduct AS
SELECT cp.ConfiguredProductId,pf.FamilyCode,pf.FamilyName,ps.SeriesCode,ps.SeriesName,
       cp.PartNumber,cp.SKUCode,cp.ConfigurationSignature,cp.CanonicalConfiguration,
       cp.CreatedAt,cp.CreatedBy
FROM cfg.ConfiguredProduct cp
JOIN cfg.PumpFamily pf ON pf.PumpFamilyId=cp.PumpFamilyId
LEFT JOIN cfg.PumpSeries ps ON ps.PumpSeriesId=cp.PumpSeriesId;
GO


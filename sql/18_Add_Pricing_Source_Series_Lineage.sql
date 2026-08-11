SET ANSI_NULLS ON;
GO
SET QUOTED_IDENTIFIER ON;
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
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
    'price.PriceRule',
    'SourceSeriesCode'
) IS NULL
BEGIN
    ALTER TABLE price.PriceRule
        ADD SourceSeriesCode varchar(100) NULL;
END;
GO

PRINT 'M021 pricing source-series lineage deployed.';
GO

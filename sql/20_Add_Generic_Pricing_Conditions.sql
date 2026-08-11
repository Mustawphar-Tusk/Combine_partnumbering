SET ANSI_NULLS ON;
GO
SET QUOTED_IDENTIFIER ON;
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
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

PRINT 'M022.3 generic pricing condition staging deployed.';
GO

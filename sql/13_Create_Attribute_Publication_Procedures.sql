USE PumpConfiguratorDB;
GO

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

CREATE OR ALTER PROCEDURE stg.usp_CreateAttributeImportBatch
    @FamilyCode varchar(50),
    @SourceFile nvarchar(1000),
    @ExpectedRowCount int,
    @AttributeValueImportBatchId bigint OUTPUT
AS
BEGIN
    SET NOCOUNT ON;

    INSERT INTO stg.AttributeValueImportBatch
    (
        FamilyCode,
        SourceFile,
        ExpectedRowCount,
        Status
    )
    VALUES
    (
        @FamilyCode,
        @SourceFile,
        @ExpectedRowCount,
        'Loading'
    );

    SET @AttributeValueImportBatchId = SCOPE_IDENTITY();
END;
GO

CREATE OR ALTER PROCEDURE stg.usp_CompleteAttributeImportBatch
    @AttributeValueImportBatchId bigint,
    @LoadedRowCount int,
    @Status varchar(20),
    @ErrorMessage nvarchar(max) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE stg.AttributeValueImportBatch
    SET LoadedRowCount = @LoadedRowCount,
        Status = @Status,
        CompletedAt = SYSUTCDATETIME(),
        ErrorMessage = @ErrorMessage
    WHERE AttributeValueImportBatchId = @AttributeValueImportBatchId;
END;
GO

CREATE OR ALTER PROCEDURE cfg.usp_PublishAttributeValues
    @AttributeValueImportBatchId bigint,
    @VersionCode varchar(50),
    @Description nvarchar(1000) = NULL,
    @Activate bit = 0,
    @MetadataPublicationId bigint OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE @FamilyCode varchar(50);
    DECLARE @PumpFamilyId int;
    DECLARE @ExpectedRowCount int;
    DECLARE @LoadedRowCount int;
    DECLARE @BatchStatus varchar(20);

    SELECT
        @FamilyCode = FamilyCode,
        @ExpectedRowCount = ExpectedRowCount,
        @LoadedRowCount = LoadedRowCount,
        @BatchStatus = Status
    FROM stg.AttributeValueImportBatch
    WHERE AttributeValueImportBatchId = @AttributeValueImportBatchId;

    IF @FamilyCode IS NULL
        THROW 51000, 'Attribute import batch was not found.', 1;

    IF @BatchStatus <> 'Loaded'
        THROW 51001, 'Attribute import batch must have status Loaded.', 1;

    IF @ExpectedRowCount <> @LoadedRowCount
        THROW 51002, 'Attribute import row counts do not match.', 1;

    SELECT @PumpFamilyId = PumpFamilyId
    FROM cfg.PumpFamily
    WHERE FamilyCode = @FamilyCode;

    IF @PumpFamilyId IS NULL
        THROW 51003, 'Pump family was not found.', 1;

    IF EXISTS
    (
        SELECT 1
        FROM cfg.MetadataPublication
        WHERE VersionCode = @VersionCode
    )
        THROW 51004, 'Metadata publication version already exists.', 1;

    BEGIN TRANSACTION;

    INSERT INTO cfg.MetadataPublication
    (
        VersionCode,
        Status,
        Description,
        ActivatedAt
    )
    VALUES
    (
        @VersionCode,
        CASE WHEN @Activate = 1 THEN 'Active' ELSE 'Testing' END,
        @Description,
        CASE WHEN @Activate = 1 THEN SYSUTCDATETIME() ELSE NULL END
    );

    SET @MetadataPublicationId = SCOPE_IDENTITY();

    IF @Activate = 1
    BEGIN
        UPDATE cfg.MetadataPublication
        SET Status = 'Retired',
            RetiredAt = SYSUTCDATETIME()
        WHERE Status = 'Active'
          AND MetadataPublicationId <> @MetadataPublicationId;
    END;

    INSERT INTO cfg.AttributeValue
    (
        MetadataPublicationId,
        PumpFamilyId,
        FieldCode,
        FieldName,
        DisplayValue,
        IdentifierCode,
        DisplayOrder,
        WorkbookName,
        WorksheetName,
        SourceDisplayCell,
        SourceCodeCell
    )
    SELECT
        @MetadataPublicationId,
        @PumpFamilyId,
        FieldCode,
        FieldName,
        DisplayValue,
        IdentifierCode,
        DisplayOrder,
        WorkbookName,
        WorksheetName,
        SourceDisplayCell,
        SourceCodeCell
    FROM stg.AttributeValueImport
    WHERE AttributeValueImportBatchId = @AttributeValueImportBatchId;

    IF @@ROWCOUNT <> @LoadedRowCount
        THROW 51005, 'Published row count does not match loaded row count.', 1;

    UPDATE stg.AttributeValueImportBatch
    SET Status = 'Published'
    WHERE AttributeValueImportBatchId = @AttributeValueImportBatchId;

    COMMIT TRANSACTION;
END;
GO

CREATE OR ALTER VIEW cfg.vw_ActiveAttributeValue
AS
SELECT
    mp.MetadataPublicationId,
    mp.VersionCode,
    pf.FamilyCode,
    av.AttributeValueId,
    av.FieldCode,
    av.FieldName,
    av.DisplayValue,
    av.IdentifierCode,
    av.DisplayOrder,
    av.IsDefault,
    av.WorkbookName,
    av.WorksheetName,
    av.SourceDisplayCell,
    av.SourceCodeCell
FROM cfg.AttributeValue AS av
INNER JOIN cfg.MetadataPublication AS mp
    ON mp.MetadataPublicationId = av.MetadataPublicationId
INNER JOIN cfg.PumpFamily AS pf
    ON pf.PumpFamilyId = av.PumpFamilyId
WHERE mp.Status = 'Active'
  AND av.IsActive = 1;
GO

USE PumpConfiguratorDB;
GO

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

IF OBJECT_ID(N'cfg.MetadataPublication', N'U') IS NULL
BEGIN
    CREATE TABLE cfg.MetadataPublication
    (
        MetadataPublicationId bigint IDENTITY(1,1) PRIMARY KEY,
        VersionCode varchar(50) NOT NULL,
        Status varchar(20) NOT NULL,
        Description nvarchar(1000) NULL,
        CreatedAt datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
        ActivatedAt datetime2(0) NULL,
        RetiredAt datetime2(0) NULL,
        CONSTRAINT UQ_MetadataPublication_VersionCode UNIQUE (VersionCode),
        CONSTRAINT CK_MetadataPublication_Status
            CHECK (Status IN ('Draft','Testing','Active','Retired','Failed'))
    );
END;
GO

IF OBJECT_ID(N'stg.AttributeValueImportBatch', N'U') IS NULL
BEGIN
    CREATE TABLE stg.AttributeValueImportBatch
    (
        AttributeValueImportBatchId bigint IDENTITY(1,1) PRIMARY KEY,
        FamilyCode varchar(50) NOT NULL,
        SourceFile nvarchar(1000) NOT NULL,
        ExpectedRowCount int NOT NULL,
        LoadedRowCount int NOT NULL DEFAULT 0,
        Status varchar(20) NOT NULL DEFAULT 'Created',
        StartedAt datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
        CompletedAt datetime2(0) NULL,
        ErrorMessage nvarchar(max) NULL
    );
END;
GO

IF OBJECT_ID(N'stg.AttributeValueImport', N'U') IS NULL
BEGIN
    CREATE TABLE stg.AttributeValueImport
    (
        AttributeValueImportId bigint IDENTITY(1,1) PRIMARY KEY,
        AttributeValueImportBatchId bigint NOT NULL,
        FamilyCode varchar(50) NOT NULL,
        WorkbookRole varchar(100) NOT NULL,
        WorkbookName nvarchar(300) NOT NULL,
        WorksheetName nvarchar(200) NOT NULL,
        FieldCode varchar(100) NOT NULL,
        FieldName nvarchar(300) NOT NULL,
        DisplayValue nvarchar(500) NOT NULL,
        IdentifierCode varchar(100) NOT NULL,
        DisplayOrder int NOT NULL,
        SourceDisplayCell varchar(30) NOT NULL,
        SourceCodeCell varchar(30) NOT NULL,
        SourceProfile nvarchar(1000) NOT NULL,
        CONSTRAINT FK_AttributeValueImport_Batch
            FOREIGN KEY (AttributeValueImportBatchId)
            REFERENCES stg.AttributeValueImportBatch(AttributeValueImportBatchId)
    );

    CREATE UNIQUE INDEX UX_AttributeValueImport_Value
        ON stg.AttributeValueImport
        (
            AttributeValueImportBatchId,
            FieldCode,
            DisplayValue
        );
END;
GO

IF OBJECT_ID(N'cfg.AttributeValue', N'U') IS NULL
BEGIN
    CREATE TABLE cfg.AttributeValue
    (
        AttributeValueId bigint IDENTITY(1,1) PRIMARY KEY,
        MetadataPublicationId bigint NOT NULL,
        PumpFamilyId int NOT NULL,
        FieldCode varchar(100) NOT NULL,
        FieldName nvarchar(300) NOT NULL,
        DisplayValue nvarchar(500) NOT NULL,
        IdentifierCode varchar(100) NOT NULL,
        EngineeringDescription nvarchar(1000) NULL,
        EngineeringNotes nvarchar(max) NULL,
        DisplayOrder int NOT NULL,
        IsDefault bit NOT NULL DEFAULT 0,
        IsActive bit NOT NULL DEFAULT 1,
        WorkbookName nvarchar(300) NOT NULL,
        WorksheetName nvarchar(200) NOT NULL,
        SourceDisplayCell varchar(30) NOT NULL,
        SourceCodeCell varchar(30) NOT NULL,
        CreatedAt datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_AttributeValue_Publication
            FOREIGN KEY (MetadataPublicationId)
            REFERENCES cfg.MetadataPublication(MetadataPublicationId),
        CONSTRAINT FK_AttributeValue_PumpFamily
            FOREIGN KEY (PumpFamilyId)
            REFERENCES cfg.PumpFamily(PumpFamilyId)
    );

    CREATE UNIQUE INDEX UX_AttributeValue_ActiveDisplay
        ON cfg.AttributeValue
        (
            MetadataPublicationId,
            PumpFamilyId,
            FieldCode,
            DisplayValue
        )
        WHERE IsActive = 1;

    CREATE INDEX IX_AttributeValue_Resolver
        ON cfg.AttributeValue
        (
            MetadataPublicationId,
            PumpFamilyId,
            FieldCode,
            DisplayValue
        )
        INCLUDE (IdentifierCode, DisplayOrder);
END;
GO

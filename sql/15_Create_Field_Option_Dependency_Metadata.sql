USE PumpConfiguratorDB;
GO
SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

IF OBJECT_ID(N'stg.FieldOptionDependencyImportBatch', N'U') IS NULL
BEGIN
    CREATE TABLE stg.FieldOptionDependencyImportBatch
    (
        FieldOptionDependencyImportBatchId bigint IDENTITY(1,1) PRIMARY KEY,
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

IF OBJECT_ID(N'stg.FieldOptionDependencyImport', N'U') IS NULL
BEGIN
    CREATE TABLE stg.FieldOptionDependencyImport
    (
        FieldOptionDependencyImportId bigint IDENTITY(1,1) PRIMARY KEY,
        FieldOptionDependencyImportBatchId bigint NOT NULL,
        FamilyCode varchar(50) NOT NULL,
        DependencyCode varchar(100) NOT NULL,
        TargetFieldCode varchar(100) NOT NULL,
        TargetDisplayValue nvarchar(500) NOT NULL,
        TargetIdentifierCode varchar(50) NULL,
        SeriesCode varchar(50) NULL,
        ContextJson nvarchar(max) NOT NULL,
        SourceWorkbook nvarchar(300) NOT NULL,
        SourceWorksheet nvarchar(200) NOT NULL,
        SourceReference nvarchar(500) NOT NULL,
        CONSTRAINT FK_FieldOptionDependencyImport_Batch
            FOREIGN KEY (FieldOptionDependencyImportBatchId)
            REFERENCES stg.FieldOptionDependencyImportBatch
                (FieldOptionDependencyImportBatchId),
        CONSTRAINT CK_FieldOptionDependencyImport_ContextJson
            CHECK (ISJSON(ContextJson) = 1)
    );

    CREATE INDEX IX_FieldOptionDependencyImport_Lookup
        ON stg.FieldOptionDependencyImport
        (
            FieldOptionDependencyImportBatchId,
            TargetFieldCode,
            SeriesCode
        )
        INCLUDE (TargetDisplayValue, TargetIdentifierCode);
END;
GO

IF OBJECT_ID(N'cfg.FieldOptionDependency', N'U') IS NULL
BEGIN
    CREATE TABLE cfg.FieldOptionDependency
    (
        FieldOptionDependencyId bigint IDENTITY(1,1) PRIMARY KEY,
        MetadataPublicationId bigint NOT NULL,
        PumpFamilyId int NOT NULL,
        DependencyCode varchar(100) NOT NULL,
        TargetFieldCode varchar(100) NOT NULL,
        TargetDisplayValue nvarchar(500) NOT NULL,
        TargetIdentifierCode varchar(50) NULL,
        SeriesCode varchar(50) NULL,
        ContextJson nvarchar(max) NOT NULL,
        SourceWorkbook nvarchar(300) NOT NULL,
        SourceWorksheet nvarchar(200) NOT NULL,
        SourceReference nvarchar(500) NOT NULL,
        IsActive bit NOT NULL DEFAULT 1,
        CreatedAt datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_FieldOptionDependency_Publication
            FOREIGN KEY (MetadataPublicationId)
            REFERENCES cfg.MetadataPublication(MetadataPublicationId),
        CONSTRAINT FK_FieldOptionDependency_Family
            FOREIGN KEY (PumpFamilyId)
            REFERENCES cfg.PumpFamily(PumpFamilyId),
        CONSTRAINT CK_FieldOptionDependency_ContextJson
            CHECK (ISJSON(ContextJson) = 1)
    );

    CREATE INDEX IX_FieldOptionDependency_Projection
        ON cfg.FieldOptionDependency
        (
            MetadataPublicationId,
            PumpFamilyId,
            TargetFieldCode,
            SeriesCode
        )
        INCLUDE (TargetDisplayValue, TargetIdentifierCode, ContextJson)
        WHERE IsActive = 1;
END;
GO

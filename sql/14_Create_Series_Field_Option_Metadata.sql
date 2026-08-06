USE PumpConfiguratorDB;
GO

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

IF OBJECT_ID(N'stg.SeriesFieldOptionImportBatch', N'U') IS NULL
BEGIN
    CREATE TABLE stg.SeriesFieldOptionImportBatch
    (
        SeriesFieldOptionImportBatchId bigint IDENTITY(1,1) PRIMARY KEY,
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

IF OBJECT_ID(N'stg.SeriesFieldOptionImport', N'U') IS NULL
BEGIN
    CREATE TABLE stg.SeriesFieldOptionImport
    (
        SeriesFieldOptionImportId bigint IDENTITY(1,1) PRIMARY KEY,
        SeriesFieldOptionImportBatchId bigint NOT NULL,
        FamilyCode varchar(50) NOT NULL,
        SourceFieldCode varchar(100) NOT NULL,
        FieldCode varchar(100) NOT NULL,
        OptionValue nvarchar(500) NOT NULL,
        SeriesCode varchar(50) NOT NULL,
        WorkbookName nvarchar(300) NOT NULL,
        WorksheetName nvarchar(200) NOT NULL,
        SourceRow int NOT NULL,
        SourceFieldCell varchar(30) NOT NULL,
        SourceValueCell varchar(30) NOT NULL,
        SourceSeriesCell varchar(30) NOT NULL,
        SourceProfile nvarchar(1000) NOT NULL,
        CONSTRAINT FK_SeriesFieldOptionImport_Batch
            FOREIGN KEY (SeriesFieldOptionImportBatchId)
            REFERENCES stg.SeriesFieldOptionImportBatch
            (
                SeriesFieldOptionImportBatchId
            )
    );

    CREATE UNIQUE INDEX UX_SeriesFieldOptionImport_Relation
        ON stg.SeriesFieldOptionImport
        (
            SeriesFieldOptionImportBatchId,
            FieldCode,
            SeriesCode,
            OptionValue
        );
END;
GO

IF OBJECT_ID(N'cfg.SeriesFieldOption', N'U') IS NULL
BEGIN
    CREATE TABLE cfg.SeriesFieldOption
    (
        SeriesFieldOptionId bigint IDENTITY(1,1) PRIMARY KEY,
        MetadataPublicationId bigint NOT NULL,
        PumpFamilyId int NOT NULL,
        SourceFieldCode varchar(100) NOT NULL,
        FieldCode varchar(100) NOT NULL,
        OptionValue nvarchar(500) NOT NULL,
        SeriesCode varchar(50) NOT NULL,
        WorkbookName nvarchar(300) NOT NULL,
        WorksheetName nvarchar(200) NOT NULL,
        SourceRow int NOT NULL,
        SourceFieldCell varchar(30) NOT NULL,
        SourceValueCell varchar(30) NOT NULL,
        SourceSeriesCell varchar(30) NOT NULL,
        IsActive bit NOT NULL DEFAULT 1,
        CreatedAt datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_SeriesFieldOption_Publication
            FOREIGN KEY (MetadataPublicationId)
            REFERENCES cfg.MetadataPublication
            (
                MetadataPublicationId
            ),
        CONSTRAINT FK_SeriesFieldOption_Family
            FOREIGN KEY (PumpFamilyId)
            REFERENCES cfg.PumpFamily(PumpFamilyId)
    );

    CREATE UNIQUE INDEX UX_SeriesFieldOption_ActiveRelation
        ON cfg.SeriesFieldOption
        (
            MetadataPublicationId,
            PumpFamilyId,
            FieldCode,
            SeriesCode,
            OptionValue
        )
        WHERE IsActive = 1;

    CREATE INDEX IX_SeriesFieldOption_Projection
        ON cfg.SeriesFieldOption
        (
            MetadataPublicationId,
            PumpFamilyId,
            SeriesCode,
            FieldCode
        )
        INCLUDE (OptionValue)
        WHERE IsActive = 1;
END;
GO

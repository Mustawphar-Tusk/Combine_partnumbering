USE PumpConfiguratorDB;
GO

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

IF OBJECT_ID(N'stg.SegmentCombinationImportBatch', N'U') IS NULL
BEGIN
    CREATE TABLE stg.SegmentCombinationImportBatch
    (
        ImportBatchId bigint IDENTITY(1,1) PRIMARY KEY,
        FamilyCode varchar(50) NOT NULL,
        SourceFile nvarchar(1000) NOT NULL,
        SourceFileHash char(64) NOT NULL,
        ExpectedRowCount int NOT NULL,
        LoadedRowCount int NOT NULL DEFAULT 0,
        Status varchar(30) NOT NULL DEFAULT 'Created',
        StartedAt datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
        CompletedAt datetime2(0) NULL,
        ErrorMessage nvarchar(max) NULL,
        CONSTRAINT CK_SegmentCombinationImportBatch_Status
            CHECK (Status IN ('Created','Loading','Loaded','Validated','Failed'))
    );

    CREATE UNIQUE INDEX UX_SegmentCombinationImportBatch_FileHash
        ON stg.SegmentCombinationImportBatch(FamilyCode, SourceFileHash);
END;
GO

IF OBJECT_ID(N'stg.SegmentCombinationImport', N'U') IS NULL
BEGIN
    CREATE TABLE stg.SegmentCombinationImport
    (
        SegmentCombinationImportId bigint IDENTITY(1,1) PRIMARY KEY,
        ImportBatchId bigint NOT NULL,
        FamilyCode varchar(50) NOT NULL,
        WorkbookRole varchar(100) NOT NULL,
        WorkbookName nvarchar(300) NOT NULL,
        WorksheetName nvarchar(200) NOT NULL,
        SegmentCode varchar(100) NOT NULL,
        SegmentName nvarchar(300) NOT NULL,
        SourceRow int NOT NULL,
        SourceId int NOT NULL,
        SegmentValue varchar(100) NOT NULL,
        ExpectedWidth int NOT NULL,
        CombinationKey nvarchar(2000) NOT NULL,
        CombinationKeyHash AS CONVERT(binary(32), HASHBYTES('SHA2_256', CONVERT(varbinary(max), CombinationKey))) PERSISTED,
        SelectionsJson nvarchar(max) NOT NULL,
        SourceCellsJson nvarchar(max) NOT NULL,
        SourceProfile nvarchar(1000) NOT NULL,
        LoadedAt datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_SegmentCombinationImport_Batch
            FOREIGN KEY (ImportBatchId)
            REFERENCES stg.SegmentCombinationImportBatch(ImportBatchId),
        CONSTRAINT CK_SegmentCombinationImport_SelectionsJson
            CHECK (ISJSON(SelectionsJson) = 1),
        CONSTRAINT CK_SegmentCombinationImport_SourceCellsJson
            CHECK (ISJSON(SourceCellsJson) = 1),
        CONSTRAINT CK_SegmentCombinationImport_ExpectedWidth
            CHECK (ExpectedWidth > 0),
        CONSTRAINT CK_SegmentCombinationImport_SegmentWidth
            CHECK (LEN(SegmentValue) = ExpectedWidth)
    );

    CREATE UNIQUE INDEX UX_SegmentCombinationImport_SourceId
        ON stg.SegmentCombinationImport(ImportBatchId, SegmentCode, SourceId);

    CREATE UNIQUE INDEX UX_SegmentCombinationImport_KeyHash
        ON stg.SegmentCombinationImport(ImportBatchId, SegmentCode, CombinationKeyHash);

    CREATE INDEX IX_SegmentCombinationImport_Segment
        ON stg.SegmentCombinationImport(ImportBatchId, SegmentCode);
END;
GO

CREATE OR ALTER VIEW stg.vw_SegmentCombinationImportValidation
AS
SELECT
    b.ImportBatchId,
    b.FamilyCode,
    b.SourceFile,
    b.ExpectedRowCount,
    b.LoadedRowCount,
    b.Status,
    i.SegmentCode,
    COUNT_BIG(*) AS SegmentRowCount,
    MIN(i.SourceId) AS MinimumSourceId,
    MAX(i.SourceId) AS MaximumSourceId,
    MIN(i.SourceRow) AS FirstSourceRow,
    MAX(i.SourceRow) AS LastSourceRow,
    SUM(CASE WHEN LEN(i.SegmentValue) = i.ExpectedWidth THEN 0 ELSE 1 END) AS InvalidWidthCount,
    SUM(CASE WHEN ISJSON(i.SelectionsJson) = 1 THEN 0 ELSE 1 END) AS InvalidSelectionsJsonCount
FROM stg.SegmentCombinationImportBatch AS b
JOIN stg.SegmentCombinationImport AS i
    ON i.ImportBatchId = b.ImportBatchId
GROUP BY
    b.ImportBatchId,
    b.FamilyCode,
    b.SourceFile,
    b.ExpectedRowCount,
    b.LoadedRowCount,
    b.Status,
    i.SegmentCode;
GO

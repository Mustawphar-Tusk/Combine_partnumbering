USE PumpConfiguratorDB;
GO

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

IF OBJECT_ID(N'cfg.SegmentCombination', N'U') IS NULL
BEGIN
    CREATE TABLE cfg.SegmentCombination
    (
        SegmentCombinationId bigint IDENTITY(1,1) PRIMARY KEY,
        IdentifierSegmentId int NOT NULL,
        ConfigurationVersionId int NOT NULL,
        SourceId int NOT NULL,
        SegmentValue varchar(100) NOT NULL,
        CombinationKey nvarchar(2000) NOT NULL,
        SelectionsJson nvarchar(max) NOT NULL,
        IsActive bit NOT NULL
            CONSTRAINT DF_SegmentCombination_IsActive DEFAULT 1,
        SourceWorksheet nvarchar(200) NOT NULL,
        SourceRow int NOT NULL,
        SourceCellsJson nvarchar(max) NOT NULL,
        CreatedAt datetime2(0) NOT NULL
            CONSTRAINT DF_SegmentCombination_CreatedAt
            DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_SegmentCombination_IdentifierSegment
            FOREIGN KEY (IdentifierSegmentId)
            REFERENCES cfg.IdentifierSegment(IdentifierSegmentId),
        CONSTRAINT FK_SegmentCombination_ConfigurationVersion
            FOREIGN KEY (ConfigurationVersionId)
            REFERENCES cfg.ConfigurationVersion(ConfigurationVersionId),
        CONSTRAINT CK_SegmentCombination_SelectionsJson
            CHECK (ISJSON(SelectionsJson) = 1),
        CONSTRAINT CK_SegmentCombination_SourceCellsJson
            CHECK (ISJSON(SourceCellsJson) = 1)
    );

    CREATE UNIQUE INDEX UX_SegmentCombination_SourceId
        ON cfg.SegmentCombination
        (
            IdentifierSegmentId,
            ConfigurationVersionId,
            SourceId
        )
        WHERE IsActive = 1;

    CREATE UNIQUE INDEX UX_SegmentCombination_Key
        ON cfg.SegmentCombination
        (
            IdentifierSegmentId,
            ConfigurationVersionId,
            CombinationKey
        )
        WHERE IsActive = 1;

    CREATE INDEX IX_SegmentCombination_Value
        ON cfg.SegmentCombination(SegmentValue);
END;
GO

IF OBJECT_ID(N'stg.SegmentCombinationCandidate', N'U') IS NULL
BEGIN
    CREATE TABLE stg.SegmentCombinationCandidate
    (
        SegmentCombinationCandidateId bigint IDENTITY(1,1) PRIMARY KEY,
        CompilerRunId bigint NOT NULL,
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
        SelectionsJson nvarchar(max) NOT NULL,
        SourceCellsJson nvarchar(max) NOT NULL,
        SourceProfile nvarchar(1000) NOT NULL,
        CONSTRAINT FK_SegmentCombinationCandidate_CompilerRun
            FOREIGN KEY (CompilerRunId)
            REFERENCES stg.CompilerRun(CompilerRunId),
        CONSTRAINT CK_SegmentCombinationCandidate_SelectionsJson
            CHECK (ISJSON(SelectionsJson) = 1),
        CONSTRAINT CK_SegmentCombinationCandidate_SourceCellsJson
            CHECK (ISJSON(SourceCellsJson) = 1)
    );
END;
GO

USE PumpConfiguratorDB;
GO

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

IF OBJECT_ID(N'stg.CompilerRun', N'U') IS NULL
BEGIN
    CREATE TABLE stg.CompilerRun
    (
        CompilerRunId bigint IDENTITY(1,1) PRIMARY KEY,
        CompilerType varchar(100) NOT NULL,
        StartedAt datetime2(0) NOT NULL
            CONSTRAINT DF_CompilerRun_StartedAt DEFAULT SYSUTCDATETIME(),
        CompletedAt datetime2(0) NULL,
        Status varchar(30) NOT NULL
            CONSTRAINT DF_CompilerRun_Status DEFAULT 'Started',
        SourceReport nvarchar(1000) NULL,
        SummaryJson nvarchar(max) NULL,
        ErrorMessage nvarchar(max) NULL,
        CONSTRAINT CK_CompilerRun_Status
            CHECK (Status IN ('Started','Completed','CompletedWithIssues','Failed')),
        CONSTRAINT CK_CompilerRun_SummaryJson
            CHECK (SummaryJson IS NULL OR ISJSON(SummaryJson) = 1)
    );
END;
GO

IF OBJECT_ID(N'stg.ConfigSectionCandidate', N'U') IS NULL
BEGIN
    CREATE TABLE stg.ConfigSectionCandidate
    (
        ConfigSectionCandidateId bigint IDENTITY(1,1) PRIMARY KEY,
        CompilerRunId bigint NOT NULL,
        FamilyCode varchar(50) NOT NULL,
        WorkbookRole varchar(100) NOT NULL,
        WorksheetName nvarchar(200) NOT NULL,
        SectionCode varchar(100) NOT NULL,
        SectionName nvarchar(300) NOT NULL,
        DisplayOrder int NOT NULL,
        SequenceFrom int NULL,
        SequenceTo int NULL,
        SourceProfile nvarchar(1000) NOT NULL,
        CONSTRAINT FK_ConfigSectionCandidate_CompilerRun
            FOREIGN KEY (CompilerRunId)
            REFERENCES stg.CompilerRun(CompilerRunId)
    );
END;
GO

IF OBJECT_ID(N'stg.ConfigFieldCandidate', N'U') IS NULL
BEGIN
    CREATE TABLE stg.ConfigFieldCandidate
    (
        ConfigFieldCandidateId bigint IDENTITY(1,1) PRIMARY KEY,
        CompilerRunId bigint NOT NULL,
        FamilyCode varchar(50) NOT NULL,
        WorkbookRole varchar(100) NOT NULL,
        WorksheetName nvarchar(200) NOT NULL,
        SectionCode varchar(100) NOT NULL,
        FieldCode varchar(150) NOT NULL,
        FieldName nvarchar(500) NOT NULL,
        DisplayOrder int NOT NULL,
        SourceCell varchar(100) NULL,
        SourceSequence int NULL,
        ExtractionStrategy varchar(50) NOT NULL,
        Confidence varchar(20) NOT NULL,
        SourceProfile nvarchar(1000) NOT NULL,
        CONSTRAINT FK_ConfigFieldCandidate_CompilerRun
            FOREIGN KEY (CompilerRunId)
            REFERENCES stg.CompilerRun(CompilerRunId)
    );
END;
GO

IF OBJECT_ID(N'stg.ConfigurationModelIssue', N'U') IS NULL
BEGIN
    CREATE TABLE stg.ConfigurationModelIssue
    (
        ConfigurationModelIssueId bigint IDENTITY(1,1) PRIMARY KEY,
        CompilerRunId bigint NOT NULL,
        FamilyCode varchar(50) NOT NULL,
        Severity varchar(20) NOT NULL,
        IssueCode varchar(100) NOT NULL,
        Message nvarchar(max) NOT NULL,
        WorksheetName nvarchar(200) NULL,
        SourceReference varchar(100) NULL,
        CONSTRAINT FK_ConfigurationModelIssue_CompilerRun
            FOREIGN KEY (CompilerRunId)
            REFERENCES stg.CompilerRun(CompilerRunId),
        CONSTRAINT CK_ConfigurationModelIssue_Severity
            CHECK (Severity IN ('Info','Warning','Error','Critical'))
    );
END;
GO

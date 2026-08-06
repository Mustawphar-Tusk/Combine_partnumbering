USE PumpConfiguratorDB;
GO

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

IF OBJECT_ID(N'stg.ConfigOptionCandidate', N'U') IS NULL
BEGIN
    CREATE TABLE stg.ConfigOptionCandidate
    (
        ConfigOptionCandidateId bigint IDENTITY(1,1) PRIMARY KEY,
        CompilerRunId bigint NOT NULL,
        FamilyCode varchar(50) NOT NULL,
        WorkbookRole varchar(100) NOT NULL,
        WorksheetName nvarchar(200) NOT NULL,
        FieldCode varchar(150) NOT NULL,
        OptionCode varchar(200) NOT NULL,
        OptionDescription nvarchar(1000) NOT NULL,
        HexCode varchar(100) NULL,
        SourceCell varchar(50) NOT NULL,
        SourceRange varchar(100) NULL,
        SourceType varchar(50) NOT NULL,
        Confidence varchar(20) NOT NULL,
        SourceProfile nvarchar(1000) NOT NULL,
        CONSTRAINT FK_ConfigOptionCandidate_CompilerRun
            FOREIGN KEY (CompilerRunId)
            REFERENCES stg.CompilerRun(CompilerRunId)
    );
END;
GO

IF OBJECT_ID(N'stg.ConfigDependencyCandidate', N'U') IS NULL
BEGIN
    CREATE TABLE stg.ConfigDependencyCandidate
    (
        ConfigDependencyCandidateId bigint IDENTITY(1,1) PRIMARY KEY,
        CompilerRunId bigint NOT NULL,
        FamilyCode varchar(50) NOT NULL,
        ParentFieldCode varchar(150) NOT NULL,
        ChildFieldCode varchar(150) NOT NULL,
        DependencyType varchar(50) NOT NULL,
        SourceFormula nvarchar(max) NULL,
        SourceReference varchar(100) NOT NULL,
        Confidence varchar(20) NOT NULL,
        SourceProfile nvarchar(1000) NOT NULL,
        CONSTRAINT FK_ConfigDependencyCandidate_CompilerRun
            FOREIGN KEY (CompilerRunId)
            REFERENCES stg.CompilerRun(CompilerRunId)
    );
END;
GO

IF OBJECT_ID(N'stg.ConstraintRuleCandidate', N'U') IS NULL
BEGIN
    CREATE TABLE stg.ConstraintRuleCandidate
    (
        ConstraintRuleCandidateId bigint IDENTITY(1,1) PRIMARY KEY,
        CompilerRunId bigint NOT NULL,
        FamilyCode varchar(50) NOT NULL,
        RuleCode varchar(200) NOT NULL,
        RuleName nvarchar(500) NOT NULL,
        RuleType varchar(50) NOT NULL,
        ConditionJson nvarchar(max) NOT NULL,
        ActionJson nvarchar(max) NOT NULL,
        SourceWorkbookRole varchar(100) NOT NULL,
        SourceWorksheet nvarchar(200) NOT NULL,
        SourceReference varchar(100) NOT NULL,
        Confidence varchar(20) NOT NULL,
        SourceProfile nvarchar(1000) NOT NULL,
        CONSTRAINT FK_ConstraintRuleCandidate_CompilerRun
            FOREIGN KEY (CompilerRunId)
            REFERENCES stg.CompilerRun(CompilerRunId),
        CONSTRAINT CK_ConstraintRuleCandidate_ConditionJson
            CHECK (ISJSON(ConditionJson) = 1),
        CONSTRAINT CK_ConstraintRuleCandidate_ActionJson
            CHECK (ISJSON(ActionJson) = 1)
    );
END;
GO

IF OBJECT_ID(N'stg.LegacyInvalidMarkerDiagnostic', N'U') IS NULL
BEGIN
    CREATE TABLE stg.LegacyInvalidMarkerDiagnostic
    (
        LegacyInvalidMarkerDiagnosticId bigint IDENTITY(1,1) PRIMARY KEY,
        CompilerRunId bigint NOT NULL,
        FamilyCode varchar(50) NOT NULL,
        WorksheetName nvarchar(200) NOT NULL,
        SourceReference varchar(100) NOT NULL,
        Marker varchar(100) NOT NULL,
        Formula nvarchar(max) NULL,
        Meaning nvarchar(1000) NOT NULL,
        CONSTRAINT FK_LegacyInvalidMarkerDiagnostic_CompilerRun
            FOREIGN KEY (CompilerRunId)
            REFERENCES stg.CompilerRun(CompilerRunId)
    );
END;
GO

USE PumpConfiguratorDB;
GO

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

IF OBJECT_ID(N'cfg.PumpModelReference', N'U') IS NULL
BEGIN
    CREATE TABLE cfg.PumpModelReference
    (
        PumpModelReferenceId bigint IDENTITY(1,1) PRIMARY KEY,
        PumpFamilyId int NOT NULL,
        ConfigurationVersionId int NOT NULL,
        ModelIdentifier varchar(100) NOT NULL,
        SeriesCode varchar(100) NOT NULL,
        SizeCode varchar(100) NOT NULL,
        BaseIdentifier varchar(150) NOT NULL,
        IsActive bit NOT NULL DEFAULT 1,
        SourceWorksheet nvarchar(200) NOT NULL,
        SourceRow int NOT NULL,
        CreatedAt datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_PumpModelReference_PumpFamily
            FOREIGN KEY (PumpFamilyId) REFERENCES cfg.PumpFamily(PumpFamilyId),
        CONSTRAINT FK_PumpModelReference_ConfigurationVersion
            FOREIGN KEY (ConfigurationVersionId)
            REFERENCES cfg.ConfigurationVersion(ConfigurationVersionId)
    );

    CREATE UNIQUE INDEX UX_PumpModelReference_SeriesSize
        ON cfg.PumpModelReference
        (
            PumpFamilyId,
            ConfigurationVersionId,
            SeriesCode,
            SizeCode
        )
        WHERE IsActive = 1;
END;
GO

IF OBJECT_ID(N'cfg.IdentifierFormat', N'U') IS NULL
BEGIN
    CREATE TABLE cfg.IdentifierFormat
    (
        IdentifierFormatId int IDENTITY(1,1) PRIMARY KEY,
        PumpFamilyId int NOT NULL,
        IdentifierType varchar(30) NOT NULL,
        FormatCode varchar(100) NOT NULL,
        VersionNumber int NOT NULL,
        FormatTemplate nvarchar(500) NOT NULL,
        SegmentSeparator varchar(20) NOT NULL,
        BaseIdentifierSource varchar(100) NOT NULL,
        IsCurrent bit NOT NULL DEFAULT 0,
        CreatedAt datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_IdentifierFormat_PumpFamily
            FOREIGN KEY (PumpFamilyId) REFERENCES cfg.PumpFamily(PumpFamilyId),
        CONSTRAINT CK_IdentifierFormat_Type
            CHECK (IdentifierType IN ('PART_NUMBER','SKU')),
        CONSTRAINT UQ_IdentifierFormat_Code
            UNIQUE (PumpFamilyId, IdentifierType, FormatCode)
    );

    CREATE UNIQUE INDEX UX_IdentifierFormat_Current
        ON cfg.IdentifierFormat(PumpFamilyId, IdentifierType)
        WHERE IsCurrent = 1;
END;
GO

IF OBJECT_ID(N'cfg.IdentifierSegment', N'U') IS NULL
BEGIN
    CREATE TABLE cfg.IdentifierSegment
    (
        IdentifierSegmentId int IDENTITY(1,1) PRIMARY KEY,
        PumpFamilyId int NOT NULL,
        ConfigurationVersionId int NOT NULL,
        SegmentCode varchar(100) NOT NULL,
        SegmentName nvarchar(300) NOT NULL,
        AssemblyOrder int NOT NULL,
        ExpectedWidth int NULL,
        SourceFieldCodesJson nvarchar(max) NOT NULL,
        IsActive bit NOT NULL DEFAULT 1,
        CreatedAt datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_IdentifierSegment_PumpFamily
            FOREIGN KEY (PumpFamilyId) REFERENCES cfg.PumpFamily(PumpFamilyId),
        CONSTRAINT FK_IdentifierSegment_ConfigurationVersion
            FOREIGN KEY (ConfigurationVersionId)
            REFERENCES cfg.ConfigurationVersion(ConfigurationVersionId),
        CONSTRAINT CK_IdentifierSegment_SourceFieldCodesJson
            CHECK (ISJSON(SourceFieldCodesJson) = 1),
        CONSTRAINT UQ_IdentifierSegment
            UNIQUE (ConfigurationVersionId, SegmentCode)
    );
END;
GO

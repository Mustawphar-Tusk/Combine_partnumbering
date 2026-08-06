/*
  Phase 1 metadata-driven schema for Dean, Fybroc, and future families.
  Family behavior is represented as data. No family-specific tables are used.
*/
SET XACT_ABORT ON;
GO

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'cfg') EXEC('CREATE SCHEMA cfg');
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'price') EXEC('CREATE SCHEMA price');
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'quote') EXEC('CREATE SCHEMA quote');
GO

CREATE TABLE cfg.PumpFamily (
    PumpFamilyId int IDENTITY PRIMARY KEY,
    FamilyCode varchar(50) NOT NULL UNIQUE,
    FamilyName nvarchar(200) NOT NULL,
    IsActive bit NOT NULL CONSTRAINT DF_PumpFamily_IsActive DEFAULT (1)
);
GO

CREATE TABLE cfg.ConfigurationVersion (
    ConfigurationVersionId int IDENTITY PRIMARY KEY,
    PumpFamilyId int NOT NULL REFERENCES cfg.PumpFamily(PumpFamilyId),
    VersionNumber int NOT NULL,
    Status varchar(20) NOT NULL,
    EffectiveFrom datetime2 NULL,
    EffectiveTo datetime2 NULL,
    SourceWorkbookHash char(64) NULL,
    CONSTRAINT UQ_ConfigurationVersion UNIQUE (PumpFamilyId, VersionNumber)
);
GO

CREATE TABLE cfg.ConfigurationField (
    ConfigurationFieldId int IDENTITY PRIMARY KEY,
    ConfigurationVersionId int NOT NULL REFERENCES cfg.ConfigurationVersion(ConfigurationVersionId),
    FieldCode varchar(100) NOT NULL,
    FieldName nvarchar(300) NOT NULL,
    SectionCode varchar(100) NULL,
    DisplaySequence int NOT NULL,
    IsRequired bit NOT NULL DEFAULT (0),
    IsActive bit NOT NULL DEFAULT (1),
    CONSTRAINT UQ_ConfigurationField UNIQUE (ConfigurationVersionId, FieldCode)
);
GO

CREATE TABLE cfg.ConfigurationOption (
    ConfigurationOptionId int IDENTITY PRIMARY KEY,
    ConfigurationFieldId int NOT NULL REFERENCES cfg.ConfigurationField(ConfigurationFieldId),
    OptionCode varchar(100) NOT NULL,
    OptionDescription nvarchar(500) NOT NULL,
    HexCode varchar(50) NULL,
    DisplaySequence int NOT NULL DEFAULT (1),
    IsActive bit NOT NULL DEFAULT (1),
    CONSTRAINT UQ_ConfigurationOption UNIQUE (ConfigurationFieldId, OptionCode)
);
GO

CREATE TABLE cfg.ConstraintRule (
    ConstraintRuleId int IDENTITY PRIMARY KEY,
    ConfigurationVersionId int NOT NULL REFERENCES cfg.ConfigurationVersion(ConfigurationVersionId),
    RuleCode varchar(100) NOT NULL,
    RuleType varchar(50) NOT NULL,
    Priority int NOT NULL DEFAULT (100),
    RuleDefinitionJson nvarchar(max) NOT NULL,
    IsActive bit NOT NULL DEFAULT (1),
    CONSTRAINT CK_ConstraintRule_Json CHECK (ISJSON(RuleDefinitionJson) = 1),
    CONSTRAINT UQ_ConstraintRule UNIQUE (ConfigurationVersionId, RuleCode)
);
GO

CREATE TABLE cfg.PartNumberFormat (
    PartNumberFormatId int IDENTITY PRIMARY KEY,
    ConfigurationVersionId int NOT NULL REFERENCES cfg.ConfigurationVersion(ConfigurationVersionId),
    FormatCode varchar(100) NOT NULL,
    FormatDefinitionJson nvarchar(max) NOT NULL,
    IsActive bit NOT NULL DEFAULT (1),
    CONSTRAINT CK_PartNumberFormat_Json CHECK (ISJSON(FormatDefinitionJson) = 1)
);
GO

CREATE TABLE cfg.ConfiguredProduct (
    ConfiguredProductId bigint IDENTITY PRIMARY KEY,
    ConfigurationVersionId int NOT NULL REFERENCES cfg.ConfigurationVersion(ConfigurationVersionId),
    ConfigurationSignature char(64) NOT NULL,
    CanonicalConfigurationJson nvarchar(max) NOT NULL,
    PartNumber varchar(200) NOT NULL,
    SKU varchar(200) NOT NULL,
    CreatedAt datetime2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT CK_ConfiguredProduct_Json CHECK (ISJSON(CanonicalConfigurationJson) = 1),
    CONSTRAINT UQ_ConfiguredProduct_Signature UNIQUE (ConfigurationSignature),
    CONSTRAINT UQ_ConfiguredProduct_PartNumber UNIQUE (PartNumber),
    CONSTRAINT UQ_ConfiguredProduct_SKU UNIQUE (SKU)
);
GO

CREATE TABLE price.PriceBook (
    PriceBookId int IDENTITY PRIMARY KEY,
    PriceBookCode varchar(100) NOT NULL UNIQUE,
    CurrencyCode char(3) NOT NULL,
    EffectiveFrom datetime2 NULL,
    EffectiveTo datetime2 NULL,
    IsActive bit NOT NULL DEFAULT (1)
);
GO

CREATE TABLE price.PricingRule (
    PricingRuleId bigint IDENTITY PRIMARY KEY,
    PriceBookId int NOT NULL REFERENCES price.PriceBook(PriceBookId),
    ConfigurationVersionId int NOT NULL REFERENCES cfg.ConfigurationVersion(ConfigurationVersionId),
    RuleCode varchar(100) NOT NULL,
    Priority int NOT NULL DEFAULT (100),
    ConditionJson nvarchar(max) NOT NULL,
    UnitPrice decimal(19,4) NOT NULL,
    IsActive bit NOT NULL DEFAULT (1),
    CONSTRAINT CK_PricingRule_Json CHECK (ISJSON(ConditionJson) = 1),
    CONSTRAINT CK_PricingRule_Nonnegative CHECK (UnitPrice >= 0),
    CONSTRAINT UQ_PricingRule UNIQUE (PriceBookId, ConfigurationVersionId, RuleCode)
);
GO

CREATE TABLE quote.QuoteTemplateMapping (
    QuoteTemplateMappingId int IDENTITY PRIMARY KEY,
    ConfigurationVersionId int NOT NULL REFERENCES cfg.ConfigurationVersion(ConfigurationVersionId),
    TemplateCode varchar(100) NOT NULL,
    WorkbookSheetName nvarchar(200) NOT NULL,
    OutputMappingJson nvarchar(max) NOT NULL,
    IsActive bit NOT NULL DEFAULT (1),
    CONSTRAINT CK_QuoteTemplateMapping_Json CHECK (ISJSON(OutputMappingJson) = 1)
);
GO

CREATE TABLE quote.GenerationAudit (
    GenerationAuditId bigint IDENTITY PRIMARY KEY,
    ConfiguredProductId bigint NULL REFERENCES cfg.ConfiguredProduct(ConfiguredProductId),
    PumpFamilyCode varchar(50) NOT NULL,
    RequestJson nvarchar(max) NOT NULL,
    ResponseJson nvarchar(max) NOT NULL,
    RequestedBy nvarchar(200) NULL,
    RequestedAt datetime2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT CK_GenerationAudit_RequestJson CHECK (ISJSON(RequestJson) = 1),
    CONSTRAINT CK_GenerationAudit_ResponseJson CHECK (ISJSON(ResponseJson) = 1)
);
GO

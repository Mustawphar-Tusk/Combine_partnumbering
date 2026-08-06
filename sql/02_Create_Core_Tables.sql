SET ANSI_NULLS ON;
GO
SET QUOTED_IDENTIFIER ON;
GO
SET ANSI_PADDING ON;
GO
SET ANSI_WARNINGS ON;
GO
SET CONCAT_NULL_YIELDS_NULL ON;
GO
SET ARITHABORT ON;
GO
SET NUMERIC_ROUNDABORT OFF;
GO
USE PumpConfiguratorDB;
GO
CREATE TABLE cfg.PumpFamily(
 PumpFamilyId int IDENTITY PRIMARY KEY,
 FamilyCode varchar(50) NOT NULL UNIQUE,
 FamilyName nvarchar(200) NOT NULL,
 IsActive bit NOT NULL DEFAULT 1,
 CreatedAt datetime2 NOT NULL DEFAULT SYSUTCDATETIME()
);
CREATE TABLE cfg.ConfigurationVersion(
 ConfigurationVersionId int IDENTITY PRIMARY KEY,
 PumpFamilyId int NOT NULL REFERENCES cfg.PumpFamily(PumpFamilyId),
 VersionCode varchar(50) NOT NULL,
 SourceWorkbook nvarchar(500) NULL,
 WorkbookHash char(64) NULL,
 Status varchar(20) NOT NULL DEFAULT 'Draft',
 IsCurrent bit NOT NULL DEFAULT 0,
 PublishedAt datetime2 NULL,
 CreatedAt datetime2 NOT NULL DEFAULT SYSUTCDATETIME(),
 CONSTRAINT CK_ConfigurationVersion_Status CHECK(Status IN('Draft','Validated','Published','Retired')),
 CONSTRAINT UQ_ConfigurationVersion UNIQUE(PumpFamilyId,VersionCode)
);
CREATE UNIQUE INDEX UX_ConfigurationVersion_Current
ON cfg.ConfigurationVersion(PumpFamilyId) WHERE IsCurrent=1;

CREATE TABLE cfg.PumpSeries(
 PumpSeriesId int IDENTITY PRIMARY KEY,
 PumpFamilyId int NOT NULL REFERENCES cfg.PumpFamily(PumpFamilyId),
 ConfigurationVersionId int NOT NULL REFERENCES cfg.ConfigurationVersion(ConfigurationVersionId),
 SeriesCode varchar(100) NOT NULL,
 SeriesName nvarchar(300) NOT NULL,
 IsActive bit NOT NULL DEFAULT 1,
 CONSTRAINT UQ_PumpSeries UNIQUE(ConfigurationVersionId,SeriesCode)
);
CREATE TABLE cfg.ConfigSection(
 ConfigSectionId int IDENTITY PRIMARY KEY,
 ConfigurationVersionId int NOT NULL REFERENCES cfg.ConfigurationVersion(ConfigurationVersionId),
 SectionCode varchar(100) NOT NULL,
 SectionName nvarchar(300) NOT NULL,
 DisplayOrder int NOT NULL,
 IsActive bit NOT NULL DEFAULT 1,
 CONSTRAINT UQ_ConfigSection UNIQUE(ConfigurationVersionId,SectionCode)
);
CREATE TABLE cfg.ConfigField(
 ConfigFieldId int IDENTITY PRIMARY KEY,
 ConfigurationVersionId int NOT NULL REFERENCES cfg.ConfigurationVersion(ConfigurationVersionId),
 ConfigSectionId int NOT NULL REFERENCES cfg.ConfigSection(ConfigSectionId),
 FieldCode varchar(100) NOT NULL,
 FieldName nvarchar(300) NOT NULL,
 DataType varchar(30) NOT NULL DEFAULT 'text',
 ControlType varchar(30) NOT NULL DEFAULT 'dropdown',
 DisplayOrder int NOT NULL,
 PartNumberOrder int NULL,
 IsRequired bit NOT NULL DEFAULT 0,
 IsPartNumberField bit NOT NULL DEFAULT 0,
 AllowsMultiple bit NOT NULL DEFAULT 0,
 IsActive bit NOT NULL DEFAULT 1,
 SourceSheet nvarchar(200) NULL,
 SourceReference nvarchar(200) NULL,
 CONSTRAINT UQ_ConfigField UNIQUE(ConfigurationVersionId,FieldCode)
);
CREATE TABLE cfg.ConfigOption(
 ConfigOptionId bigint IDENTITY PRIMARY KEY,
 ConfigFieldId int NOT NULL REFERENCES cfg.ConfigField(ConfigFieldId),
 PumpSeriesId int NULL REFERENCES cfg.PumpSeries(PumpSeriesId),
 OptionCode varchar(150) NOT NULL,
 OptionDescription nvarchar(500) NOT NULL,
 HexCode varchar(100) NULL,
 PartNumberCode varchar(100) NULL,
 ERPCode varchar(100) NULL,
 DisplayOrder int NOT NULL,
 IsDefault bit NOT NULL DEFAULT 0,
 IsActive bit NOT NULL DEFAULT 1,
 EffectiveFrom date NULL,
 EffectiveTo date NULL,
 SourceSheet nvarchar(200) NULL,
 SourceReference nvarchar(200) NULL
);
CREATE UNIQUE INDEX UX_ConfigOption_FieldSeriesCode
ON cfg.ConfigOption(ConfigFieldId,PumpSeriesId,OptionCode);

CREATE TABLE cfg.ConstraintRule(
 ConstraintRuleId bigint IDENTITY PRIMARY KEY,
 ConfigurationVersionId int NOT NULL REFERENCES cfg.ConfigurationVersion(ConfigurationVersionId),
 PumpSeriesId int NULL REFERENCES cfg.PumpSeries(PumpSeriesId),
 RuleCode varchar(100) NOT NULL,
 RuleName nvarchar(300) NOT NULL,
 RuleType varchar(30) NOT NULL,
 Priority int NOT NULL DEFAULT 100,
 StopOnMatch bit NOT NULL DEFAULT 0,
 IsActive bit NOT NULL DEFAULT 1,
 CONSTRAINT UQ_ConstraintRule UNIQUE(ConfigurationVersionId,RuleCode)
);
CREATE TABLE cfg.ConstraintCondition(
 ConstraintConditionId bigint IDENTITY PRIMARY KEY,
 ConstraintRuleId bigint NOT NULL REFERENCES cfg.ConstraintRule(ConstraintRuleId),
 SequenceNo int NOT NULL,
 LogicalOperator varchar(5) NOT NULL DEFAULT 'AND',
 FieldCode varchar(100) NOT NULL,
 ComparisonOperator varchar(30) NOT NULL,
 ComparisonValue nvarchar(1000) NULL
);
CREATE TABLE cfg.ConstraintAction(
 ConstraintActionId bigint IDENTITY PRIMARY KEY,
 ConstraintRuleId bigint NOT NULL REFERENCES cfg.ConstraintRule(ConstraintRuleId),
 SequenceNo int NOT NULL,
 ActionType varchar(40) NOT NULL,
 TargetFieldCode varchar(100) NULL,
 ActionValue nvarchar(2000) NULL,
 Message nvarchar(1000) NULL
);

CREATE TABLE cfg.PartNumberFormat(
 PartNumberFormatId int IDENTITY PRIMARY KEY,
 ConfigurationVersionId int NOT NULL REFERENCES cfg.ConfigurationVersion(ConfigurationVersionId),
 FormatCode varchar(100) NOT NULL,
 Prefix varchar(100) NULL,
 Separator varchar(20) NOT NULL DEFAULT '-',
 Suffix varchar(100) NULL,
 FormatDefinition nvarchar(max) NOT NULL,
 IsActive bit NOT NULL DEFAULT 1,
 CONSTRAINT CK_PartNumberFormat_JSON CHECK(ISJSON(FormatDefinition)=1),
 CONSTRAINT UQ_PartNumberFormat UNIQUE(ConfigurationVersionId,FormatCode)
);
CREATE TABLE cfg.ConfiguredProduct(
 ConfiguredProductId bigint IDENTITY PRIMARY KEY,
 PumpFamilyId int NOT NULL REFERENCES cfg.PumpFamily(PumpFamilyId),
 ConfigurationVersionId int NOT NULL REFERENCES cfg.ConfigurationVersion(ConfigurationVersionId),
 PumpSeriesId int NULL REFERENCES cfg.PumpSeries(PumpSeriesId),
 ConfigurationSignature char(64) NOT NULL,
 PartNumber varchar(200) NOT NULL UNIQUE,
 SKUCode varchar(100) NOT NULL UNIQUE,
 CanonicalConfiguration nvarchar(max) NOT NULL,
 CreatedAt datetime2 NOT NULL DEFAULT SYSUTCDATETIME(),
 CreatedBy nvarchar(200) NULL,
 CONSTRAINT CK_ConfiguredProduct_JSON CHECK(ISJSON(CanonicalConfiguration)=1),
 CONSTRAINT UQ_ConfiguredProduct_Signature UNIQUE(PumpFamilyId,ConfigurationSignature)
);

CREATE TABLE price.PriceBook(
 PriceBookId int IDENTITY PRIMARY KEY,
 PumpFamilyId int NOT NULL REFERENCES cfg.PumpFamily(PumpFamilyId),
 PriceBookCode varchar(100) NOT NULL,
 PriceBookName nvarchar(300) NOT NULL,
 CurrencyCode char(3) NOT NULL DEFAULT 'USD',
 IsActive bit NOT NULL DEFAULT 1,
 CONSTRAINT UQ_PriceBook UNIQUE(PumpFamilyId,PriceBookCode)
);
CREATE TABLE price.PriceBookVersion(
 PriceBookVersionId int IDENTITY PRIMARY KEY,
 PriceBookId int NOT NULL REFERENCES price.PriceBook(PriceBookId),
 VersionCode varchar(50) NOT NULL,
 EffectiveFrom date NOT NULL,
 EffectiveTo date NULL,
 IsCurrent bit NOT NULL DEFAULT 0,
 SourceWorkbook nvarchar(500) NULL,
 CONSTRAINT UQ_PriceBookVersion UNIQUE(PriceBookId,VersionCode)
);
CREATE UNIQUE INDEX UX_PriceBookVersion_Current
ON price.PriceBookVersion(PriceBookId) WHERE IsCurrent=1;
CREATE TABLE price.PriceRule(
 PriceRuleId bigint IDENTITY PRIMARY KEY,
 PriceBookVersionId int NOT NULL REFERENCES price.PriceBookVersion(PriceBookVersionId),
 RuleCode varchar(100) NOT NULL,
 RuleName nvarchar(300) NOT NULL,
 RuleType varchar(30) NOT NULL,
 Priority int NOT NULL DEFAULT 100,
 Amount decimal(19,4) NOT NULL DEFAULT 0,
 IsActive bit NOT NULL DEFAULT 1,
 CONSTRAINT UQ_PriceRule UNIQUE(PriceBookVersionId,RuleCode)
);
CREATE TABLE price.PriceCondition(
 PriceConditionId bigint IDENTITY PRIMARY KEY,
 PriceRuleId bigint NOT NULL REFERENCES price.PriceRule(PriceRuleId),
 SequenceNo int NOT NULL,
 FieldCode varchar(100) NOT NULL,
 ComparisonOperator varchar(30) NOT NULL,
 ComparisonValue nvarchar(1000) NULL
);

CREATE TABLE quote.QuoteTemplate(
 QuoteTemplateId int IDENTITY PRIMARY KEY,
 PumpFamilyId int NOT NULL REFERENCES cfg.PumpFamily(PumpFamilyId),
 TemplateCode varchar(100) NOT NULL,
 TemplateName nvarchar(300) NOT NULL,
 WorkbookName nvarchar(500) NULL,
 WorksheetName nvarchar(200) NOT NULL,
 IsActive bit NOT NULL DEFAULT 1,
 CONSTRAINT UQ_QuoteTemplate UNIQUE(PumpFamilyId,TemplateCode)
);
CREATE TABLE quote.QuoteTemplateMapping(
 QuoteTemplateMappingId bigint IDENTITY PRIMARY KEY,
 QuoteTemplateId int NOT NULL REFERENCES quote.QuoteTemplate(QuoteTemplateId),
 OutputKey varchar(100) NOT NULL,
 ExcelTargetType varchar(30) NOT NULL,
 ExcelTargetReference nvarchar(200) NOT NULL,
 DisplayOrder int NOT NULL,
 IsRequired bit NOT NULL DEFAULT 0,
 CONSTRAINT UQ_QuoteTemplateMapping UNIQUE(QuoteTemplateId,OutputKey)
);
CREATE TABLE quote.QuoteHeader(
 QuoteId bigint IDENTITY PRIMARY KEY,
 QuoteNumber AS('Q-'+RIGHT('000000'+CONVERT(varchar(20),QuoteId),6)) PERSISTED,
 CustomerName nvarchar(300) NULL,
 CurrencyCode char(3) NOT NULL DEFAULT 'USD',
 CreatedAt datetime2 NOT NULL DEFAULT SYSUTCDATETIME(),
 CreatedBy nvarchar(200) NULL
);
CREATE TABLE quote.QuoteLine(
 QuoteLineId bigint IDENTITY PRIMARY KEY,
 QuoteId bigint NOT NULL REFERENCES quote.QuoteHeader(QuoteId),
 ConfiguredProductId bigint NOT NULL REFERENCES cfg.ConfiguredProduct(ConfiguredProductId),
 Quantity decimal(18,4) NOT NULL DEFAULT 1,
 UnitPrice decimal(19,4) NOT NULL DEFAULT 0,
 ExtendedPrice AS(Quantity*UnitPrice) PERSISTED,
 PricingStatus varchar(30) NOT NULL DEFAULT 'not_found'
);

CREATE TABLE stg.ImportBatch(
 ImportBatchId bigint IDENTITY PRIMARY KEY,
 PumpFamilyId int NULL REFERENCES cfg.PumpFamily(PumpFamilyId),
 ImportType varchar(50) NOT NULL,
 SourcePath nvarchar(1000) NOT NULL,
 SourceFileName nvarchar(500) NOT NULL,
 SourceHash char(64) NOT NULL,
 Status varchar(30) NOT NULL DEFAULT 'Created',
 StartedAt datetime2 NOT NULL DEFAULT SYSUTCDATETIME(),
 CompletedAt datetime2 NULL,
 ErrorMessage nvarchar(max) NULL
);
CREATE TABLE stg.RawCell(
 RawCellId bigint IDENTITY PRIMARY KEY,
 ImportBatchId bigint NOT NULL REFERENCES stg.ImportBatch(ImportBatchId),
 WorksheetName nvarchar(200) NOT NULL,
 CellReference varchar(50) NOT NULL,
 RawValue nvarchar(max) NULL,
 Formula nvarchar(max) NULL,
 DataType varchar(20) NULL
);
CREATE TABLE stg.ExtractionIssue(
 ExtractionIssueId bigint IDENTITY PRIMARY KEY,
 ImportBatchId bigint NOT NULL REFERENCES stg.ImportBatch(ImportBatchId),
 Severity varchar(20) NOT NULL,
 IssueCode varchar(100) NOT NULL,
 WorksheetName nvarchar(200) NULL,
 CellReference varchar(50) NULL,
 Message nvarchar(max) NOT NULL,
 CreatedAt datetime2 NOT NULL DEFAULT SYSUTCDATETIME()
);
CREATE TABLE audit.ApiRequest(
 ApiRequestId bigint IDENTITY PRIMARY KEY,
 CorrelationId uniqueidentifier NOT NULL DEFAULT NEWID(),
 Endpoint nvarchar(300) NOT NULL,
 RequestBody nvarchar(max) NULL,
 ResponseStatus int NULL,
 ResponseBody nvarchar(max) NULL,
 RequestedAt datetime2 NOT NULL DEFAULT SYSUTCDATETIME(),
 CompletedAt datetime2 NULL,
 RequestedBy nvarchar(200) NULL
);
GO


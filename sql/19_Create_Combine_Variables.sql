-- Combine Variables (Rev0.3) — two distinct shapes.
-- Source: docs/evidence/F120/FYBROC_MOTOR_CONSTRAINT_MODEL.json
--   combine_variable_tables    -> cfg.CombineVariable      (composite-key -> component values)
--   combine_value_domain_tables -> cfg.CombineValueDomain  (per-attribute value lists)

-- (a) key->value decomposition tables (MotorHpRpm, MotorMfg, WettedHardware)
IF OBJECT_ID(N'cfg.CombineVariable', N'U') IS NULL
BEGIN
    CREATE TABLE cfg.CombineVariable
    (
        CombineVariableId bigint IDENTITY(1,1) PRIMARY KEY,
        MetadataPublicationId bigint NOT NULL,
        PumpFamilyId int NOT NULL,
        TableName varchar(60) NOT NULL,       -- e.g. MotorHpRpm_to_HpAndRpm
        KeyField varchar(100) NOT NULL,        -- composite key field header
        KeyValue nvarchar(200) NOT NULL,       -- e.g. "1-1200"
        ValueField varchar(100) NOT NULL,      -- component field header
        ValueValue nvarchar(200) NULL,         -- decomposed component value
        IsActive bit NOT NULL DEFAULT 1,
        CreatedAt datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_CombineVariable_Publication
            FOREIGN KEY (MetadataPublicationId)
            REFERENCES cfg.MetadataPublication(MetadataPublicationId),
        CONSTRAINT FK_CombineVariable_Family
            FOREIGN KEY (PumpFamilyId)
            REFERENCES cfg.PumpFamily(PumpFamilyId)
    );

    CREATE INDEX IX_CombineVariable_Lookup
        ON cfg.CombineVariable
        (MetadataPublicationId, PumpFamilyId, TableName, KeyValue)
        INCLUDE (ValueField, ValueValue)
        WHERE IsActive = 1;
END;
GO

-- (b) per-attribute value domains (the MotorType region)
IF OBJECT_ID(N'cfg.CombineValueDomain', N'U') IS NULL
BEGIN
    CREATE TABLE cfg.CombineValueDomain
    (
        CombineValueDomainId bigint IDENTITY(1,1) PRIMARY KEY,
        MetadataPublicationId bigint NOT NULL,
        PumpFamilyId int NOT NULL,
        TableName varchar(60) NOT NULL,        -- e.g. MotorType_domains
        AttributeName varchar(100) NOT NULL,    -- e.g. F_MotorHp
        AttributeValue nvarchar(200) NOT NULL,  -- one valid value
        SortOrder int NOT NULL,                 -- workbook order within the domain
        IsActive bit NOT NULL DEFAULT 1,
        CreatedAt datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_CombineValueDomain_Publication
            FOREIGN KEY (MetadataPublicationId)
            REFERENCES cfg.MetadataPublication(MetadataPublicationId),
        CONSTRAINT FK_CombineValueDomain_Family
            FOREIGN KEY (PumpFamilyId)
            REFERENCES cfg.PumpFamily(PumpFamilyId)
    );

    CREATE INDEX IX_CombineValueDomain_Lookup
        ON cfg.CombineValueDomain
        (MetadataPublicationId, PumpFamilyId, TableName, AttributeName, SortOrder)
        INCLUDE (AttributeValue)
        WHERE IsActive = 1;
END;
GO

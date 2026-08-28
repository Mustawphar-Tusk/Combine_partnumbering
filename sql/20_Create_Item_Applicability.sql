-- cfg.ItemApplicability: Rev0.3 Items sheet field applicability.
-- Source: docs/evidence/F120/FYBROC_ITEMS_HIERARCHY_MODEL.json (items.rows,
-- 467 item records). Normalized to one row per (series, item, applicable field)
-- so the runtime can query "which fields apply to this series/item".
IF OBJECT_ID(N'cfg.ItemApplicability', N'U') IS NULL
BEGIN
    CREATE TABLE cfg.ItemApplicability
    (
        ItemApplicabilityId bigint IDENTITY(1,1) PRIMARY KEY,
        MetadataPublicationId bigint NOT NULL,
        PumpFamilyId int NOT NULL,
        SeriesCode varchar(50) NOT NULL,
        ItemCode varchar(50) NOT NULL,
        FieldCode varchar(100) NOT NULL,   -- an F_* field that applies to this item
        IsActive bit NOT NULL DEFAULT 1,
        CreatedAt datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_ItemApplicability_Publication
            FOREIGN KEY (MetadataPublicationId)
            REFERENCES cfg.MetadataPublication(MetadataPublicationId),
        CONSTRAINT FK_ItemApplicability_Family
            FOREIGN KEY (PumpFamilyId)
            REFERENCES cfg.PumpFamily(PumpFamilyId)
    );

    CREATE INDEX IX_ItemApplicability_Lookup
        ON cfg.ItemApplicability
        (MetadataPublicationId, PumpFamilyId, SeriesCode, ItemCode)
        INCLUDE (FieldCode)
        WHERE IsActive = 1;
END;
GO

-- cfg.ItemRegistry: the full set of (series, item) records from the Items sheet
-- INCLUDING items with zero applicable fields (208 of 467). ItemApplicability
-- only carries items that have >=1 applicable field, so this registry preserves
-- the existence of every item record so none are silently lost.
IF OBJECT_ID(N'cfg.ItemRegistry', N'U') IS NULL
BEGIN
    CREATE TABLE cfg.ItemRegistry
    (
        ItemRegistryId bigint IDENTITY(1,1) PRIMARY KEY,
        MetadataPublicationId bigint NOT NULL,
        PumpFamilyId int NOT NULL,
        SeriesCode varchar(50) NOT NULL,
        ItemCode varchar(50) NOT NULL,
        ApplicableFieldCount int NOT NULL,
        IsActive bit NOT NULL DEFAULT 1,
        CreatedAt datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_ItemRegistry_Publication
            FOREIGN KEY (MetadataPublicationId)
            REFERENCES cfg.MetadataPublication(MetadataPublicationId),
        CONSTRAINT FK_ItemRegistry_Family
            FOREIGN KEY (PumpFamilyId)
            REFERENCES cfg.PumpFamily(PumpFamilyId)
    );

    CREATE UNIQUE INDEX UX_ItemRegistry_Item
        ON cfg.ItemRegistry
        (MetadataPublicationId, PumpFamilyId, SeriesCode, ItemCode)
        WHERE IsActive = 1;
END;
GO

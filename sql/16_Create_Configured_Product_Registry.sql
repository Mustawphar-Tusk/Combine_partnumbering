USE PumpConfiguratorDB;
GO

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
SET XACT_ABORT ON;
GO

IF OBJECT_ID(N'cfg.ConfiguredProductRegistry', N'U') IS NULL
BEGIN
    CREATE TABLE cfg.ConfiguredProductRegistry
    (
        ConfiguredProductRegistryId bigint IDENTITY(1,1) NOT NULL
            CONSTRAINT PK_ConfiguredProductRegistry PRIMARY KEY,
        PumpFamilyId int NOT NULL,
        ConfigurationSignature char(64) NOT NULL,
        SelectionHash binary(32) NOT NULL,
        PartNumber varchar(200) NOT NULL,
        SKU varchar(200) NOT NULL,
        CanonicalConfigurationJson nvarchar(max) NOT NULL,
        SelectionsJson nvarchar(max) NOT NULL,
        SegmentsJson nvarchar(max) NOT NULL,
        RuntimeRevision varchar(500) NOT NULL,
        MetadataPublicationId bigint NOT NULL,
        SeriesBatchId bigint NULL,
        CombinationBatchId bigint NULL,
        DependencyBatchId bigint NULL,
        CreatedAt datetime2(0) NOT NULL
            CONSTRAINT DF_ConfiguredProductRegistry_CreatedAt
            DEFAULT SYSUTCDATETIME(),
        CreatedBy nvarchar(200) NULL,
        LastRequestedAt datetime2(0) NOT NULL
            CONSTRAINT DF_ConfiguredProductRegistry_LastRequestedAt
            DEFAULT SYSUTCDATETIME(),
        LastRequestedBy nvarchar(200) NULL,
        RequestCount bigint NOT NULL
            CONSTRAINT DF_ConfiguredProductRegistry_RequestCount
            DEFAULT (1),
        RowVersion rowversion NOT NULL,
        CONSTRAINT FK_ConfiguredProductRegistry_PumpFamily
            FOREIGN KEY (PumpFamilyId)
            REFERENCES cfg.PumpFamily(PumpFamilyId),
        CONSTRAINT CK_ConfiguredProductRegistry_Signature
            CHECK (
                LEN(ConfigurationSignature) = 64
                AND ConfigurationSignature NOT LIKE '%[^0-9A-Fa-f]%'
            ),
        CONSTRAINT CK_ConfiguredProductRegistry_CanonicalJson
            CHECK (ISJSON(CanonicalConfigurationJson) = 1),
        CONSTRAINT CK_ConfiguredProductRegistry_SelectionsJson
            CHECK (ISJSON(SelectionsJson) = 1),
        CONSTRAINT CK_ConfiguredProductRegistry_SegmentsJson
            CHECK (ISJSON(SegmentsJson) = 1),
        CONSTRAINT CK_ConfiguredProductRegistry_RequestCount
            CHECK (RequestCount >= 1)
    );

    CREATE UNIQUE INDEX UX_ConfiguredProductRegistry_FamilySignature
        ON cfg.ConfiguredProductRegistry
        (
            PumpFamilyId,
            ConfigurationSignature
        );

    CREATE UNIQUE INDEX UX_ConfiguredProductRegistry_PartNumber
        ON cfg.ConfiguredProductRegistry(PartNumber);

    CREATE UNIQUE INDEX UX_ConfiguredProductRegistry_SKU
        ON cfg.ConfiguredProductRegistry(SKU);
END;
GO

IF OBJECT_ID(N'cfg.ConfiguredProductSelection', N'U') IS NULL
BEGIN
    CREATE TABLE cfg.ConfiguredProductSelection
    (
        ConfiguredProductSelectionId bigint IDENTITY(1,1) NOT NULL
            CONSTRAINT PK_ConfiguredProductSelection PRIMARY KEY,
        ConfiguredProductRegistryId bigint NOT NULL,
        SelectionSequence int NOT NULL,
        FieldCode varchar(100) NOT NULL,
        DisplayValue nvarchar(500) NOT NULL,
        CONSTRAINT FK_ConfiguredProductSelection_Registry
            FOREIGN KEY (ConfiguredProductRegistryId)
            REFERENCES cfg.ConfiguredProductRegistry
                (ConfiguredProductRegistryId)
            ON DELETE CASCADE,
        CONSTRAINT UQ_ConfiguredProductSelection_Field
            UNIQUE (
                ConfiguredProductRegistryId,
                FieldCode
            ),
        CONSTRAINT UQ_ConfiguredProductSelection_Sequence
            UNIQUE (
                ConfiguredProductRegistryId,
                SelectionSequence
            ),
        CONSTRAINT CK_ConfiguredProductSelection_Sequence
            CHECK (SelectionSequence > 0)
    );
END;
GO

IF OBJECT_ID(N'cfg.ConfiguredProductSegment', N'U') IS NULL
BEGIN
    CREATE TABLE cfg.ConfiguredProductSegment
    (
        ConfiguredProductSegmentId bigint IDENTITY(1,1) NOT NULL
            CONSTRAINT PK_ConfiguredProductSegment PRIMARY KEY,
        ConfiguredProductRegistryId bigint NOT NULL,
        SegmentSequence int NOT NULL,
        SegmentCode varchar(100) NOT NULL,
        SegmentValue varchar(200) NOT NULL,
        ResolutionType varchar(50) NOT NULL,
        SourceId bigint NULL,
        SourceIdsJson nvarchar(max) NOT NULL,
        CONSTRAINT FK_ConfiguredProductSegment_Registry
            FOREIGN KEY (ConfiguredProductRegistryId)
            REFERENCES cfg.ConfiguredProductRegistry
                (ConfiguredProductRegistryId)
            ON DELETE CASCADE,
        CONSTRAINT UQ_ConfiguredProductSegment_Code
            UNIQUE (
                ConfiguredProductRegistryId,
                SegmentCode
            ),
        CONSTRAINT UQ_ConfiguredProductSegment_Sequence
            UNIQUE (
                ConfiguredProductRegistryId,
                SegmentSequence
            ),
        CONSTRAINT CK_ConfiguredProductSegment_Sequence
            CHECK (SegmentSequence > 0),
        CONSTRAINT CK_ConfiguredProductSegment_SourceIdsJson
            CHECK (ISJSON(SourceIdsJson) = 1)
    );
END;
GO

IF OBJECT_ID(N'cfg.ConfiguredProductRequestAudit', N'U') IS NULL
BEGIN
    CREATE TABLE cfg.ConfiguredProductRequestAudit
    (
        ConfiguredProductRequestAuditId bigint IDENTITY(1,1) NOT NULL
            CONSTRAINT PK_ConfiguredProductRequestAudit PRIMARY KEY,
        ConfiguredProductRegistryId bigint NOT NULL,
        WasCreated bit NOT NULL,
        RuntimeRevision varchar(500) NOT NULL,
        RequestedAt datetime2(0) NOT NULL
            CONSTRAINT DF_ConfiguredProductRequestAudit_RequestedAt
            DEFAULT SYSUTCDATETIME(),
        RequestedBy nvarchar(200) NULL,
        CONSTRAINT FK_ConfiguredProductRequestAudit_Registry
            FOREIGN KEY (ConfiguredProductRegistryId)
            REFERENCES cfg.ConfiguredProductRegistry
                (ConfiguredProductRegistryId)
    );

    CREATE INDEX IX_ConfiguredProductRequestAudit_RegistryRequestedAt
        ON cfg.ConfiguredProductRequestAudit
        (
            ConfiguredProductRegistryId,
            RequestedAt DESC
        );
END;
GO

CREATE OR ALTER PROCEDURE cfg.usp_PersistConfiguredProduct
    @FamilyCode varchar(50),
    @ConfigurationSignature char(64),
    @PartNumber varchar(200),
    @SKU varchar(200),
    @CanonicalConfigurationJson nvarchar(max),
    @SelectionsJson nvarchar(max),
    @SegmentsJson nvarchar(max),
    @RuntimeRevision varchar(500),
    @MetadataPublicationId bigint,
    @SeriesBatchId bigint = NULL,
    @CombinationBatchId bigint = NULL,
    @DependencyBatchId bigint = NULL,
    @RequestedBy nvarchar(200) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF @FamilyCode IS NULL OR LTRIM(RTRIM(@FamilyCode)) = ''
        THROW 51000, 'FamilyCode is required.', 1;

    IF @ConfigurationSignature IS NULL
       OR LEN(@ConfigurationSignature) <> 64
       OR @ConfigurationSignature LIKE '%[^0-9A-Fa-f]%'
        THROW 51001,
            'ConfigurationSignature must be a 64-character hexadecimal SHA-256 value.',
            1;

    IF @PartNumber IS NULL OR LTRIM(RTRIM(@PartNumber)) = ''
        THROW 51002, 'PartNumber is required.', 1;

    IF @SKU IS NULL OR LTRIM(RTRIM(@SKU)) = ''
        THROW 51003, 'SKU is required.', 1;

    IF ISJSON(@CanonicalConfigurationJson) <> 1
        THROW 51004, 'CanonicalConfigurationJson must be valid JSON.', 1;

    IF ISJSON(@SelectionsJson) <> 1
        THROW 51005, 'SelectionsJson must be valid JSON.', 1;

    IF ISJSON(@SegmentsJson) <> 1
        THROW 51006, 'SegmentsJson must be valid JSON.', 1;

    IF NOT EXISTS (SELECT 1 FROM OPENJSON(@SelectionsJson))
        THROW 51007, 'SelectionsJson must contain at least one selection.', 1;

    IF NOT EXISTS (SELECT 1 FROM OPENJSON(@SegmentsJson))
        THROW 51008, 'SegmentsJson must contain at least one segment.', 1;

    DECLARE
        @PumpFamilyId int,
        @ConfiguredProductRegistryId bigint,
        @WasCreated bit = 0,
        @LockResult int,
        @LockResource nvarchar(255),
        @ExistingPartNumber varchar(200),
        @ExistingSKU varchar(200),
        @ExistingSelectionHash binary(32),
        @SelectionHash binary(32);

    SET @SelectionHash = HASHBYTES(
        'SHA2_256',
        CONVERT(varbinary(max), @SelectionsJson)
    );

    SELECT @PumpFamilyId = PumpFamilyId
    FROM cfg.PumpFamily
    WHERE FamilyCode = @FamilyCode
      AND IsActive = 1;

    IF @PumpFamilyId IS NULL
        THROW 51009,
            'An active pump family was not found for FamilyCode.',
            1;

    SET @LockResource = CONCAT(
        N'ConfiguredProduct:',
        @FamilyCode,
        N':',
        @ConfigurationSignature
    );

    BEGIN TRANSACTION;

    EXEC @LockResult = sys.sp_getapplock
        @Resource = @LockResource,
        @LockMode = 'Exclusive',
        @LockOwner = 'Transaction',
        @LockTimeout = 15000;

    IF @LockResult < 0
        THROW 51010,
            'Unable to acquire the configured-product persistence lock.',
            1;

    SELECT
        @ConfiguredProductRegistryId = ConfiguredProductRegistryId,
        @ExistingPartNumber = PartNumber,
        @ExistingSKU = SKU,
        @ExistingSelectionHash = SelectionHash
    FROM cfg.ConfiguredProductRegistry WITH (UPDLOCK, HOLDLOCK)
    WHERE PumpFamilyId = @PumpFamilyId
      AND ConfigurationSignature = @ConfigurationSignature;

    IF @ConfiguredProductRegistryId IS NOT NULL
    BEGIN
        IF @ExistingSelectionHash <> @SelectionHash
            THROW 51011,
                'The configuration signature already exists with a different selection payload.',
                1;

        IF @ExistingPartNumber <> @PartNumber
            THROW 51012,
                'The configuration signature already exists with a different Part Number.',
                1;

        IF @ExistingSKU <> @SKU
            THROW 51013,
                'The configuration signature already exists with a different SKU.',
                1;

        UPDATE cfg.ConfiguredProductRegistry
        SET
            LastRequestedAt = SYSUTCDATETIME(),
            LastRequestedBy = @RequestedBy,
            RequestCount = RequestCount + 1
        WHERE ConfiguredProductRegistryId = @ConfiguredProductRegistryId;
    END
    ELSE
    BEGIN
        IF EXISTS
        (
            SELECT 1
            FROM cfg.ConfiguredProductRegistry WITH (UPDLOCK, HOLDLOCK)
            WHERE PartNumber = @PartNumber
        )
            THROW 51014,
                'The generated Part Number is already assigned to another configuration.',
                1;

        IF EXISTS
        (
            SELECT 1
            FROM cfg.ConfiguredProductRegistry WITH (UPDLOCK, HOLDLOCK)
            WHERE SKU = @SKU
        )
            THROW 51015,
                'The generated SKU is already assigned to another configuration.',
                1;

        INSERT INTO cfg.ConfiguredProductRegistry
        (
            PumpFamilyId,
            ConfigurationSignature,
            SelectionHash,
            PartNumber,
            SKU,
            CanonicalConfigurationJson,
            SelectionsJson,
            SegmentsJson,
            RuntimeRevision,
            MetadataPublicationId,
            SeriesBatchId,
            CombinationBatchId,
            DependencyBatchId,
            CreatedBy,
            LastRequestedBy
        )
        VALUES
        (
            @PumpFamilyId,
            @ConfigurationSignature,
            @SelectionHash,
            @PartNumber,
            @SKU,
            @CanonicalConfigurationJson,
            @SelectionsJson,
            @SegmentsJson,
            @RuntimeRevision,
            @MetadataPublicationId,
            @SeriesBatchId,
            @CombinationBatchId,
            @DependencyBatchId,
            @RequestedBy,
            @RequestedBy
        );

        SET @ConfiguredProductRegistryId = SCOPE_IDENTITY();

        INSERT INTO cfg.ConfiguredProductSelection
        (
            ConfiguredProductRegistryId,
            SelectionSequence,
            FieldCode,
            DisplayValue
        )
        SELECT
            @ConfiguredProductRegistryId,
            selection.SelectionSequence,
            selection.FieldCode,
            selection.DisplayValue
        FROM OPENJSON(@SelectionsJson)
        WITH
        (
            SelectionSequence int '$.selection_sequence',
            FieldCode varchar(100) '$.field_code',
            DisplayValue nvarchar(500) '$.display_value'
        ) AS selection;

        IF @@ROWCOUNT = 0
            THROW 51016, 'No configuration selections were persisted.', 1;

        INSERT INTO cfg.ConfiguredProductSegment
        (
            ConfiguredProductRegistryId,
            SegmentSequence,
            SegmentCode,
            SegmentValue,
            ResolutionType,
            SourceId,
            SourceIdsJson
        )
        SELECT
            @ConfiguredProductRegistryId,
            segment.SegmentSequence,
            segment.SegmentCode,
            segment.SegmentValue,
            segment.ResolutionType,
            segment.SourceId,
            segment.SourceIdsJson
        FROM OPENJSON(@SegmentsJson)
        WITH
        (
            SegmentSequence int '$.segment_sequence',
            SegmentCode varchar(100) '$.segment_code',
            SegmentValue varchar(200) '$.segment_value',
            ResolutionType varchar(50) '$.resolution_type',
            SourceId bigint '$.source_id',
            SourceIdsJson nvarchar(max) '$.source_ids_json'
        ) AS segment;

        IF @@ROWCOUNT = 0
            THROW 51017, 'No identifier segments were persisted.', 1;

        SET @WasCreated = 1;
    END;

    INSERT INTO cfg.ConfiguredProductRequestAudit
    (
        ConfiguredProductRegistryId,
        WasCreated,
        RuntimeRevision,
        RequestedBy
    )
    VALUES
    (
        @ConfiguredProductRegistryId,
        @WasCreated,
        @RuntimeRevision,
        @RequestedBy
    );

    COMMIT TRANSACTION;

    SELECT
        registry.ConfiguredProductRegistryId,
        registry.ConfigurationSignature,
        registry.PartNumber,
        registry.SKU,
        registry.RuntimeRevision,
        registry.MetadataPublicationId,
        registry.SeriesBatchId,
        registry.CombinationBatchId,
        registry.DependencyBatchId,
        registry.CreatedAt,
        registry.LastRequestedAt,
        registry.RequestCount,
        @WasCreated AS WasCreated
    FROM cfg.ConfiguredProductRegistry AS registry
    WHERE registry.ConfiguredProductRegistryId =
        @ConfiguredProductRegistryId;
END;
GO

CREATE OR ALTER VIEW cfg.vw_ConfiguredProductRegistry
AS
SELECT
    registry.ConfiguredProductRegistryId,
    family.FamilyCode,
    family.FamilyName,
    registry.ConfigurationSignature,
    registry.PartNumber,
    registry.SKU,
    registry.RuntimeRevision,
    registry.MetadataPublicationId,
    registry.SeriesBatchId,
    registry.CombinationBatchId,
    registry.DependencyBatchId,
    registry.CreatedAt,
    registry.CreatedBy,
    registry.LastRequestedAt,
    registry.LastRequestedBy,
    registry.RequestCount,
    (
        SELECT COUNT_BIG(*)
        FROM cfg.ConfiguredProductSelection AS selection
        WHERE selection.ConfiguredProductRegistryId =
            registry.ConfiguredProductRegistryId
    ) AS SelectionCount,
    (
        SELECT COUNT_BIG(*)
        FROM cfg.ConfiguredProductSegment AS segment
        WHERE segment.ConfiguredProductRegistryId =
            registry.ConfiguredProductRegistryId
    ) AS SegmentCount
FROM cfg.ConfiguredProductRegistry AS registry
INNER JOIN cfg.PumpFamily AS family
    ON family.PumpFamilyId = registry.PumpFamilyId;
GO

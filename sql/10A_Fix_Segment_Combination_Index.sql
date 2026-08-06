USE PumpConfiguratorDB;
GO

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
GO

IF EXISTS
(
    SELECT 1
    FROM sys.indexes
    WHERE name = 'UX_SegmentCombination_Key'
      AND object_id = OBJECT_ID('cfg.SegmentCombination')
)
BEGIN
    DROP INDEX UX_SegmentCombination_Key
        ON cfg.SegmentCombination;
END;
GO

IF COL_LENGTH(
    'cfg.SegmentCombination',
    'CombinationKeyHash'
) IS NULL
BEGIN
    ALTER TABLE cfg.SegmentCombination
    ADD CombinationKeyHash AS
        CONVERT(
            binary(32),
            HASHBYTES(
                'SHA2_256',
                CONVERT(varbinary(max), CombinationKey)
            )
        ) PERSISTED;
END;
GO

IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes
    WHERE name = N'UX_SegmentCombination_KeyHash'
      AND object_id = OBJECT_ID(N'cfg.SegmentCombination')
)
BEGIN
    CREATE UNIQUE INDEX UX_SegmentCombination_KeyHash
        ON cfg.SegmentCombination
        (
            IdentifierSegmentId,
            ConfigurationVersionId,
            CombinationKeyHash
        )
        WHERE IsActive = 1;
END;
GO

USE PumpConfiguratorDB;
GO

DECLARE @ImportBatchId bigint =
(
    SELECT MAX(ImportBatchId)
    FROM stg.SegmentCombinationImportBatch
    WHERE FamilyCode = 'FYBROC'
);

SELECT *
FROM stg.SegmentCombinationImportBatch
WHERE ImportBatchId = @ImportBatchId;

SELECT *
FROM stg.vw_SegmentCombinationImportValidation
WHERE ImportBatchId = @ImportBatchId
ORDER BY SegmentCode;

SELECT SegmentCode, COUNT_BIG(*) AS DuplicateSourceIdGroups
FROM
(
    SELECT SegmentCode, SourceId
    FROM stg.SegmentCombinationImport
    WHERE ImportBatchId = @ImportBatchId
    GROUP BY SegmentCode, SourceId
    HAVING COUNT_BIG(*) > 1
) AS d
GROUP BY SegmentCode;

SELECT SegmentCode, COUNT_BIG(*) AS DuplicateCombinationGroups
FROM
(
    SELECT SegmentCode, CombinationKeyHash
    FROM stg.SegmentCombinationImport
    WHERE ImportBatchId = @ImportBatchId
    GROUP BY SegmentCode, CombinationKeyHash
    HAVING COUNT_BIG(*) > 1
) AS d
GROUP BY SegmentCode;
GO

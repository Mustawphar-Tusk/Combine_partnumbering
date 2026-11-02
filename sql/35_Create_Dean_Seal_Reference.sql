/* ================================================================
   DEAN REVISION D-R1 - SEAL REFERENCE TABLE (capture-only)
   ----------------------------------------------------------------
   ADDITIVE ONLY. New table cfg.DeanSealReference captures the new
   per-series "Seal Reference Table" column from the revised
   PumpConfiguration_Logic_0.1 'Pump Constraints' sheet (column 594).
   Each Dean series maps to a seal-reference key (a shaft-size family:
   e.g. '1.750" Shafts', plus 'Misc.' / 'X'), pointing to the seal
   configuration reference compatible with that series.

   This is a REFERENCE only: it is NOT wired into the Dean part number
   and does NOT affect cfg.SeriesFieldOption / FeasibleConstraint /
   stg.SegmentCombinationImport. It exists to guide the upcoming seal
   configuration/spec work. Dean-only; Fybroc untouched.
   ================================================================ */

SET NOCOUNT ON;
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

USE PumpConfiguratorDB;
GO

IF OBJECT_ID('cfg.DeanSealReference', 'U') IS NULL
BEGIN
    CREATE TABLE cfg.DeanSealReference (
        DeanSealReferenceId INT IDENTITY(1,1) NOT NULL
            CONSTRAINT PK_cfg_DeanSealReference PRIMARY KEY,
        SeriesCode   VARCHAR(40) NOT NULL,
        SealRefKey   NVARCHAR(80) NOT NULL,   -- e.g. '1.750" Shafts', 'Misc.', 'X'
        SourceRow    INT NULL,                -- Pump Constraints row it came from
        LoadedAt     DATETIME2(3) NOT NULL
            CONSTRAINT DF_cfg_DeanSealReference_At DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT UQ_cfg_DeanSealReference_Series UNIQUE (SeriesCode)
    );
END
GO

/* usp_ListDeanSealReference - the per-series seal-reference map. */
CREATE OR ALTER PROCEDURE cfg.usp_ListDeanSealReference
AS
BEGIN
    SET NOCOUNT ON;
    SELECT SeriesCode, SealRefKey, SourceRow, LoadedAt
    FROM cfg.DeanSealReference
    ORDER BY SeriesCode;
END;
GO

PRINT 'DEAN D-R1: cfg.DeanSealReference + usp_ListDeanSealReference created (additive).';
GO

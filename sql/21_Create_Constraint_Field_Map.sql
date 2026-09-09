-- cfg.ConstraintFieldMap
--
-- Bridges the Feasible Constraint sheet's field LABELS (e.g. "Alt Size",
-- "CouplingGuard", "C-Face Adapter") to the runtime SFO FieldCode vocabulary
-- (e.g. ALT_SIZE, COUPLING_GUARD, C_FACE_ADAPTOR) used by cfg.SeriesFieldOption
-- and the evaluate endpoint.
--
-- The evaluate endpoint's feasible-constraint enforcement looks up this table
-- to translate between the two vocabularies. Without it, that enforcement is a
-- no-op (the lookup returns nothing and no options are filtered). The map is
-- bidirectional in use: SFOFieldCode -> ConstraintFieldName and back.
--
-- Idempotent.

IF OBJECT_ID('cfg.ConstraintFieldMap', 'U') IS NULL
BEGIN
    CREATE TABLE cfg.ConstraintFieldMap (
        ConstraintFieldMapId int IDENTITY(1,1) PRIMARY KEY,
        SFOFieldCode        varchar(100) NOT NULL,
        ConstraintFieldName varchar(100) NOT NULL,
        CreatedAt           datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_ConstraintFieldMap_SFO UNIQUE (SFOFieldCode),
        CONSTRAINT UQ_ConstraintFieldMap_Constraint UNIQUE (ConstraintFieldName)
    );
    CREATE INDEX IX_ConstraintFieldMap_Constraint
        ON cfg.ConstraintFieldMap (ConstraintFieldName);
END;
GO

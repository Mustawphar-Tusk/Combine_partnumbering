-- cfg.MotorConstraint: Rev0.3 Motor Constraints (allowed motor-attribute pairs).
-- Source: docs/evidence/F120/FYBROC_MOTOR_CONSTRAINT_MODEL.json (3278 rows,
-- 19 blocks across 6 series-scope groups). Each row is one allowed/not-allowed
-- pair between two motor-related dimensions for a series scope.
IF OBJECT_ID(N'cfg.MotorConstraint', N'U') IS NULL
BEGIN
    CREATE TABLE cfg.MotorConstraint
    (
        MotorConstraintId bigint IDENTITY(1,1) PRIMARY KEY,
        MetadataPublicationId bigint NOT NULL,
        PumpFamilyId int NOT NULL,
        SeriesScope varchar(50) NOT NULL,     -- e.g. "1500 and 1600", "5500"
        Dimension1Field varchar(100) NOT NULL, -- e.g. Alt_Size, F_Frame_Size
        Dimension1Value nvarchar(200) NOT NULL,
        Dimension2Field varchar(100) NOT NULL, -- e.g. F_MotorHpRpm, F_Motor Type
        Dimension2Value nvarchar(200) NOT NULL,
        Allowed varchar(20) NOT NULL DEFAULT 'Allowed',
        IsActive bit NOT NULL DEFAULT 1,
        CreatedAt datetime2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_MotorConstraint_Publication
            FOREIGN KEY (MetadataPublicationId)
            REFERENCES cfg.MetadataPublication(MetadataPublicationId),
        CONSTRAINT FK_MotorConstraint_Family
            FOREIGN KEY (PumpFamilyId)
            REFERENCES cfg.PumpFamily(PumpFamilyId)
    );

    CREATE INDEX IX_MotorConstraint_Lookup
        ON cfg.MotorConstraint
        (MetadataPublicationId, PumpFamilyId, Dimension1Field, Dimension1Value)
        INCLUDE (Dimension2Field, Dimension2Value, Allowed, SeriesScope)
        WHERE IsActive = 1;
END;
GO

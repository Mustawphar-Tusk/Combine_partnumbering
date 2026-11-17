/* ============================================================
   sql/39 - one spec/price table PER SealNumbering permutation sheet
   (supersedes the combined cfg.DeanSealSpec of sql/38, which the loader drops).

   Why: each sheet is its own permutation space (codes repeat across sheets, e.g.
   '001'). Within a sheet the permutation (the selection values) is the PRIMARY KEY, so a
   collision cannot be stored. Collision rule (owner): when the same permutation (same
   values across every column) appears more than once, the EARLIER row is retained and
   the later rows are discarded (logged in cfg.DeanSealSpecDiscarded); permutation
   numbers are then re-sequenced 1..N in sheet order (PermutationNo).

   cfg.DeanSealSheet maps a Seal Reference Table key -> its spec table.
   Dean-only, additive. Fybroc untouched.
   ============================================================ */
IF OBJECT_ID('cfg.DeanSealSheet','U') IS NULL
    CREATE TABLE cfg.DeanSealSheet (
        SealRefKey nvarchar(40) NOT NULL CONSTRAINT PK_DeanSealSheet PRIMARY KEY,
        SpecTable  sysname      NOT NULL CONSTRAINT UQ_DeanSealSheet_Table UNIQUE,
        HasGasket  bit          NOT NULL,
        LoadedAt   datetime2    NOT NULL CONSTRAINT DF_DeanSealSheet_LoadedAt DEFAULT SYSUTCDATETIME()
    );

IF OBJECT_ID('cfg.DeanSealSpecDiscarded','U') IS NULL
    CREATE TABLE cfg.DeanSealSpecDiscarded (
        DeanSealSpecDiscardedId bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_DeanSealSpecDiscarded PRIMARY KEY,
        SealRefKey nvarchar(40)   NOT NULL,
        ComboHash  binary(32)     NOT NULL,
        ComboKey   nvarchar(1200) NOT NULL,
        SealCode   varchar(8)     NOT NULL,   -- the DISCARDED later row's code
        KeptSealCode varchar(8)   NOT NULL,   -- the earlier row retained for this permutation
        PriceRaw   nvarchar(40)   NULL,
        SourceRow  int            NOT NULL,
        LoadedAt   datetime2      NOT NULL CONSTRAINT DF_DeanSealSpecDiscarded_LoadedAt DEFAULT SYSUTCDATETIME()
    );
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name='IX_DeanSealSpecDiscarded_Lookup')
    CREATE INDEX IX_DeanSealSpecDiscarded_Lookup ON cfg.DeanSealSpecDiscarded (SealRefKey, ComboHash);

/* one table per permutation sheet */
IF OBJECT_ID('cfg.DeanSealSpec_S1000','U') IS NULL
    CREATE TABLE cfg.DeanSealSpec_S1000 (PermutationNo int NOT NULL CONSTRAINT UQ_DeanSealSpec_S1000_No UNIQUE, ComboHash binary(32) NOT NULL CONSTRAINT PK_DeanSealSpec_S1000 PRIMARY KEY, ComboKey nvarchar(1200) NOT NULL, SealCode varchar(8) NOT NULL CONSTRAINT UQ_DeanSealSpec_S1000_Code UNIQUE, PriceRaw nvarchar(40) NULL, PriceAmount decimal(18,2) NULL, PriceStatus varchar(10) NOT NULL CONSTRAINT CK_DeanSealSpec_S1000_P CHECK (PriceStatus IN ('PRICED','CF','TBD','BLANK')), SourceRow int NOT NULL);
IF OBJECT_ID('cfg.DeanSealSpec_S1375','U') IS NULL
    CREATE TABLE cfg.DeanSealSpec_S1375 (PermutationNo int NOT NULL CONSTRAINT UQ_DeanSealSpec_S1375_No UNIQUE, ComboHash binary(32) NOT NULL CONSTRAINT PK_DeanSealSpec_S1375 PRIMARY KEY, ComboKey nvarchar(1200) NOT NULL, SealCode varchar(8) NOT NULL CONSTRAINT UQ_DeanSealSpec_S1375_Code UNIQUE, PriceRaw nvarchar(40) NULL, PriceAmount decimal(18,2) NULL, PriceStatus varchar(10) NOT NULL CONSTRAINT CK_DeanSealSpec_S1375_P CHECK (PriceStatus IN ('PRICED','CF','TBD','BLANK')), SourceRow int NOT NULL);
IF OBJECT_ID('cfg.DeanSealSpec_S1750','U') IS NULL
    CREATE TABLE cfg.DeanSealSpec_S1750 (PermutationNo int NOT NULL CONSTRAINT UQ_DeanSealSpec_S1750_No UNIQUE, ComboHash binary(32) NOT NULL CONSTRAINT PK_DeanSealSpec_S1750 PRIMARY KEY, ComboKey nvarchar(1200) NOT NULL, SealCode varchar(8) NOT NULL CONSTRAINT UQ_DeanSealSpec_S1750_Code UNIQUE, PriceRaw nvarchar(40) NULL, PriceAmount decimal(18,2) NULL, PriceStatus varchar(10) NOT NULL CONSTRAINT CK_DeanSealSpec_S1750_P CHECK (PriceStatus IN ('PRICED','CF','TBD','BLANK')), SourceRow int NOT NULL);
IF OBJECT_ID('cfg.DeanSealSpec_S2125','U') IS NULL
    CREATE TABLE cfg.DeanSealSpec_S2125 (PermutationNo int NOT NULL CONSTRAINT UQ_DeanSealSpec_S2125_No UNIQUE, ComboHash binary(32) NOT NULL CONSTRAINT PK_DeanSealSpec_S2125 PRIMARY KEY, ComboKey nvarchar(1200) NOT NULL, SealCode varchar(8) NOT NULL CONSTRAINT UQ_DeanSealSpec_S2125_Code UNIQUE, PriceRaw nvarchar(40) NULL, PriceAmount decimal(18,2) NULL, PriceStatus varchar(10) NOT NULL CONSTRAINT CK_DeanSealSpec_S2125_P CHECK (PriceStatus IN ('PRICED','CF','TBD','BLANK')), SourceRow int NOT NULL);
IF OBJECT_ID('cfg.DeanSealSpec_S2250','U') IS NULL
    CREATE TABLE cfg.DeanSealSpec_S2250 (PermutationNo int NOT NULL CONSTRAINT UQ_DeanSealSpec_S2250_No UNIQUE, ComboHash binary(32) NOT NULL CONSTRAINT PK_DeanSealSpec_S2250 PRIMARY KEY, ComboKey nvarchar(1200) NOT NULL, SealCode varchar(8) NOT NULL CONSTRAINT UQ_DeanSealSpec_S2250_Code UNIQUE, PriceRaw nvarchar(40) NULL, PriceAmount decimal(18,2) NULL, PriceStatus varchar(10) NOT NULL CONSTRAINT CK_DeanSealSpec_S2250_P CHECK (PriceStatus IN ('PRICED','CF','TBD','BLANK')), SourceRow int NOT NULL);
IF OBJECT_ID('cfg.DeanSealSpec_S3000','U') IS NULL
    CREATE TABLE cfg.DeanSealSpec_S3000 (PermutationNo int NOT NULL CONSTRAINT UQ_DeanSealSpec_S3000_No UNIQUE, ComboHash binary(32) NOT NULL CONSTRAINT PK_DeanSealSpec_S3000 PRIMARY KEY, ComboKey nvarchar(1200) NOT NULL, SealCode varchar(8) NOT NULL CONSTRAINT UQ_DeanSealSpec_S3000_Code UNIQUE, PriceRaw nvarchar(40) NULL, PriceAmount decimal(18,2) NULL, PriceStatus varchar(10) NOT NULL CONSTRAINT CK_DeanSealSpec_S3000_P CHECK (PriceStatus IN ('PRICED','CF','TBD','BLANK')), SourceRow int NOT NULL);
IF OBJECT_ID('cfg.DeanSealSpec_Misc','U') IS NULL
    CREATE TABLE cfg.DeanSealSpec_Misc (PermutationNo int NOT NULL CONSTRAINT UQ_DeanSealSpec_Misc_No UNIQUE, ComboHash binary(32) NOT NULL CONSTRAINT PK_DeanSealSpec_Misc PRIMARY KEY, ComboKey nvarchar(1200) NOT NULL, SealCode varchar(8) NOT NULL CONSTRAINT UQ_DeanSealSpec_Misc_Code UNIQUE, PriceRaw nvarchar(40) NULL, PriceAmount decimal(18,2) NULL, PriceStatus varchar(10) NOT NULL CONSTRAINT CK_DeanSealSpec_Misc_P CHECK (PriceStatus IN ('PRICED','CF','TBD','BLANK')), SourceRow int NOT NULL);

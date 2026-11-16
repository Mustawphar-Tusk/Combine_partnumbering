/* ============================================================
   sql/38 - Dean seal configuration SPEC + PRICE mapping (additive, Dean-only).

   Source: workbooks/Dean/SealNumbering.xlsx permutation sheets
     "1.000" Shafts", "1.375" Shafts", "1.750" Shafts", "2.125" Shafts",
     "2.250" Shafts", "3.000" Shafts", "Misc."
   Each sheet name IS a cfg.DeanSealReference.SealRefKey (Seal Reference Table,
   Pump Constraints col 594). One row per coded permutation:
     (SealRefKey, ComboKey) -> SealCode + Price.
   ComboKey = '*'-join of the seal selection values in the fixed field order
   defined in scripts/load_dean_seal_spec.py (lower-cased, whitespace-collapsed);
   ComboHash = SHA-256 of ComboKey (indexed lookup key).
   PriceStatus: PRICED (numeric), CF ('C.F.' = call factory), TBD, BLANK.
   CF/TBD/BLANK are placeholders: engineering determines the price when the quote
   is submitted for review.
   Fybroc is untouched (no shared table is altered).
   ============================================================ */
IF OBJECT_ID('cfg.DeanSealSpec','U') IS NULL
BEGIN
    CREATE TABLE cfg.DeanSealSpec (
        DeanSealSpecId bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_DeanSealSpec PRIMARY KEY,
        SealRefKey     nvarchar(40)  NOT NULL,
        SealCode       varchar(8)    NOT NULL,
        ComboKey       nvarchar(1200) NOT NULL,
        ComboHash      binary(32)    NOT NULL,
        PriceRaw       nvarchar(40)  NULL,
        PriceAmount    decimal(18,2) NULL,
        PriceStatus    varchar(10)   NOT NULL,
        SourceRow      int           NOT NULL,
        LoadedAt       datetime2     NOT NULL CONSTRAINT DF_DeanSealSpec_LoadedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT CK_DeanSealSpec_PriceStatus CHECK (PriceStatus IN ('PRICED','CF','TBD','BLANK'))
    );
    CREATE INDEX IX_DeanSealSpec_Lookup ON cfg.DeanSealSpec (SealRefKey, ComboHash) INCLUDE (SealCode, PriceAmount, PriceStatus);
    CREATE INDEX IX_DeanSealSpec_Code   ON cfg.DeanSealSpec (SealRefKey, SealCode);
END

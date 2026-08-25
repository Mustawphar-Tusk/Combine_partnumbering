"""Test all 7 Fybroc series end-to-end."""
import pyodbc
import json
import hashlib

conn_str = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=PumpConfiguratorDB;"
    "Trusted_Connection=yes;"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)

SERIES_TESTS = {
    "1500": {"ALT_SIZE": "1x1.5x6", "PUMP_MATERIAL": "vr-1", "IMPELLER_TRIM": "6.000", "FLANGE_TYPE": "ansi flange"},
    "1530": {"ALT_SIZE": "1.5x3x8", "PUMP_MATERIAL": "vr-1a", "IMPELLER_TRIM": "7.500", "FLANGE_TYPE": "ansi flange"},
    "1600": {"ALT_SIZE": "2x3x6", "PUMP_MATERIAL": "vr-1", "IMPELLER_TRIM": "5.500", "FLANGE_TYPE": "ansi flange"},
    "1630": {"ALT_SIZE": "1x1.5x8", "PUMP_MATERIAL": "vr-1", "IMPELLER_TRIM": "7.000", "FLANGE_TYPE": "ansi flange"},
    "2530": {"ALT_SIZE": "1x1.5x6", "PUMP_MATERIAL": "vr-1", "IMPELLER_TRIM": "6.000"},
    "3000": {"ALT_SIZE": "2x3x6", "PUMP_MATERIAL": "vr-1", "IMPELLER_TRIM": "5.500", "FLANGE_TYPE": "ansi flange"},
    "5500": {"ALT_SIZE": "1x2x10", "PUMP_MATERIAL": "vr-1", "IMPELLER_TRIM": "8.000", "FLANGE_TYPE": "ansi flange"},
}

FLANGE_MAP = {"ansi flange": "ANSI", "din/iso flange": "Din", "jis flange": "JIS"}


def main():
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    print("=" * 80)
    print("FYBROC ALL-SERIES END-TO-END TEST")
    print("=" * 80)
    print()

    all_pass = True
    for series, specific in SERIES_TESTS.items():
        issues = []

        # Series code
        flange = specific.get("FLANGE_TYPE", "")
        flange_short = FLANGE_MAP.get(flange, "ANSI") if flange else ""
        series_key = f"{series} ({flange_short})" if flange_short else series
        sc = cursor.execute("SELECT cfg.fn_LookupIdentifierCode(2,2,?,?)", "SERIES", series_key).fetchone()[0]
        if not sc:
            sc = cursor.execute("SELECT cfg.fn_LookupIdentifierCode(2,2,?,?)", "SERIES", series).fetchone()[0]
        if not sc:
            issues.append("SERIES_CODE")

        # Size
        size_code = cursor.execute("SELECT cfg.fn_LookupIdentifierCode(2,2,?,?)", "SIZE", specific["ALT_SIZE"]).fetchone()[0]
        if not size_code:
            issues.append("SIZE_CODE")

        # Material
        mat_code = cursor.execute("SELECT cfg.fn_LookupIdentifierCode(2,2,?,?)", "PUMP_MATERIAL", specific["PUMP_MATERIAL"]).fetchone()[0]
        if not mat_code:
            issues.append("MATERIAL_CODE")

        # Trim
        trim_code = cursor.execute("SELECT cfg.fn_LookupIdentifierCode(2,2,?,?)", "IMPELLER_TRIM", specific["IMPELLER_TRIM"]).fetchone()[0]
        if not trim_code:
            issues.append("TRIM_CODE")

        # Pricing
        size_upper = specific["ALT_SIZE"].upper()
        price_row = cursor.execute("""
            SELECT TOP 1 pr.Amount FROM price.PriceRule pr
            JOIN price.PriceBookVersion pbv ON pbv.PriceBookVersionId=pr.PriceBookVersionId AND pbv.IsCurrent=1
            WHERE pr.ComponentCode='BASE_PUMP' AND pr.IsActive=1
              AND (pr.SeriesCode=? OR pr.SeriesCode LIKE ?)
              AND UPPER(pr.SourceSizeValue) LIKE ?
        """, series, f"{series}%", f"{size_upper}%").fetchone()
        price = float(price_row[0]) if price_row else None
        if not price:
            issues.append("PRICING")

        # Seal combo
        seal_row = cursor.execute("""
            SELECT TOP 1 SegmentValue FROM cfg.vw_SegmentCombinationLookup
            WHERE SegmentCode='SEAL_ASSEMBLY'
              AND LOWER(SelectionsJson) LIKE '%mechanical seal included%'
              AND LOWER(SelectionsJson) LIKE '%8b2 single outside%'
        """).fetchone()
        seal = seal_row[0] if seal_row else None
        if not seal:
            issues.append("SEAL_COMBO")

        # Pump options combo
        pump_row = cursor.execute("""
            SELECT TOP 1 SegmentValue FROM cfg.vw_SegmentCombinationLookup
            WHERE SegmentCode='PUMP_OPTIONS'
              AND LOWER(SelectionsJson) LIKE '%316 ss shaft%'
              AND LOWER(SelectionsJson) LIKE '%internal flush%'
              AND LOWER(SelectionsJson) LIKE '%fkm%'
        """).fetchone()
        pump = pump_row[0] if pump_row else None
        if not pump:
            issues.append("PUMP_OPTIONS_COMBO")

        # Options combo
        opts_row = cursor.execute("""
            SELECT TOP 1 SegmentValue FROM cfg.vw_SegmentCombinationLookup
            WHERE SegmentCode='OPTIONS'
              AND LOWER(SelectionsJson) LIKE '%coupling included%'
              AND LOWER(SelectionsJson) LIKE '%baseplate included%'
        """).fetchone()
        opts = opts_row[0] if opts_row else None
        if not opts:
            issues.append("OPTIONS_COMBO")

        status = "PASS" if not issues else "FAIL"
        if issues:
            all_pass = False

        pn_parts = f"F{sc or '?'}{size_code or '?'}{mat_code or '?'}{trim_code or '??'}"
        print(f"  [{status}] {series}: PN={pn_parts}-{pump or '????'}-F{seal or '??'}-{opts or '??'}-18???-XXX-00")
        print(f"         Price: ${price:,.0f}" if price else "         Price: NONE")
        if issues:
            print(f"         ISSUES: {issues}")
        print()

    print("=" * 80)
    print(f"RESULT: {'ALL PASS' if all_pass else 'SOME FAILURES'}")
    conn.close()


if __name__ == "__main__":
    main()

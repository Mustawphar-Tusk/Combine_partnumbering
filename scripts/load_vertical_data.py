"""Load vertical series data: Pump Options Vertical combinations + pricing for 5530/7500."""
import openpyxl
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

WORKBOOK = "workbooks/Fybroc/Nomenclature_V6.xlsm"


def load_vertical_pump_options():
    """Load the 23,040-row vertical Pump Options combination table."""
    print("Loading Vertical Pump Options from Nomenclature_V6...")
    wb = openpyxl.load_workbook(WORKBOOK, read_only=True, data_only=True)
    ws = wb["Pump Options - Vertical"]

    # Data: rows 14-23053, cols C-Q
    # Col C=key, D=Shaft Material, E=Impeller Sleeve, F=Wetted Hardware,
    # G=Pump Elastomers, H=Flush, I=Flush Options, J=Impeller Balance,
    # K=Vapor Protection, L=Strainer, M=Hex-Code, N=ID
    FIELDS = [
        (4, "SHAFT_MATERIAL"),
        (5, "IMPELLER_SLEEVE"),
        (6, "WETTED_HARDWARE"),
        (7, "PUMP_ELASTOMERS"),
        (8, "FLUSH"),
        (9, "FLUSH_OPTIONS"),
        (10, "IMPELLER_BALANCE"),
        (11, "VAPOR_PROTECTION"),
        (12, "STRAINER"),
    ]

    rows = []
    for row_tuple in ws.iter_rows(min_row=14, max_row=23053, min_col=3, max_col=14, values_only=True):
        hex_code = row_tuple[10]  # col M (index 10 from col C=0)
        if hex_code is None:
            break
        hex_code = str(hex_code).strip()

        selections = {}
        for col_offset, field_name in FIELDS:
            v = row_tuple[col_offset - 3]  # adjust for min_col=3
            selections[field_name] = str(v).strip() if v else ""

        combination_key = "|".join(selections.values())
        selections_json = json.dumps(selections, ensure_ascii=False)

        rows.append((hex_code, combination_key, selections_json))

    wb.close()
    print(f"  Extracted {len(rows)} vertical pump options rows")
    return rows


def load_vertical_pricing():
    """Load 5530 and 7500 pricing from Pricebook."""
    print("Loading vertical pricing from Pricebook...")
    wb = openpyxl.load_workbook(
        "workbooks/Fybroc/Price Estimator-Fybroc.xlsm",
        read_only=True, data_only=True,
    )
    ws = wb["Pricebook"]

    pricing_rows = []

    # 5530 block: col 126-130, row 5 headers, row 6+ data
    print("  5530 pricing...")
    for r in range(6, 50):
        size = ws.cell(row=r, column=126).value
        price = ws.cell(row=r, column=127).value
        if size is None:
            break
        if price is not None:
            try:
                pricing_rows.append(("5530", str(size).strip(), float(price)))
            except (ValueError, TypeError):
                pass

    # 7500 block: col 133+, row 5 headers, row 6+ data
    print("  7500 pricing...")
    for r in range(6, 50):
        size = ws.cell(row=r, column=133).value
        price = ws.cell(row=r, column=137).value  # first price col
        if size is None:
            break
        if price is not None:
            try:
                pricing_rows.append(("7500", str(size).strip(), float(price)))
            except (ValueError, TypeError):
                pass

    # 7530 block: col 157+
    print("  7530 pricing...")
    for r in range(6, 50):
        size = ws.cell(row=r, column=157).value
        price = ws.cell(row=r, column=159).value
        if size is None:
            break
        if price is not None:
            try:
                pricing_rows.append(("7530", str(size).strip(), float(price)))
            except (ValueError, TypeError):
                pass

    wb.close()
    print(f"  Total vertical pricing rows: {len(pricing_rows)}")
    return pricing_rows


def main():
    # 1. Load vertical pump options
    vert_pump_opts = load_vertical_pump_options()

    conn = pyodbc.connect(conn_str, autocommit=False)
    cursor = conn.cursor()

    # Get the latest batch ID
    batch_id = cursor.execute(
        "SELECT MAX(ImportBatchId) FROM stg.SegmentCombinationImportBatch"
    ).fetchone()[0]

    # Insert vertical pump options into staging
    print(f"Inserting {len(vert_pump_opts)} vertical PUMP_OPTIONS into staging (batch {batch_id})...")
    batch_size = 1000
    inserted = 0
    for i in range(0, len(vert_pump_opts), batch_size):
        batch = vert_pump_opts[i:i + batch_size]
        cursor.executemany(
            "INSERT INTO stg.SegmentCombinationImport "
            "(ImportBatchId, FamilyCode, WorkbookRole, WorkbookName, WorksheetName, "
            " SegmentCode, SegmentName, SourceRow, SourceId, SegmentValue, ExpectedWidth, "
            " CombinationKey, SelectionsJson, SourceCellsJson, SourceProfile) "
            "VALUES (?, 'FYBROC', 'vertical_pump_options', 'Nomenclature_V6.xlsm', "
            " 'Pump Options - Vertical', 'PUMP_OPTIONS_VERTICAL', 'Pump Options Vertical', "
            " ?, ?, ?, 4, ?, ?, '{}', 'F110.5b')",
            [(batch_id, idx + i, idx + i, hex_code, combo_key, sel_json)
             for idx, (hex_code, combo_key, sel_json) in enumerate(batch, i + 1)],
        )
        inserted += len(batch)
    conn.commit()
    print(f"  Inserted {inserted} rows")

    # 2. Load vertical pricing
    pricing_rows = load_vertical_pricing()

    pbv_id = cursor.execute(
        "SELECT PriceBookVersionId FROM price.PriceBookVersion WHERE IsCurrent=1"
    ).fetchone()[0]

    print(f"Inserting vertical pricing into price.PriceRule...")
    for series, size, amount in pricing_rows:
        try:
            cursor.execute(
                "INSERT INTO price.PriceRule "
                "(PriceBookVersionId, RuleCode, RuleName, RuleType, ComponentCode, SeriesCode, "
                " Priority, Amount, PricingStatus, IsActive, SourceSizeValue, SourceOptionValue) "
                "VALUES (?, ?, ?, 'base_pump', 'BASE_PUMP', ?, 100, ?, 'found', 1, ?, 'VR-1 (Standard)')",
                pbv_id, f"{series}-BASE-{size}-VR1", f"{series} Base {size}",
                series, amount, size.upper(),
            )
        except Exception:
            pass  # skip duplicates
    conn.commit()

    # 3. Update the view to include vertical pump options
    cursor.execute("""
    CREATE OR ALTER VIEW cfg.vw_SegmentCombinationLookup AS
    SELECT SegmentCode, CombinationKey, CombinationKeyHash, SegmentValue, SelectionsJson, FamilyCode
    FROM stg.SegmentCombinationImport
    WHERE ImportBatchId IN (
        SELECT ImportBatchId FROM stg.SegmentCombinationImportBatch
        WHERE FamilyCode = 'FYBROC' AND Status = 'Loaded'
    );
    """)
    conn.commit()

    # Verify
    total = cursor.execute(
        "SELECT COUNT(*) FROM cfg.vw_SegmentCombinationLookup WHERE SegmentCode='PUMP_OPTIONS_VERTICAL'"
    ).fetchone()[0]
    print(f"\nVertical PUMP_OPTIONS in lookup view: {total}")

    pricing_count = cursor.execute("""
        SELECT SeriesCode, COUNT(*) FROM price.PriceRule pr
        JOIN price.PriceBookVersion pbv ON pbv.PriceBookVersionId=pr.PriceBookVersionId AND pbv.IsCurrent=1
        WHERE pr.SeriesCode IN ('5530','7500','7530') AND pr.IsActive=1
        GROUP BY pr.SeriesCode
    """).fetchall()
    print("Vertical pricing loaded:")
    for r in pricing_count:
        print(f"  {r[0]}: {r[1]} rules")

    conn.close()
    print("\nDone!")


if __name__ == "__main__":
    main()

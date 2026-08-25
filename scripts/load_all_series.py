"""Load ALL Fybroc series into SeriesFieldOption (including vertical series)."""
import openpyxl
import pyodbc

conn_str = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=PumpConfiguratorDB;"
    "Trusted_Connection=yes;"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)

def main():
    wb = openpyxl.load_workbook(
        "workbooks/Fybroc/Fybroc Configuration Rev0.3.xlsx",
        read_only=True, data_only=True,
    )
    ws = wb["Selections"]

    # Read series from header (row 1, cols 4-13)
    series_codes = []
    for c in range(4, 14):
        v = ws.cell(row=1, column=c).value
        if v:
            series_codes.append(str(v).strip())
    print(f"Series in Selections: {series_codes}")

    # Read all rows
    rows = []
    for r in range(2, 679):
        question = ws.cell(row=r, column=2).value
        answer = ws.cell(row=r, column=3).value
        if not question or not answer:
            continue
        question = str(question).strip()
        answer = str(answer).strip()
        field_code = question.upper().replace(" ", "_").replace("-", "_")

        for i, series in enumerate(series_codes):
            if ws.cell(row=r, column=4 + i).value == "X":
                rows.append((field_code, answer.lower(), series))

    wb.close()
    print(f"Total rows: {len(rows)}")

    # Load into SQL
    conn = pyodbc.connect(conn_str, autocommit=False)
    cursor = conn.cursor()

    pub_id = 2
    family_id = 2

    # Clear and reload
    cursor.execute("DELETE FROM cfg.SeriesFieldOption WHERE MetadataPublicationId=?", pub_id)
    conn.commit()

    # Batch insert
    batch_size = 500
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        cursor.executemany(
            "INSERT INTO cfg.SeriesFieldOption "
            "(MetadataPublicationId, PumpFamilyId, SourceFieldCode, FieldCode, OptionValue, "
            " SeriesCode, WorkbookName, WorksheetName, SourceRow, SourceFieldCell, SourceValueCell, SourceSeriesCell) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            [(pub_id, family_id, "", fc, val, series,
              "Fybroc Configuration Rev0.3.xlsx", "Selections", 0, "", "", "")
             for fc, val, series in batch],
        )
    conn.commit()

    # Verify
    total = cursor.execute(
        "SELECT COUNT(*) FROM cfg.SeriesFieldOption WHERE MetadataPublicationId=?", pub_id
    ).fetchone()[0]
    print(f"\nPublished: {total} rows")

    for r in cursor.execute(
        "SELECT SeriesCode, COUNT(*) FROM cfg.SeriesFieldOption "
        "WHERE MetadataPublicationId=? GROUP BY SeriesCode ORDER BY SeriesCode", pub_id
    ).fetchall():
        print(f"  {r[0]}: {r[1]}")

    conn.close()


if __name__ == "__main__":
    main()

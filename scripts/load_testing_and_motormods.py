"""Load Testing combinations (60 rows) + Motor Modifications code logic into SQL."""
import openpyxl
import pyodbc
import json

conn_str = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=PumpConfiguratorDB;"
    "Trusted_Connection=yes;"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)

WORKBOOK = "workbooks/Fybroc/Nomenclature_V6.xlsm"


def load_testing_combinations():
    """Load Testing sheet (60 rows) — row 10+, col G=key, H=Perf, I=Hydro, J=Vib, K=Sound, L=hex."""
    print("Loading Testing combinations from Nomenclature_V6...")
    wb = openpyxl.load_workbook(WORKBOOK, read_only=True, data_only=True)
    ws = wb["Testing"]

    rows = []
    for r in range(10, 70):
        hex_code = ws.cell(row=r, column=12).value  # col L
        if hex_code is None:
            break
        hex_code = str(hex_code).strip()

        perf = str(ws.cell(row=r, column=8).value or "NONE").strip()
        hydro = str(ws.cell(row=r, column=9).value or "NONE").strip()
        vib = str(ws.cell(row=r, column=10).value or "NONE").strip()
        sound = str(ws.cell(row=r, column=11).value or "NONE").strip()

        selections = {
            "PERFORMANCE_TESTING": perf.lower(),
            "HYDROTEST": hydro.lower(),
            "VIBRATION": vib.lower(),
            "SOUND_LEVEL": sound.lower(),
        }
        combination_key = "|".join(selections.values())
        sel_json = json.dumps(selections, ensure_ascii=False)
        rows.append((hex_code, combination_key, sel_json))

    wb.close()
    print(f"  Extracted {len(rows)} testing combinations")
    return rows


def load_motor_mod_codes():
    """Load Motor Modifications codes from V6 Attributes (F110.3 data)."""
    print("Loading Motor Modification codes from V6 Attributes...")
    attrs = json.load(open("docs/evidence/F110/FYBROC_V6_ATTRIBUTES.json", encoding="utf-8"))
    mods = attrs["motor_modification_codes"]
    print(f"  {len(mods)} motor modification codes")
    for m in mods[:5]:
        print(f"    {m['code']} = {m['modification']}")
    return mods


def main():
    testing_rows = load_testing_combinations()
    motor_mods = load_motor_mod_codes()

    conn = pyodbc.connect(conn_str, autocommit=True)
    cursor = conn.cursor()

    # Get batch ID
    batch_id = cursor.execute(
        "SELECT MAX(ImportBatchId) FROM stg.SegmentCombinationImportBatch"
    ).fetchone()[0]

    # Load testing combinations
    print(f"\nInserting {len(testing_rows)} TESTING combinations into staging...")
    for idx, (hex_code, combo_key, sel_json) in enumerate(testing_rows, 1):
        try:
            cursor.execute(
                "INSERT INTO stg.SegmentCombinationImport "
                "(ImportBatchId, FamilyCode, WorkbookRole, WorkbookName, WorksheetName, "
                " SegmentCode, SegmentName, SourceRow, SourceId, SegmentValue, ExpectedWidth, "
                " CombinationKey, SelectionsJson, SourceCellsJson, SourceProfile) "
                "VALUES (?, 'FYBROC', 'testing', 'Nomenclature_V6.xlsm', 'Testing', "
                " 'TESTING', 'Testing', ?, ?, ?, 2, ?, ?, '{}', 'F110.10')",
                batch_id, idx, idx + 300000, hex_code, combo_key, sel_json,
            )
        except Exception as e:
            pass

    # Load motor modification codes into VocabularyMap for direct code lookup
    print("\nLoading Motor Modification codes into VocabularyMap...")
    for mod in motor_mods:
        try:
            cursor.execute(
                "INSERT INTO cfg.VocabularyMap (FieldCode, ComboValue, SFOValue) VALUES (?,?,?)",
                "MOTOR_MOD", mod["modification"].lower(), mod["code"],
            )
        except:
            pass

    # Verify
    testing_count = cursor.execute(
        "SELECT COUNT(*) FROM stg.SegmentCombinationImport WHERE SegmentCode='TESTING'"
    ).fetchone()[0]
    print(f"\nTesting combinations in SQL: {testing_count}")

    mod_count = cursor.execute(
        "SELECT COUNT(*) FROM cfg.VocabularyMap WHERE FieldCode='MOTOR_MOD'"
    ).fetchone()[0]
    print(f"Motor Mod codes in VocabularyMap: {mod_count}")

    # Test a lookup
    row = cursor.execute(
        "SELECT TOP 1 SegmentValue FROM cfg.vw_SegmentCombinationLookup "
        "WHERE SegmentCode='TESTING' AND LOWER(SelectionsJson) LIKE '%none%' "
        "AND LOWER(SelectionsJson) LIKE '%none%'"
    ).fetchone()
    print(f"Testing 'all NONE' resolves to: {row[0] if row else 'NOT FOUND'}")

    conn.close()
    print("\nDone!")


if __name__ == "__main__":
    main()

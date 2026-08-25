"""Re-index vertical combination tables to use SFO-normalized vocabulary.

This eliminates the VocabularyMap translation layer for vertical lookups
by updating SelectionsJson to use the same lowercase SFO values that the
UI sends. After this, LIKE searches work directly.
"""
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


def build_reverse_vocab_map(cursor):
    """Build ComboValue -> SFOValue mapping from VocabularyMap."""
    rmap = {}
    for r in cursor.execute("SELECT FieldCode, ComboValue, SFOValue FROM cfg.VocabularyMap").fetchall():
        field, combo, sfo = r[0], r[1], r[2]
        # Handle pipe-separated SFO values — take the first one
        first_sfo = sfo.split("|")[0].strip()
        rmap[(field, combo.lower().rstrip("*").strip())] = first_sfo
    return rmap


def normalize_value(field_code, combo_value, reverse_map):
    """Convert a combo display value to its SFO normalized form."""
    if not combo_value or combo_value == "-":
        return combo_value
    
    # Strip asterisk (standard marker)
    clean = combo_value.rstrip("*").strip()
    
    # Look up in reverse map
    key = (field_code, clean.lower())
    if key in reverse_map:
        return reverse_map[key]
    
    # Fallback: just lowercase it
    return clean.lower()


def main():
    conn = pyodbc.connect(conn_str, autocommit=False)
    cursor = conn.cursor()

    reverse_map = build_reverse_vocab_map(cursor)
    print(f"Reverse vocab map: {len(reverse_map)} entries")

    # Process PUMP_OPTIONS_VERTICAL rows
    print("Re-indexing PUMP_OPTIONS_VERTICAL...")
    rows = cursor.execute(
        "SELECT SegmentCombinationImportId, SelectionsJson "
        "FROM stg.SegmentCombinationImport "
        "WHERE SegmentCode = 'PUMP_OPTIONS_VERTICAL'"
    ).fetchall()
    print(f"  Rows to process: {len(rows)}")

    updated = 0
    for row_id, sel_json in rows:
        if not sel_json:
            continue
        d = json.loads(sel_json)
        normalized = {}
        for field, value in d.items():
            normalized[field] = normalize_value(field, value, reverse_map)
        
        new_json = json.dumps(normalized, ensure_ascii=False)
        new_key = "|".join(normalized.values())
        
        cursor.execute(
            "UPDATE stg.SegmentCombinationImport "
            "SET SelectionsJson = ?, CombinationKey = ? "
            "WHERE SegmentCombinationImportId = ?",
            new_json, new_key, row_id,
        )
        updated += 1

    conn.commit()
    print(f"  Updated: {updated} rows")

    # Also re-index horizontal PUMP_OPTIONS
    print("\nRe-indexing PUMP_OPTIONS (horizontal)...")
    rows = cursor.execute(
        "SELECT SegmentCombinationImportId, SelectionsJson "
        "FROM stg.SegmentCombinationImport "
        "WHERE SegmentCode = 'PUMP_OPTIONS'"
    ).fetchall()
    print(f"  Rows to process: {len(rows)}")

    updated = 0
    batch = []
    for row_id, sel_json in rows:
        if not sel_json:
            continue
        d = json.loads(sel_json)
        normalized = {}
        for field, value in d.items():
            normalized[field] = normalize_value(field, value, reverse_map)
        
        new_json = json.dumps(normalized, ensure_ascii=False)
        new_key = "|".join(normalized.values())
        batch.append((new_json, new_key, row_id))
        updated += 1

        if len(batch) >= 5000:
            cursor.executemany(
                "UPDATE stg.SegmentCombinationImport "
                "SET SelectionsJson = ?, CombinationKey = ? "
                "WHERE SegmentCombinationImportId = ?",
                batch,
            )
            conn.commit()
            batch = []
            print(f"    ...{updated} processed")

    if batch:
        cursor.executemany(
            "UPDATE stg.SegmentCombinationImport "
            "SET SelectionsJson = ?, CombinationKey = ? "
            "WHERE SegmentCombinationImportId = ?",
            batch,
        )
        conn.commit()

    print(f"  Updated: {updated} rows")

    # Re-index SEAL_ASSEMBLY and OPTIONS and MOTOR_ASSEMBLY too
    for seg in ["SEAL_ASSEMBLY", "OPTIONS", "MOTOR_ASSEMBLY"]:
        print(f"\nRe-indexing {seg}...")
        rows = cursor.execute(
            "SELECT SegmentCombinationImportId, SelectionsJson "
            "FROM stg.SegmentCombinationImport WHERE SegmentCode = ?",
            seg,
        ).fetchall()
        print(f"  Rows: {len(rows)}")

        batch = []
        for row_id, sel_json in rows:
            if not sel_json:
                continue
            d = json.loads(sel_json)
            normalized = {}
            for field, value in d.items():
                normalized[field] = normalize_value(field, value, reverse_map)
            new_json = json.dumps(normalized, ensure_ascii=False)
            new_key = "|".join(normalized.values())
            batch.append((new_json, new_key, row_id))

        if batch:
            cursor.executemany(
                "UPDATE stg.SegmentCombinationImport "
                "SET SelectionsJson = ?, CombinationKey = ? "
                "WHERE SegmentCombinationImportId = ?",
                batch,
            )
            conn.commit()
        print(f"  Updated: {len(batch)} rows")

    # Verify
    print("\n=== Verification ===")
    sample = cursor.execute(
        "SELECT TOP 1 SelectionsJson FROM stg.SegmentCombinationImport "
        "WHERE SegmentCode='PUMP_OPTIONS_VERTICAL'"
    ).fetchone()
    if sample:
        print("Sample VERTICAL SelectionsJson (after re-index):")
        d = json.loads(sample[0])
        for k, v in d.items():
            print(f"  {k} = {v!r}")

    sample2 = cursor.execute(
        "SELECT TOP 1 SelectionsJson FROM stg.SegmentCombinationImport "
        "WHERE SegmentCode='PUMP_OPTIONS' AND SegmentValue='0001'"
    ).fetchone()
    if sample2:
        print("\nSample HORIZONTAL SelectionsJson (after re-index):")
        d = json.loads(sample2[0])
        for k, v in d.items():
            print(f"  {k} = {v!r}")

    conn.close()
    print("\nDone! All combination tables re-indexed to SFO vocabulary.")


if __name__ == "__main__":
    main()

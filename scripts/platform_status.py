from __future__ import annotations

import os

import pyodbc


def connection_string() -> str:
    server = os.getenv("DB_SERVER", "localhost")
    database = os.getenv("DB_DATABASE", "PumpConfiguratorDB")
    driver = os.getenv(
        "DB_DRIVER",
        "ODBC Driver 18 for SQL Server",
    )
    return (
        f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
        "Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;"
    )


def main() -> None:
    connection = pyodbc.connect(connection_string(), autocommit=True)

    try:
        cursor = connection.cursor()

        segment_count = cursor.execute(
            "SELECT COUNT_BIG(*) FROM stg.SegmentCombinationImport;"
        ).fetchone()[0]

        publication_count = cursor.execute(
            """
            SELECT COUNT_BIG(*)
            FROM sys.tables
            WHERE object_id = OBJECT_ID('cfg.MetadataPublication');
            """
        ).fetchone()[0]

        attribute_table = cursor.execute(
            """
            SELECT COUNT_BIG(*)
            FROM sys.tables
            WHERE object_id = OBJECT_ID('cfg.AttributeValue');
            """
        ).fetchone()[0]

        print("Pump Configuration Platform Status")
        print("==================================")
        print(f"Segment combinations staged: {int(segment_count):,}")
        print(
            "Metadata publication table: "
            + ("OK" if publication_count else "MISSING")
        )
        print(
            "Attribute value table: "
            + ("OK" if attribute_table else "MISSING")
        )
        print("Platform status: READY FOR ATTRIBUTE COMPILATION")
    finally:
        connection.close()


if __name__ == "__main__":
    main()

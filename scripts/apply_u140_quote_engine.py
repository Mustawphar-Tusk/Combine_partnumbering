"""U140 - Apply Quote Engine schema additions."""
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
    conn = pyodbc.connect(conn_str, autocommit=True)
    cursor = conn.cursor()

    # Add missing columns
    additions = [
        ("quote.QuoteHeader", "SiteCode", "varchar(10) NULL"),
        ("quote.QuoteHeader", "Status", "varchar(20) NULL"),
        ("quote.QuoteLine", "LineNumber", "int NULL"),
        ("quote.QuoteLine", "FamilyCode", "varchar(50) NULL"),
        ("quote.QuoteLine", "SiteCode", "varchar(10) NULL"),
        ("quote.QuoteLine", "PartNumber", "varchar(200) NULL"),
        ("quote.QuoteLine", "SKU", "varchar(100) NULL"),
        ("quote.QuoteLine", "ConfigurationJson", "nvarchar(max) NULL"),
        ("quote.QuoteLine", "PricingLineage", "nvarchar(max) NULL"),
        ("quote.QuoteLine", "PublicationVersion", "varchar(50) NULL"),
    ]

    for table, col, dtype in additions:
        exists = cursor.execute(
            "SELECT COL_LENGTH(?, ?)", table, col
        ).fetchone()[0]
        if exists is None:
            cursor.execute(f"ALTER TABLE {table} ADD [{col}] {dtype}")
            print(f"  Added {table}.{col}")
        else:
            print(f"  Exists: {table}.{col}")

    print("\nQuote tables updated. U140 complete.")
    print("Quote flow: SKU -> ConfiguredProduct -> QuoteLine (with PN, pricing, lineage)")
    conn.close()


if __name__ == "__main__":
    main()

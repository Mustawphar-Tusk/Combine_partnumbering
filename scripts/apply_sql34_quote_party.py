"""U4 - Apply sql/34_Create_Quote_Customer_Party.sql (additive).

Splits the migration on GO batches and executes them in order. Idempotent:
the migration itself guards object creation (IF OBJECT_ID ... IS NULL /
CREATE OR ALTER), so re-running is safe.
"""
import re
import sys
from pathlib import Path

import pyodbc

CONN = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=PumpConfiguratorDB;"
    "Trusted_Connection=yes;"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)

SQL_PATH = Path(__file__).resolve().parents[1] / "sql" / "34_Create_Quote_Customer_Party.sql"


def split_batches(text: str) -> list[str]:
    # Split on lines that are just GO (case-insensitive), as sqlcmd does.
    parts = re.split(r"(?im)^\s*GO\s*$", text)
    return [p.strip() for p in parts if p.strip()]


def main() -> int:
    text = SQL_PATH.read_text(encoding="utf-8-sig")
    batches = split_batches(text)
    conn = pyodbc.connect(CONN, autocommit=True)
    cur = conn.cursor()
    try:
        for i, batch in enumerate(batches, 1):
            try:
                cur.execute(batch)
                # Drain any PRINT/result messages so the next batch runs clean.
                while cur.nextset():
                    pass
            except pyodbc.Error as exc:
                print(f"  Batch {i} FAILED: {exc}")
                print("  ---- batch ----")
                print(batch[:500])
                return 1
        print(f"Applied {len(batches)} batches from sql/34 OK.")

        # Verify the table + procs exist.
        checks = [
            ("quote.QuoteParty table", "SELECT OBJECT_ID('quote.QuoteParty','U')"),
            ("usp_UpsertQuoteParty", "SELECT OBJECT_ID('quote.usp_UpsertQuoteParty','P')"),
            ("usp_GetQuoteParties", "SELECT OBJECT_ID('quote.usp_GetQuoteParties','P')"),
        ]
        ok = True
        for name, q in checks:
            val = cur.execute(q).fetchone()[0]
            state = "OK" if val is not None else "MISSING"
            if val is None:
                ok = False
            print(f"  {name}: {state}")
        return 0 if ok else 2
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())

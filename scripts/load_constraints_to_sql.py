"""Load the 21 Fybroc feasible constraint tables into SQL for runtime enforcement."""
import json
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
    # Load constraint model
    d = json.load(open("docs/evidence/F120/FYBROC_CONSTRAINT_MODEL.json", encoding="utf-8"))

    conn = pyodbc.connect(conn_str, autocommit=True)
    cursor = conn.cursor()

    # Create constraint table if not exists
    cursor.execute("""
    IF OBJECT_ID('cfg.FeasibleConstraint', 'U') IS NULL
    BEGIN
        CREATE TABLE cfg.FeasibleConstraint (
            FeasibleConstraintId bigint IDENTITY(1,1) PRIMARY KEY,
            TableName varchar(50) NOT NULL,
            Option1Field varchar(100) NOT NULL,
            Option1Value nvarchar(500) NOT NULL,
            Option2Field varchar(100) NULL,
            Option2Value nvarchar(500) NULL,
            Option3Field varchar(100) NULL,
            Option3Value nvarchar(500) NULL,
            Allowed varchar(20) NOT NULL DEFAULT 'Allowed',
            SeriesApplicability varchar(20) NOT NULL DEFAULT 'ALL_SERIES',
            Description nvarchar(1000) NULL
        );
        CREATE INDEX IX_FeasibleConstraint_Lookup
            ON cfg.FeasibleConstraint (Option1Field, Option1Value, Option2Field);
    END;
    """)

    # Clear existing
    cursor.execute("DELETE FROM cfg.FeasibleConstraint")

    # Load each constraint table
    total = 0
    for entry in d["constraint_index"]:
        table_name = entry.get("table_name")
        resolved = entry.get("resolved_table")
        if not table_name or not resolved:
            continue

        opt1_field = entry.get("option1", "")
        opt2_field = entry.get("option2", "")
        opt3_field = entry.get("option3", "")
        description = entry.get("description", "")
        series_app = entry.get("series_applicability", "ALL_SERIES")

        headers = resolved.get("headers", [])
        rows = resolved.get("rows", [])

        for row in rows:
            # Get values by header position
            vals = list(row.values())
            opt1_val = vals[0] if len(vals) > 0 else ""
            opt2_val = vals[1] if len(vals) > 1 else ""
            allowed = vals[2] if len(vals) > 2 else "Allowed"
            opt3_val = vals[3] if len(vals) > 3 else None

            if opt1_val:
                cursor.execute(
                    "INSERT INTO cfg.FeasibleConstraint "
                    "(TableName, Option1Field, Option1Value, Option2Field, Option2Value, "
                    " Option3Field, Option3Value, Allowed, SeriesApplicability, Description) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    table_name, opt1_field, str(opt1_val or ""),
                    opt2_field, str(opt2_val or ""),
                    opt3_field or None, str(opt3_val) if opt3_val else None,
                    str(allowed or "Allowed"), series_app, description[:1000],
                )
                total += 1

    print(f"Loaded {total} feasible constraint rows into cfg.FeasibleConstraint")

    # Summary by table
    for row in cursor.execute(
        "SELECT TableName, COUNT(*) FROM cfg.FeasibleConstraint GROUP BY TableName ORDER BY TableName"
    ).fetchall():
        print(f"  {row[0]}: {row[1]} rows")

    conn.close()


if __name__ == "__main__":
    main()

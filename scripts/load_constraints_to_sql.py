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

        # Field NAMES are taken from the table headers (below), NOT from the
        # constraint-index option1/2/3 - those can be in a different order than
        # the headers (e.g. ConstraintTable21 index says Pump Material/Length/
        # Alt Size but headers are Alt Size/Pump Material/Length), which would
        # mislabel every value. Deriving both name and value from the headers
        # keeps Option-field aligned with its Option-value.
        description = entry.get("description", "")
        series_app = entry.get("series_applicability", "ALL_SERIES")

        headers = resolved.get("headers", [])
        rows = resolved.get("rows", [])

        # Identify the "Allowed?" column by HEADER NAME, not position. Tables
        # have either [Opt1, Opt2, Allowed?] (2-field) or
        # [Opt1, Opt2, Opt3, Allowed?] (3-field, e.g. ConstraintTable21). A prior
        # positional parse mislabeled the 3-field case: it stored the Opt3
        # (Length) value as "Allowed" and the "Allowed?" text as Opt3Value. The
        # option-VALUE columns are all header columns except the Allowed one, in
        # order, so Option1/2/3 map correctly regardless of arity.
        allowed_idx = next(
            (i for i, h in enumerate(headers)
             if str(h).strip().lower().rstrip("?") == "allowed"),
            len(headers) - 1,  # fallback: last column
        )
        value_header_idxs = [i for i in range(len(headers)) if i != allowed_idx]
        # Field labels come from the headers at those same indexes, so name and
        # value stay aligned (Option1Field is headers[value_header_idxs[0]], etc.)
        opt_fields = [str(headers[i]).strip() for i in value_header_idxs]
        opt1_field = opt_fields[0] if len(opt_fields) > 0 else ""
        opt2_field = opt_fields[1] if len(opt_fields) > 1 else ""
        opt3_field = opt_fields[2] if len(opt_fields) > 2 else ""

        for row in rows:
            vals = list(row.values())

            def _v(i):
                return vals[i] if 0 <= i < len(vals) else None

            opt_vals = [_v(i) for i in value_header_idxs]
            opt1_val = opt_vals[0] if len(opt_vals) > 0 else ""
            opt2_val = opt_vals[1] if len(opt_vals) > 1 else ""
            opt3_val = opt_vals[2] if len(opt_vals) > 2 else None
            allowed = _v(allowed_idx)

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

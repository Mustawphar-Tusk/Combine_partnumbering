from __future__ import annotations

import argparse
import os

import pyodbc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-id", type=int, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument(
        "--description",
        default="Fybroc attribute metadata publication",
    )
    parser.add_argument("--activate", action="store_true")
    parser.add_argument("--server", default=os.getenv("DB_SERVER", "localhost"))
    parser.add_argument(
        "--database",
        default=os.getenv("DB_DATABASE", "PumpConfiguratorDB"),
    )
    parser.add_argument(
        "--driver",
        default=os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    connection_string = (
        f"DRIVER={{{args.driver}}};SERVER={args.server};"
        f"DATABASE={args.database};Trusted_Connection=yes;"
        "Encrypt=yes;TrustServerCertificate=yes;"
    )

    connection = pyodbc.connect(connection_string, autocommit=True)

    try:
        row = connection.cursor().execute(
            """
            DECLARE @PublicationId bigint;
            EXEC cfg.usp_PublishAttributeValues
                @AttributeValueImportBatchId = ?,
                @VersionCode = ?,
                @Description = ?,
                @Activate = ?,
                @MetadataPublicationId = @PublicationId OUTPUT;
            SELECT @PublicationId;
            """,
            args.batch_id,
            args.version,
            args.description,
            1 if args.activate else 0,
        ).fetchone()

        publication_id = int(row[0])

        print(f"Metadata publication: {publication_id}")
        print(f"Version: {args.version}")
        print(
            "Status: "
            + ("Active" if args.activate else "Testing")
        )
    finally:
        connection.close()


if __name__ == "__main__":
    main()

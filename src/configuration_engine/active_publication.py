from __future__ import annotations

import pyodbc


def get_active_publication_id(connection_string: str) -> int:
    connection = pyodbc.connect(connection_string, autocommit=True)
    try:
        row = connection.cursor().execute(
            """
            SELECT TOP (1) MetadataPublicationId
            FROM cfg.MetadataPublication
            WHERE Status = 'Active'
            ORDER BY ActivatedAt DESC, MetadataPublicationId DESC;
            """
        ).fetchone()

        if row is None:
            raise RuntimeError("No active metadata publication exists.")

        return int(row[0])
    finally:
        connection.close()

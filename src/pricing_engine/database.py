from __future__ import annotations

import pyodbc


def default_connection_string() -> str:
    drivers = pyodbc.drivers()

    preferred = (
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "SQL Server",
    )

    driver = next(
        (
            value
            for value in preferred
            if value in drivers
        ),
        None,
    )

    if driver is None:
        raise RuntimeError(
            "No supported SQL Server ODBC driver "
            f"was found. Installed: {drivers}"
        )

    return (
        f"DRIVER={{{driver}}};"
        "SERVER=localhost;"
        "DATABASE=PumpConfiguratorDB;"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )

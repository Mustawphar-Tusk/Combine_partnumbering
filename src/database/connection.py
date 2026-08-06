from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src.config.settings import get_settings

@lru_cache
def get_engine() -> Engine:
    return create_engine(
        get_settings().sqlalchemy_url,
        pool_pre_ping=True,
        pool_recycle=1800,
        future=True,
    )

def check_database_connection() -> dict:
    with get_engine().connect() as connection:
        row = connection.execute(
            text("SELECT @@SERVERNAME AS server_name, DB_NAME() AS database_name")
        ).mappings().one()

    return {
        "status": "ok",
        "server": row["server_name"],
        "database": row["database_name"],
    }

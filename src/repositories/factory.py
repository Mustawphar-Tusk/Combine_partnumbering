from src.config.settings import get_settings
from src.database.connection import get_engine
from src.repositories.sql_repository import SqlConfigurationRepository

def build_repository():
    backend = get_settings().repository_backend.lower()

    if backend == "sqlserver":
        return SqlConfigurationRepository(get_engine())

    raise ValueError(f"Unsupported repository backend: {backend}")

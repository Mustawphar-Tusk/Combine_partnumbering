from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_environment: str = "development"
    repository_backend: str = "sqlserver"

    sql_server: str = "localhost"
    sql_database: str = "PumpConfiguratorDB"
    sql_driver: str = "ODBC Driver 18 for SQL Server"
    sql_trusted_connection: bool = True
    sql_encrypt: bool = True
    sql_trust_server_certificate: bool = True
    sql_connection_timeout: int = 30
    sql_username: str | None = None
    sql_password: str | None = None

    @property
    def sqlalchemy_url(self) -> str:
        parts = [
            f"DRIVER={{{self.sql_driver}}}",
            f"SERVER={self.sql_server}",
            f"DATABASE={self.sql_database}",
            f"Encrypt={'yes' if self.sql_encrypt else 'no'}",
            f"TrustServerCertificate={'yes' if self.sql_trust_server_certificate else 'no'}",
            f"Connection Timeout={self.sql_connection_timeout}",
        ]

        if self.sql_trusted_connection:
            parts.append("Trusted_Connection=yes")
        else:
            if not self.sql_username or self.sql_password is None:
                raise ValueError("SQL credentials are required.")
            parts.extend([f"UID={self.sql_username}", f"PWD={self.sql_password}"])

        return "mssql+pyodbc:///?odbc_connect=" + quote_plus(";".join(parts))

@lru_cache
def get_settings() -> Settings:
    return Settings()

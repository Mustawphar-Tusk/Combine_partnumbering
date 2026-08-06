from fastapi import APIRouter, HTTPException

from src.config.settings import get_settings
from src.database.connection import check_database_connection

router = APIRouter(tags=["Health"])

@router.get("/health")
def health() -> dict:
    settings = get_settings()

    if settings.repository_backend.lower() != "sqlserver":
        return {"status": "ok", "repository_backend": settings.repository_backend}

    try:
        database = check_database_connection()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "status": "ok",
        "repository_backend": "sqlserver",
        "database": database,
    }

def test_imports() -> None:
    from src.api.main import app
    from src.database.connection import get_engine

    assert app.title == "Pump Configuration API"
    assert get_engine() is not None

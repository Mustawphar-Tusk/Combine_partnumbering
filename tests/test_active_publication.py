from src.configuration_engine.active_publication import get_active_publication_id


def test_active_publication_function_exists() -> None:
    assert callable(get_active_publication_id)

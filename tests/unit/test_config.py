from rootcause.core.config import Settings


def test_asyncpg_url_rewritten():
    s = Settings(database_url="postgresql://user:pass@localhost/db")
    assert s.database_url.startswith("postgresql+asyncpg://")


def test_asyncpg_url_unchanged_if_already_correct():
    url = "postgresql+asyncpg://user:pass@localhost/db"
    s = Settings(database_url=url)
    assert s.database_url == url


def test_defaults():
    s = Settings()
    assert s.app_env == "development"
    assert s.cors_origins == "*"
    assert s.api_secret_key == ""
    assert s.qdrant_collection == "rootcause_runbooks"

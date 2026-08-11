from app.db import normalize_database_url


def test_render_heroku_postgres_scheme_is_normalized():
    # Render/Heroku hand out bare postgres:// — must become the psycopg dialect.
    assert normalize_database_url("postgres://u:p@host:5432/db") == "postgresql+psycopg://u:p@host:5432/db"
    assert normalize_database_url("postgresql://u:p@host/db") == "postgresql+psycopg://u:p@host/db"


def test_already_qualified_and_sqlite_pass_through():
    assert normalize_database_url("postgresql+psycopg://u@h/db") == "postgresql+psycopg://u@h/db"
    assert normalize_database_url("sqlite:///./vanta.db") == "sqlite:///./vanta.db"

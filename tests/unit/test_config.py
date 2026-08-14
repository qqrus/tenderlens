from pydantic import SecretStr

from tenderlens.core.config import Settings


def test_database_dsn_unwraps_secret() -> None:
    settings = Settings(database_url=SecretStr("postgresql+asyncpg://example"))

    assert settings.database_dsn == "postgresql+asyncpg://example"
    assert "example" not in repr(settings.database_url)

import pytest
from pydantic import SecretStr, ValidationError

from tenderlens.core.config import Settings


def test_database_dsn_unwraps_secret() -> None:
    settings = Settings(database_url=SecretStr("postgresql+asyncpg://example"))

    assert settings.database_dsn == "postgresql+asyncpg://example"
    assert "example" not in repr(settings.database_url)


def test_upload_limit_is_exposed_in_bytes() -> None:
    settings = Settings(max_upload_size_mb=2)

    assert settings.max_upload_size_bytes == 2 * 1024 * 1024


def test_chunk_overlap_must_be_smaller_than_chunk_size() -> None:
    with pytest.raises(ValidationError):
        Settings(chunk_size_chars=200, chunk_overlap_chars=200)


def test_zero_cost_answer_provider_is_default() -> None:
    assert Settings().llm_provider == "extractive"

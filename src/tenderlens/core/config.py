from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import AnyHttpUrl, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "TenderLens API"
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    cors_origins: list[AnyHttpUrl] = Field(default_factory=list)

    database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://tenderlens:tenderlens@localhost:5432/tenderlens"
    )

    upload_dir: Path = Path("data/uploads")
    max_upload_size_mb: int = Field(default=20, ge=1, le=100)
    max_pdf_pages: int = Field(default=300, ge=1, le=2_000)
    chunk_size_chars: int = Field(default=1_600, ge=200, le=10_000)
    chunk_overlap_chars: int = Field(default=200, ge=0, le=2_000)

    llm_provider: Literal["ollama", "openai"] = "ollama"
    llm_model: str = "qwen3:4b"
    ollama_base_url: AnyHttpUrl = AnyHttpUrl("http://localhost:11434")
    openai_api_key: SecretStr | None = None

    @model_validator(mode="after")
    def validate_chunk_settings(self) -> Self:
        if self.chunk_overlap_chars >= self.chunk_size_chars:
            raise ValueError("chunk_overlap_chars must be smaller than chunk_size_chars")
        return self

    @property
    def database_dsn(self) -> str:
        return self.database_url.get_secret_value()

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()

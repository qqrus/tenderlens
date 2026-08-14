from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr
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

    llm_provider: Literal["ollama", "openai"] = "ollama"
    llm_model: str = "qwen3:4b"
    ollama_base_url: AnyHttpUrl = AnyHttpUrl("http://localhost:11434")
    openai_api_key: SecretStr | None = None

    @property
    def database_dsn(self) -> str:
        return self.database_url.get_secret_value()


@lru_cache
def get_settings() -> Settings:
    return Settings()

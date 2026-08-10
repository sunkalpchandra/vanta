from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./vanta.db"
    redis_url: str | None = None
    anthropic_api_key: str | None = None
    vanta_model: str = "claude-opus-5"
    frontend_origin: str = "http://localhost:3000"
    # Mutating requests per client per minute; 0 disables limiting.
    rate_limit_per_minute: int = 240


@lru_cache
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All secrets come from the environment. Nothing here is hard-coded."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: SecretStr = Field(..., alias="TELEGRAM_BOT_TOKEN")
    bot_api_secret: SecretStr = Field(..., alias="TELEGRAM_BOT_API_SECRET")
    api_base_url: str = Field("http://localhost:8000/api/v1", alias="API_BASE_URL")
    web_app_url: str = Field("http://localhost:5173", alias="WEB_APP_URL")
    redis_url: str = Field("", alias="REDIS_URL")
    admin_telegram_ids: str = Field("", alias="ADMIN_TELEGRAM_IDS")
    rate_limit_per_minute: int = Field(30, alias="BOT_RATE_LIMIT_PER_MINUTE", ge=1, le=600)
    max_upload_mb: int = Field(20, alias="BOT_MAX_UPLOAD_MB", ge=1, le=25)
    request_timeout_seconds: float = Field(10.0, alias="BOT_REQUEST_TIMEOUT", gt=0, le=60)

    @property
    def admin_ids(self) -> frozenset[int]:
        return frozenset(int(x) for x in self.admin_telegram_ids.replace(" ", "").split(",") if x)


@lru_cache
def get_settings() -> Settings:
    return Settings()

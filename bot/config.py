from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str = Field(min_length=1)
    api_base_url: str = "http://localhost:8000"
    api_timeout_seconds: float = Field(default=30.0, gt=0)
    log_level: str = "INFO"
    log_questions: bool = True

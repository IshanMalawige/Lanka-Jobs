from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./jobs.db"
    public_base_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:5173"
    scrape_interval_minutes: int = 360
    gmail_sync_interval_minutes: int = 15
    enable_scheduler: bool = True
    enable_ocr: bool = False
    my_skills: str = ""
    telegram_bot_token: SecretStr = SecretStr("")
    telegram_chat_id: str = ""
    telegram_match_threshold: int = 75


settings = Settings()

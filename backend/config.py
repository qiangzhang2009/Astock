from pydantic_settings import BaseSettings, SettingsConfigDict
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    deepseek_api_key: str = ""

    # SQLite database path (relative to project root)
    database_path: str = "astock.db"

    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()

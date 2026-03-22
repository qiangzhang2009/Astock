from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    deepseek_api_key: str = ""
    database_path: str = "astock.db"
    akshare_data_dir: str = "./data"
    host: str = "0.0.0.0"
    port: int = 8000

    @property
    def db_path(self) -> Path:
        p = Path(self.database_path)
        if not p.is_absolute():
            p = Path(__file__).parent.parent / p
        return p


settings = Settings()

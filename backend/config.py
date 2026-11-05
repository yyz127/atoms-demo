import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ATMOS_", env_file=".env", extra="ignore")
    public_url: str = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000")
    search_url: str = ""
    production: bool = False
    publish_dir: str = "./data/published"
    max_publications: int = 500
    publish_durable: bool = False


settings = Settings()

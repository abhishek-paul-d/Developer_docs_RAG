from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="DEVDOCS_", extra="ignore")

    data_dir: Path = Path("data")
    results_dir: Path = Path("results")
    cache_dir: Path = Path(".cache/llm")
    groq_api_key: str = ""


settings = Settings()

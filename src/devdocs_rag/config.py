from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="DEVDOCS_", extra="ignore")

    data_dir: Path = Path("data")
    results_dir: Path = Path("results")
    cache_dir: Path = Path(".cache/llm")
    docs_repo: str = "pola-rs/polars"
    docs_tag: str = "py-2.0.0"
    library_version: str = "2.0.0"
    chunk_max_tokens: int = 300
    split_seed: int = 0
    split_ratios: tuple[float, float, float] = (0.7, 0.1, 0.2)
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"


settings = Settings()

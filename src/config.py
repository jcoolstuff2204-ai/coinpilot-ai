"""Application configuration loaded from environment variables."""

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    database_path: Path
    coingecko_base_url: str
    openai_api_key: str
    openai_model: str
    backend_url: str


def project_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


settings = Settings(
    database_path=project_path(os.getenv("DATABASE_PATH", "data/coinpilot.db")),
    coingecko_base_url=os.getenv("COINGECKO_BASE_URL", "https://api.coingecko.com/api/v3"),
    openai_api_key=os.getenv("OPENAI_API_KEY", ""),
    openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    backend_url=os.getenv("BACKEND_URL", "http://127.0.0.1:8000"),
)

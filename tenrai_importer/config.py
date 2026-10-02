import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Config:
    database_url: str
    base_url: str
    server_key: str | None
    requests_per_second: float
    requests_per_minute: int
    max_retries: int
    timeout_seconds: float
    user_agent: str
    data_dir: Path

def load_config(require_database=True) -> Config:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if require_database and not database_url:
        raise ValueError("DATABASE_URL is required for database commands")

    key = os.getenv("TENRAI_SERVER_KEY", "").strip() or None
    rps = float(os.getenv("TENRAI_REQUESTS_PER_SECOND", "2"))
    rpm = int(os.getenv("TENRAI_REQUESTS_PER_MINUTE", "90"))

    if rps <= 0 or rps > 4:
        raise ValueError("TENRAI_REQUESTS_PER_SECOND must be > 0 and <= 4")
    if rpm <= 0 or rpm > (300 if key else 120):
        raise ValueError("TENRAI_REQUESTS_PER_MINUTE exceeds the configured Tenrai tier")

    return Config(
        database_url=database_url,
        base_url=os.getenv("TENRAI_BASE_URL", "https://api.tenrai.org/v1").rstrip("/"),
        server_key=key,
        requests_per_second=rps,
        requests_per_minute=rpm,
        max_retries=int(os.getenv("TENRAI_MAX_RETRIES", "6")),
        timeout_seconds=float(os.getenv("TENRAI_TIMEOUT_SECONDS", "30")),
        user_agent=os.getenv("TENRAI_USER_AGENT", "anime-db-importer/2.0"),
        data_dir=Path(os.getenv("TENRAI_DATA_DIR", "./data")).expanduser(),
    )

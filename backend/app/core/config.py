"""Application settings, read from environment variables / the repo-root .env file.

Secrets never live in code: every value here comes from the environment.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> parents[3] is the repository root
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    app_name: str = "FALCON"
    environment: str = "development"

    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5434
    postgres_db: str
    postgres_user: str
    postgres_password: SecretStr  # SecretStr hides the value in logs and error messages

    # --- Sessions & login protection ---
    session_cookie_name: str = "falcon_session"
    # Secure cookies are only sent over HTTPS. Local development uses plain HTTP.
    session_cookie_secure: bool = False
    session_hours: int = 8  # a normal sign-in lasts one work shift
    session_remember_days: int = 7  # "Remember this device"
    login_max_failures: int = 5
    login_lockout_minutes: int = 15

    # --- Evidence storage ---
    # Original evidence files live here (outside the code, ignored by Git).
    storage_dir: Path = REPO_ROOT / "storage"
    max_upload_mb: int = 250

    # --- Extraction ---
    # Phone numbers written without a country code are read as numbers from this region.
    default_phone_region: str = "IN"
    ocr_enabled: bool = True

    # --- Local AI (Ollama) ---
    # Everything runs on this computer: evidence is never sent to a cloud service.
    ai_enabled: bool = True
    ollama_url: str = "http://127.0.0.1:11434"
    ai_chat_model: str = "qwen3:8b"  # tool calling + JSON output; fallback: qwen3:4b
    ai_embed_model: str = "all-minilm"  # all-MiniLM-L6-v2, 384-number vectors
    ai_timeout_seconds: int = 300  # CPU-only machines are slow; be patient
    assistant_max_steps: int = 8

    # Password for the fictional demo users created by the seed script (development only)
    demo_password: SecretStr | None = None

    @property
    def database_url(self) -> str:
        password = self.postgres_password.get_secret_value()
        return (
            f"postgresql+psycopg://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """Load settings once and reuse them (cached)."""
    return Settings()

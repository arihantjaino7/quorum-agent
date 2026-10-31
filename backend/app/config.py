"""Settings loaded from the environment / .env.

Every integration exposes an ``*_enabled`` flag so callers can degrade gracefully
instead of crashing when a key is missing.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    groq_api_key: str = ""
    groq_model_strong: str = "openai/gpt-oss-120b"
    groq_model_fast: str = "llama-3.1-8b-instant"
    groq_model_whisper: str = "whisper-large-v3-turbo"

    # Demo safety net
    demo_replay: bool = True
    demo_clock_start: str = "2026-10-31T09:00:00"
    # In replay mode each agent stays "working" at least this long so the live trace is watchable on stage.
    replay_step_ms: int = 700

    # Integrations
    notion_token: str = ""
    notion_database_id: str = ""
    github_token: str = ""
    github_repo: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Storage
    database_url: str = f"sqlite:///{BACKEND_DIR / 'data' / 'quorum.db'}"
    checkpoint_db: str = str(BACKEND_DIR / "data" / "checkpoints.db")
    embedding_model: str = "BAAI/bge-small-en-v1.5"

    @property
    def groq_enabled(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def notion_enabled(self) -> bool:
        return bool(self.notion_token and self.notion_database_id)

    @property
    def github_enabled(self) -> bool:
        return bool(self.github_token and "/" in self.github_repo and self.github_repo != "owner/repo")

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    @property
    def replay_active(self) -> bool:
        """Replay recordings are used when explicitly enabled or when Groq is unavailable."""
        return self.demo_replay or not self.groq_enabled


@lru_cache
def get_settings() -> Settings:
    return Settings()

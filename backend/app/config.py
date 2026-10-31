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
    groq_model_fast: str = "qwen/qwen3.8-27b"
    groq_model_whisper: str = "whisper-large-v3-turbo"
    # Reasoning effort for models that support it (gpt-oss: low | medium | high). Empty = model default.
    groq_reasoning_strong: str = "low"
    groq_reasoning_fast: str = ""
    groq_timeout_s: float = 30.0
    groq_max_retries: int = 2  # retries after malformed output or a transient error
    # When no GROQ_API_KEY is set, probe Groq once at startup: the key may be a network secret the proxy injects.
    groq_autodetect: bool = True

    # Demo safety net
    demo_replay: bool = True
    demo_clock_start: str = "2026-10-31T09:00:00"
    # In replay mode each agent stays "working" at least this long so the live trace is watchable on stage.
    replay_step_ms: int = 700
    # Save live LLM answers as replay recordings. Only when explicitly asked.
    quorum_record: bool = False

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
    def notion_enabled(self) -> bool:
        return bool(self.notion_token and self.notion_database_id)

    @property
    def github_enabled(self) -> bool:
        return bool(self.github_token and "/" in self.github_repo and self.github_repo != "owner/repo")

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()

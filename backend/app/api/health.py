from fastapi import APIRouter

from app import __version__
from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    s = get_settings()
    return {
        "ok": True,
        "version": __version__,
        "replay": s.replay_active,
        # Phase 1 moves the demo clock into the settings table; until then it is the configured start.
        "clock": s.demo_clock_start,
        "integrations": {
            "groq": s.groq_enabled,
            "notion": s.notion_enabled,
            "github": s.github_enabled,
            "telegram": s.telegram_enabled,
        },
    }

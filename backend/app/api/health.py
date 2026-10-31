from fastapi import APIRouter, Depends
from sqlmodel import Session

from app import __version__
from app.config import get_settings
from app.db import get_session
from app.services import clock

router = APIRouter(tags=["health"])


@router.get("/health")
def health(session: Session = Depends(get_session)) -> dict:
    s = get_settings()
    return {
        "ok": True,
        "version": __version__,
        "replay": s.replay_active,
        "clock": clock.fmt(clock.now(session)),
        "integrations": {
            "groq": s.groq_enabled,
            "notion": s.notion_enabled,
            "github": s.github_enabled,
            "telegram": s.telegram_enabled,
        },
    }

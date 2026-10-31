"""FastAPI entrypoint. Run with: uvicorn app.main:app --reload --port 8000"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app import pipeline
from app.api import clock, decisions, demo, directory, health, runs, tasks
from app.config import get_settings
from app.db import init_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("quorum")


def _log_integrations() -> None:
    s = get_settings()
    flags = {
        "groq": s.groq_enabled,
        "notion": s.notion_enabled,
        "github": s.github_enabled,
        "telegram": s.telegram_enabled,
    }
    for name, enabled in flags.items():
        if not enabled:
            log.warning("[%s] not configured; this feature will degrade gracefully", name)
    log.info("replay mode: %s", "ON" if s.replay_active else "off")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    await pipeline.startup()
    _log_integrations()
    yield
    await pipeline.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(
        lifespan=lifespan,
        title="Quorum",
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        swagger_ui_oauth2_redirect_url="/api/docs/oauth2-redirect",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # local hackathon demo; the frontend dev server runs on another port
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for module in (health, demo, clock, directory, decisions, tasks, runs):
        app.include_router(module.router, prefix="/api")
    return app


app = create_app()

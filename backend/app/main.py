"""FastAPI entrypoint. Run with: uvicorn app.main:app --reload --port 8000"""

import logging
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from app import __version__
from app import pipeline
from app.api import clock, decisions, demo, directory, health, insights, runs, tasks
from app.config import get_settings
from app.db import get_engine, init_db
from app.integrations import llm
from app.services import seed

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("quorum")


def _log_integrations() -> None:
    s = get_settings()
    llm.probe()
    flags = {
        "notion": s.notion_enabled,
        "github": s.github_enabled,
        "telegram": s.telegram_enabled,
    }
    for name, enabled in flags.items():
        if not enabled:
            log.warning("[%s] not configured; this feature will degrade gracefully", name)
    log.info("replay mode: %s", "ON" if llm.replay_active() else "off")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with Session(get_engine()) as session:
        if seed.seed_if_empty(session):
            log.info("empty database: loaded the seed meeting")
    await pipeline.startup()
    _log_integrations()
    yield
    await pipeline.shutdown()


def _serve_frontend(app: FastAPI) -> None:
    """When a built frontend is present (the container image), serve it from the same origin as the API."""
    dist = Path(get_settings().frontend_dist)
    index = dist / "index.html"
    if not index.is_file():
        return
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        target = (dist / path).resolve()
        if path and target.is_file() and dist.resolve() in target.parents:
            return FileResponse(target)
        return FileResponse(index)


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
    for module in (health, demo, clock, directory, insights, decisions, tasks, runs):
        app.include_router(module.router, prefix="/api")
    _serve_frontend(app)
    return app


app = create_app()

import json
import os
from pathlib import Path

import pytest

# Tests always run on replay recordings, never on live Groq (unless marked `live`).
os.environ.setdefault("DEMO_REPLAY", "1")

SEED_DIR = Path(__file__).resolve().parent.parent / "seed"


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def seed_dir() -> Path:
    return SEED_DIR


@pytest.fixture(scope="session")
def expected_debrief2() -> dict:
    return json.loads((SEED_DIR / "expected_debrief2.json").read_text())


def route_exists(client, method: str, path: str) -> bool:
    """True once a phase has mounted the route. Lets guardrail tests switch on automatically."""
    # Use the OpenAPI schema: FastAPI wraps included routers, so app.routes doesn't list nested paths.
    return method.lower() in client.app.openapi()["paths"].get(path, {})

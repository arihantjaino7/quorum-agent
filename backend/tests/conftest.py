import json
import os
import tempfile
from pathlib import Path

import pytest

# Tests always run on replay recordings, never on live Groq (unless marked `live`),
# on a throwaway database, and with no integration keys (whatever is in the developer's .env).
os.environ["DEMO_REPLAY"] = "1"
_tmp = Path(tempfile.mkdtemp(prefix="quorum-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp / 'test.db'}"
os.environ["CHECKPOINT_DB"] = str(_tmp / "checkpoints.db")
os.environ["REPLAY_STEP_MS"] = "0"
os.environ["GROQ_AUTODETECT"] = "0"  # no network probe in tests
os.environ["QUORUM_RECORD"] = "0"
for _key in ("GROQ_API_KEY", "NOTION_TOKEN", "NOTION_DATABASE_ID", "GITHUB_TOKEN", "GITHUB_REPO",
             "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
    os.environ[_key] = ""

SEED_DIR = Path(__file__).resolve().parent.parent / "seed"


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def fresh(client):
    """Reset to the demo starting state before a test."""
    assert client.post("/api/demo/reset").status_code == 200
    return client


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

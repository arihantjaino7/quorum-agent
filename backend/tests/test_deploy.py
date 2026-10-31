"""Deployment behaviour: first-start seeding and serving the built frontend from the API."""

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import Decision, Project
from app.services import seed


def test_seed_if_empty_loads_once():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        assert seed.seed_if_empty(s) is True
        decisions = len(s.exec(select(Decision)).all())
        assert decisions >= 3
        assert seed.seed_if_empty(s) is False
        assert len(s.exec(select(Decision)).all()) == decisions
        assert s.exec(select(Project)).first().name == "Pocket"


def test_frontend_is_served_next_to_the_api(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "index.html").write_text("<html>quorum</html>")
    monkeypatch.setenv("FRONTEND_DIST", str(tmp_path))
    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            self_check(client)
    finally:
        monkeypatch.delenv("FRONTEND_DIST")
        get_settings.cache_clear()


def self_check(client):
    assert client.get("/").text == "<html>quorum</html>"
    assert client.get("/memory").text == "<html>quorum</html>"  # client-side route falls back to the page
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert "root:" not in client.get("/..%2f..%2fetc/passwd").text
    assert client.get("/api/nope").status_code == 404  # API misses stay JSON 404s, not the page
    assert client.get("/api/health").json()["ok"] is True


def test_no_frontend_means_api_only(tmp_path, monkeypatch):
    monkeypatch.setenv("FRONTEND_DIST", str(tmp_path / "missing"))
    from app.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    try:
        assert TestClient(create_app()).get("/").status_code == 404
    finally:
        monkeypatch.delenv("FRONTEND_DIST")
        get_settings.cache_clear()

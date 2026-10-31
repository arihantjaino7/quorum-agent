def test_health_reports_status_and_integrations(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["replay"] is True
    assert body["clock"].startswith("2026-")
    assert set(body["integrations"]) == {"groq", "notion", "github", "telegram"}
    assert all(isinstance(v, bool) for v in body["integrations"].values())


def test_every_route_is_under_api(client):
    app = client.app
    paths = list(app.openapi()["paths"])
    assert "/api/health" in paths
    assert all(p.startswith("/api/") for p in paths), [p for p in paths if not p.startswith("/api/")]
    for url in (app.docs_url, app.openapi_url, app.swagger_ui_oauth2_redirect_url):
        assert url is None or url.startswith("/api/"), url
    assert app.redoc_url is None

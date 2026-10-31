import json
import logging

import httpx
import pytest

from app.config import get_settings
from app.integrations import github_issues

TOKEN = "private-test-access-token"
REPO = "team/pocket"
ISSUE_URL = "https://github.com/team/pocket/issues/42"


@pytest.fixture(autouse=True)
def settings_env(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "")
    monkeypatch.setenv("GITHUB_REPO", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", TOKEN)
    monkeypatch.setenv("GITHUB_REPO", REPO)
    get_settings.cache_clear()


async def test_not_configured_logs_once_without_sending(caplog):
    caplog.set_level(logging.INFO, logger="quorum.github")
    def transport(request):
        pytest.fail("Unconfigured tracker must not make a request")
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        assert await github_issues.create_issue("A task", "Details", client=client) is None
    assert [record.getMessage() for record in caplog.records] == [
        "[github] GITHUB_TOKEN or GITHUB_REPO missing; skipping, task kept locally"
    ]


@pytest.mark.parametrize("repo", ["", "owner/repo", "team", "team/", "/pocket", "team/pocket/extra"])
async def test_incomplete_or_invalid_repository_is_skipped(configured, monkeypatch, repo):
    monkeypatch.setenv("GITHUB_REPO", repo)
    get_settings.cache_clear()
    def transport(request):
        pytest.fail("Invalid repository must not make a request")
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        assert await github_issues.create_issue("A task", "Details", client=client) is None


@pytest.mark.parametrize("labels, expected", [(None, ["quorum"]), ([], []), (["launch", "quorum"], ["launch", "quorum"])])
async def test_success_sends_the_required_headers_and_payload(configured, labels, expected):
    def transport(request):
        assert str(request.url) == "https://api.github.com/repos/team/pocket/issues"
        assert request.method == "POST"
        assert request.headers["Authorization"] == f"Bearer {TOKEN}"
        assert request.headers["Accept"] == "application/vnd.github+json"
        assert request.headers["X-GitHub-Api-Version"] == "2022-11-28"
        assert json.loads(request.content) == {"title": "A task", "body": "Details", "labels": expected}
        assert request.extensions["timeout"] == {"connect": 10.0, "read": 10.0, "write": 10.0, "pool": 10.0}
        return httpx.Response(201, json={"html_url": ISSUE_URL})
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        assert await github_issues.create_issue("A task", "Details", labels, client=client) == ISSUE_URL
        assert not client.is_closed


@pytest.mark.parametrize("status", [422, 401, 500, 200])
async def test_non_created_status_is_logged_without_response_secrets(configured, caplog, status):
    caplog.set_level(logging.INFO)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(status, text=TOKEN))) as client:
        assert await github_issues.create_issue("A task", "Details", client=client) is None
    own_records = [r for r in caplog.records if r.name == "quorum.github"]
    assert len(own_records) == 1 and own_records[0].levelno == logging.WARNING
    assert f"HTTP {status}" in caplog.text
    assert TOKEN not in caplog.text


@pytest.mark.parametrize("response", [httpx.Response(201, text="bad json"), httpx.Response(201, json=[]), httpx.Response(201, json={}), httpx.Response(201, json={"html_url": 123})])
async def test_bad_json_or_missing_url_is_skipped(configured, caplog, response):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: response)) as client:
        assert await github_issues.create_issue("A task", "Details", client=client) is None
    assert len(caplog.records) == 1


@pytest.mark.parametrize("error", [httpx.ReadTimeout, httpx.ConnectError, RuntimeError])
async def test_request_failures_do_not_raise_or_leak_the_token(configured, caplog, error):
    def transport(request):
        raise error(f"Request failed with {TOKEN}")
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        assert await github_issues.create_issue("A task", "Details", client=client) is None
    assert len(caplog.records) == 1
    assert TOKEN not in caplog.text


async def test_own_client_is_closed(configured, monkeypatch):
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(201, json={"html_url": ISSUE_URL})))
    def factory(**kwargs):
        assert kwargs == {"timeout": 10.0}
        return client
    monkeypatch.setattr(github_issues.httpx, "AsyncClient", factory)
    assert await github_issues.create_issue("A task", "Details") == ISSUE_URL
    assert client.is_closed


def test_issue_body_includes_due_phrase_and_every_quote_line():
    body = github_issues.task_issue_body({
        "title": "Redo onboarding", "owner": "Ananya", "due_date": "2026-11-04",
        "raw_due_phrase": "next Wednesday", "source_quote": "Ananya, redo onboarding.\nInclude Android too.",
    }, "Investor sync")
    assert "**Owner:** Ananya" in body
    assert "**Due:** 2026-11-04 [next Wednesday]" in body
    assert "**Meeting:** Investor sync" in body
    assert "> Ananya, redo onboarding.\n> Include Android too." in body
    assert body.endswith("_Created by Quorum after human approval._")


def test_issue_body_without_date_or_optional_fields():
    body = github_issues.task_issue_body({}, "Planning")
    assert "**Owner:** Someone" in body
    assert "**Due:** No due date" in body
    assert "[]" not in body
    assert body.endswith("_Created by Quorum after human approval._")


def test_raw_phrase_is_kept_even_if_no_date_was_resolved():
    body = github_issues.task_issue_body({"raw_due_phrase": "soon", "due_date": None}, "Planning")
    assert "No due date [soon]" in body

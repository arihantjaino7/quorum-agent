import json
import logging

import httpx
import pytest

from app.config import get_settings
from app.integrations import notion

TOKEN = "private-notion-test-token"
DATABASE = "12345678-1234-1234-1234-123456789012"
PAGE_URL = "https://www.notion.so/pocket-task-123"
TASK = {"title": "Redo onboarding", "owner": "Ananya", "due_date": "2026-11-04", "source_quote": "Ananya, redo onboarding for Android."}


@pytest.fixture(autouse=True)
def settings_env(monkeypatch):
    monkeypatch.setenv("NOTION_TOKEN", "")
    monkeypatch.setenv("NOTION_DATABASE_ID", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("NOTION_TOKEN", TOKEN)
    monkeypatch.setenv("NOTION_DATABASE_ID", DATABASE)
    get_settings.cache_clear()


async def test_not_configured_logs_once_without_sending(caplog):
    caplog.set_level(logging.INFO, logger="quorum.notion")
    def transport(request):
        pytest.fail("Unconfigured integration must not make a request")
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        assert await notion.create_task_page(TASK, "Investor sync", client=client) is None
    assert [record.getMessage() for record in caplog.records] == [
        "[notion] NOTION_TOKEN or NOTION_DATABASE_ID missing; skipping, task kept locally"
    ]


@pytest.mark.parametrize("key", ["NOTION_TOKEN", "NOTION_DATABASE_ID"])
async def test_either_missing_setting_skips(configured, monkeypatch, key):
    monkeypatch.setenv(key, "")
    get_settings.cache_clear()
    def transport(request):
        pytest.fail("Incomplete configuration must not make a request")
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        assert await notion.create_task_page(TASK, "Investor sync", client=client) is None


async def test_success_sends_exact_properties_blocks_and_headers(configured):
    def transport(request):
        assert str(request.url) == "https://api.notion.com/v1/pages"
        assert request.method == "POST"
        assert request.headers["Authorization"] == f"Bearer {TOKEN}"
        assert request.headers["Notion-Version"] == "2022-06-28"
        assert request.headers["Content-Type"] == "application/json"
        assert request.extensions["timeout"] == {"connect": 10.0, "read": 10.0, "write": 10.0, "pool": 10.0}
        assert json.loads(request.content) == {
            "parent": {"database_id": DATABASE},
            "properties": {
                "Name": {"title": [{"text": {"content": "Redo onboarding"}}]},
                "Owner": {"rich_text": [{"text": {"content": "Ananya"}}]},
                "Due": {"date": {"start": "2026-11-04"}},
                "Status": {"select": {"name": "To do"}},
                "Meeting": {"rich_text": [{"text": {"content": "Investor sync"}}]},
            },
            "children": [
                {"object": "block", "type": "quote", "quote": {"rich_text": [{"text": {"content": TASK["source_quote"]}}]}},
                {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": "Created by Quorum after human approval."}}]}},
            ],
        }
        return httpx.Response(200, json={"url": PAGE_URL})
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        assert await notion.create_task_page(TASK, "Investor sync", client=client) == PAGE_URL
        assert not client.is_closed


@pytest.mark.parametrize("owner", ["", None, "  "])
async def test_missing_owner_and_date_are_omitted(configured, owner):
    def transport(request):
        properties = json.loads(request.content)["properties"]
        assert "Owner" not in properties and "Due" not in properties
        assert properties["Status"] == {"select": {"name": "To do"}}
        return httpx.Response(200, json={"url": PAGE_URL})
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        assert await notion.create_task_page({**TASK, "owner": owner, "due_date": None}, "Meeting", client=client) == PAGE_URL


async def test_missing_optional_task_fields_and_quote_do_not_crash(configured):
    def transport(request):
        body = json.loads(request.content)
        assert body["properties"]["Name"] == {"title": [{"text": {"content": "Untitled task"}}]}
        assert "Owner" not in body["properties"] and "Due" not in body["properties"]
        assert len(body["children"]) == 1 and body["children"][0]["type"] == "paragraph"
        return httpx.Response(200, json={"url": PAGE_URL})
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        assert await notion.create_task_page({}, "Meeting", client=client) == PAGE_URL


@pytest.mark.parametrize("status", [400, 401, 500, 201])
async def test_failure_status_logs_one_safe_warning(configured, caplog, status):
    caplog.set_level(logging.INFO)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(status, text=TOKEN))) as client:
        assert await notion.create_task_page(TASK, "Meeting", client=client) is None
    records = [r for r in caplog.records if r.name == "quorum.notion"]
    assert len(records) == 1 and records[0].levelno == logging.WARNING
    assert f"HTTP {status}" in caplog.text
    assert TOKEN not in caplog.text


@pytest.mark.parametrize("response", [httpx.Response(200, text="bad json"), httpx.Response(200, json=[]), httpx.Response(200, json={}), httpx.Response(200, json={"url": 123})])
async def test_bad_json_and_missing_page_url_skip_cleanly(configured, caplog, response):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: response)) as client:
        assert await notion.create_task_page(TASK, "Meeting", client=client) is None
    assert len(caplog.records) == 1


@pytest.mark.parametrize("error", [httpx.ReadTimeout, httpx.ConnectError, RuntimeError])
async def test_request_failures_do_not_raise_or_expose_tokens(configured, caplog, error):
    def transport(request):
        raise error(f"A failure containing {TOKEN}")
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        assert await notion.create_task_page(TASK, "Meeting", client=client) is None
    assert len(caplog.records) == 1
    assert TOKEN not in caplog.text


async def test_all_text_fields_are_truncated_without_splitting_unicode(configured):
    long_text = "é🌿" * 1500
    def transport(request):
        body = json.loads(request.content)
        fields = [body["properties"]["Name"]["title"], body["properties"]["Owner"]["rich_text"],
                  body["properties"]["Meeting"]["rich_text"], body["children"][0]["quote"]["rich_text"]]
        for field in fields:
            content = field[0]["text"]["content"]
            assert content == long_text[:2000]
            assert len(content) == 2000
            assert content.encode("utf-8").decode("utf-8") == content
        return httpx.Response(200, json={"url": PAGE_URL})
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        task = {**TASK, "title": long_text, "owner": long_text, "source_quote": long_text}
        assert await notion.create_task_page(task, long_text, client=client) == PAGE_URL


async def test_created_client_is_closed(configured, monkeypatch):
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"url": PAGE_URL})))
    def factory(**kwargs):
        assert kwargs == {"timeout": 10.0}
        return client
    monkeypatch.setattr(notion.httpx, "AsyncClient", factory)
    assert await notion.create_task_page(TASK, "Meeting") == PAGE_URL
    assert client.is_closed

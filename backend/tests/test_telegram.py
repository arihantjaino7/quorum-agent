import json
import logging

import httpx
import pytest

from app.config import get_settings
from app.integrations import telegram

TOKEN = "123456:private-test-token"
CHAT = "-1001234567890"


@pytest.fixture(autouse=True)
def settings_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", CHAT)
    get_settings.cache_clear()


async def test_not_configured_logs_one_line_and_the_message(caplog):
    caplog.set_level(logging.INFO, logger="quorum.telegram")
    result = await telegram.send_message("Priya, a reminder.\nDue tomorrow.")
    assert result == telegram.SendResult(False, "log", "not configured")
    assert len(caplog.records) == 1
    assert "[telegram] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing; skipping, message logged" in caplog.text
    assert "Priya, a reminder." in caplog.text
    assert "Due tomorrow." in caplog.text
    assert "\n" not in caplog.records[0].getMessage()


@pytest.mark.parametrize("missing", ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"])
async def test_either_missing_setting_skips_without_a_request(configured, monkeypatch, missing):
    monkeypatch.setenv(missing, "")
    get_settings.cache_clear()
    def transport(request):
        pytest.fail("An unconfigured sender must not make a request")
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        assert (await telegram.send_message("Hello", client=client)).detail == "not configured"


async def test_success_posts_exact_plain_text_payload_and_keeps_borrowed_client(configured, caplog):
    caplog.set_level(logging.INFO)
    def transport(request):
        assert request.method == "POST"
        assert str(request.url) == f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        assert json.loads(request.content) == {"chat_id": CHAT, "text": "**Hello**", "disable_web_page_preview": True}
        assert request.extensions["timeout"] == {"connect": 10.0, "read": 10.0, "write": 10.0, "pool": 10.0}
        return httpx.Response(200, json={"ok": True})
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        assert await telegram.send_message("**Hello**", client=client) == telegram.SendResult(True, "telegram", "sent")
        assert not client.is_closed
    assert TOKEN not in caplog.text
    assert "[redacted]" in caplog.text


@pytest.mark.parametrize("status", [500, 401, 429])
async def test_http_error_returns_a_log_result(configured, caplog, status):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(status, text=TOKEN))) as client:
        result = await telegram.send_message("Hello", client=client)
    assert result == telegram.SendResult(False, "log", f"HTTP {status}")
    assert len([r for r in caplog.records if r.name == "quorum.telegram"]) == 1
    assert TOKEN not in caplog.text


async def test_api_rejection_does_not_log_response_description(configured, caplog):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"ok": False, "description": TOKEN}))) as client:
        result = await telegram.send_message("Hello", client=client)
    assert result == telegram.SendResult(False, "log", "API rejected message")
    assert TOKEN not in caplog.text


@pytest.mark.parametrize("response", [httpx.Response(200, text="not json"), httpx.Response(200, json=[]), httpx.Response(200, json={"ok": "true"})])
async def test_malformed_or_unconfirmed_success_is_skipped(configured, response):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: response)) as client:
        assert not (await telegram.send_message("Hello", client=client)).sent


@pytest.mark.parametrize("error", [httpx.ReadTimeout, httpx.ConnectError, RuntimeError])
async def test_request_failures_never_raise_or_expose_tokens(configured, caplog, error):
    caplog.set_level(logging.INFO)
    filters_before = list(logging.getLogger("httpx").filters)
    def transport(request):
        raise error(f"Failed URL containing {TOKEN}")
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        result = await telegram.send_message("Hello", client=client)
    assert result.channel == "log" and not result.sent
    assert TOKEN not in caplog.text
    assert logging.getLogger("httpx").filters == filters_before


async def test_sender_owns_and_closes_a_client_when_none_is_passed(configured, monkeypatch):
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"ok": True})))
    def factory(**kwargs):
        assert kwargs == {"timeout": 10.0}
        return client
    monkeypatch.setattr(telegram.httpx, "AsyncClient", factory)
    assert (await telegram.send_message("Hello")).sent
    assert client.is_closed


def test_reminder_format_with_an_iso_date():
    assert telegram.format_reminder({"owner": "Ananya", "title": "Redo onboarding", "due_date": "2026-11-04"}) == '⏰ Ananya: "Redo onboarding" is due Wed 4 Nov.'


@pytest.mark.parametrize("due", [None, "", "bad-date"])
def test_reminder_missing_owner_or_date_has_a_safe_fallback(due):
    assert telegram.format_reminder({"title": "Redo onboarding", "due_date": due}) == '⏰ Someone: "Redo onboarding" is due soon.'


def test_heads_up_keeps_the_body_plain_text():
    assert telegram.format_heads_up("Rahul", "**Launch moved.**\nKeep the listing date.") == "📣 Rahul, here's what changed for you:\n\n**Launch moved.**\nKeep the listing date."

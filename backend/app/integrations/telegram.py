"""Send plain-text team reminders; unavailable delivery degrades to a log result."""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
import logging
from urllib.parse import quote

import httpx

from app.config import get_settings

log = logging.getLogger("quorum.telegram")


@dataclass
class SendResult:
    sent: bool
    channel: str
    detail: str


class _RedactToken(logging.Filter):
    def __init__(self, token: str) -> None:
        super().__init__()
        self.secrets = (token, quote(token, safe=""))

    def filter(self, record: logging.LogRecord) -> bool:
        original = record.getMessage()
        redacted = original
        for secret in self.secrets:
            redacted = redacted.replace(secret, "[redacted]")
        if redacted != original:
            record.msg, record.args = redacted, ()
        return True


@contextmanager
def _redact_request_logs(token: str):
    # The token is part of the Bot API URL, including in httpx's normal INFO log.
    logger = logging.getLogger("httpx")
    redactor = _RedactToken(token)
    logger.addFilter(redactor)
    try:
        yield
    finally:
        logger.removeFilter(redactor)


def _failed(reason: str) -> SendResult:
    log.warning("[telegram] %s; delivery skipped", reason)
    return SendResult(False, "log", reason)


async def send_message(text: str, *, client: httpx.AsyncClient | None = None) -> SendResult:
    settings = get_settings()
    if not settings.telegram_enabled:
        # Keep multiline messages in one log line, with their line breaks visible.
        message = text.replace("\r", "\\r").replace("\n", "\\n")
        log.info(
            "[telegram] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing; skipping, message logged | %s",
            message,
        )
        return SendResult(False, "log", "not configured")

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {"chat_id": settings.telegram_chat_id, "text": text, "disable_web_page_preview": True}
    try:
        with _redact_request_logs(settings.telegram_bot_token):
            if client is None:
                async with httpx.AsyncClient(timeout=10.0) as owned:
                    response = await owned.post(url, json=payload, timeout=10.0)
            else:
                response = await client.post(url, json=payload, timeout=10.0)
        if response.status_code != 200:
            return _failed(f"HTTP {response.status_code}")
        try:
            body = response.json()
        except ValueError:
            return _failed("invalid response")
        if not isinstance(body, dict):
            return _failed("invalid response")
        if body.get("ok") is not True:
            return _failed("API rejected message")
        return SendResult(True, "telegram", "sent")
    except httpx.TimeoutException:
        return _failed("request timed out")
    except Exception:
        # Exception text and response bodies can contain credential-bearing URLs.
        return _failed("request failed")


def format_reminder(task: dict) -> str:
    owner = task.get("owner") or "Someone"
    title = task.get("title") or "Untitled task"
    due = task.get("due_date")
    try:
        deadline = date.fromisoformat(due) if due else None
    except (TypeError, ValueError):
        deadline = None
    if deadline is None:
        return f'⏰ {owner}: "{title}" is due soon.'
    weekdays = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    when = f"{weekdays[deadline.weekday()]} {deadline.day} {months[deadline.month - 1]}"
    return f'⏰ {owner}: "{title}" is due {when}.'


def format_heads_up(person: str, message_md: str) -> str:
    return f"📣 {person or 'Someone'}, here's what changed for you:\n\n{message_md}"

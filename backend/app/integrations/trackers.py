"""Tracker and chat adapters used by the executor.

Tries Notion first, then GitHub Issues, then keeps the task local (tracker_url stays null). Each integration
lives in its own module and checks its own config; this adapter only picks the first one that yields a URL and
never raises. If an integration module isn't implemented yet it is skipped with one log line.
"""

import logging
from types import ModuleType

log = logging.getLogger("quorum.trackers")


def _module(name: str) -> ModuleType | None:
    import importlib

    try:
        return importlib.import_module(f"app.integrations.{name}")
    except Exception as e:  # pragma: no cover - defensive
        log.warning("[%s] integration unavailable: %s", name, e)
        return None


async def create_task_link(task: dict, meeting_title: str) -> str | None:
    """Create the task in the first configured tracker; return its URL, or None to keep it local."""
    notion = _module("notion")
    fn = getattr(notion, "create_task_page", None)
    if fn:
        try:
            if url := await fn(task, meeting_title):
                return url
        except Exception as e:
            log.warning("[notion] failed (%s); trying the next tracker", type(e).__name__)
    github = _module("github_issues")
    fn = getattr(github, "create_issue", None)
    if fn:
        try:
            body = github.task_issue_body(task, meeting_title) if hasattr(github, "task_issue_body") else task["title"]
            if url := await fn(task["title"], body, ["quorum"]):
                return url
        except Exception as e:
            log.warning("[github] failed (%s); keeping the task local", type(e).__name__)
    if not fn and not getattr(notion, "create_task_page", None):
        log.info("[trackers] no tracker integration available; task kept locally")
    return None


async def send_chat(text: str) -> str:
    """Send a message to the team chat. Returns the channel used: "telegram" or "log"."""
    telegram = _module("telegram")
    fn = getattr(telegram, "send_message", None)
    if fn:
        try:
            result = await fn(text)
            return getattr(result, "channel", "log")
        except Exception as e:
            log.warning("[telegram] failed (%s); message logged", type(e).__name__)
    log.info("[telegram] message logged: %s", text)
    return "log"

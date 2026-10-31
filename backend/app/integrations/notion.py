"""Create approved tasks in a Notion database, keeping work local on failure.

Create these exact database properties before enabling the integration:
``Name`` (title), ``Owner`` (rich text), ``Due`` (date), ``Status`` (select,
with a ``To do`` option), and ``Meeting`` (rich text).
"""

import logging

import httpx

from app.config import get_settings

log = logging.getLogger("quorum.notion")
_FOOTER = "Created by Quorum after human approval."


def _rich_text(value: str) -> list[dict]:
    # Slice characters, not encoded bytes, so multibyte text is never split.
    return [{"text": {"content": str(value)[:2000]}}]


def _failed(reason: str) -> None:
    log.warning("[notion] %s; task kept locally", reason)


async def create_task_page(
    task: dict, meeting_title: str, *, client: httpx.AsyncClient | None = None,
) -> str | None:
    settings = get_settings()
    if not settings.notion_enabled:
        log.info("[notion] NOTION_TOKEN or NOTION_DATABASE_ID missing; skipping, task kept locally")
        return None

    properties = {"Name": {"title": _rich_text(task.get("title") or "Untitled task")}}
    owner = str(task.get("owner") or "").strip()
    if owner:
        properties["Owner"] = {"rich_text": _rich_text(owner)}
    due = task.get("due_date")
    if due is not None:
        properties["Due"] = {"date": {"start": due}}
    properties["Status"] = {"select": {"name": "To do"}}
    properties["Meeting"] = {"rich_text": _rich_text(meeting_title)}

    children = []
    source_quote = task.get("source_quote")
    if source_quote:
        children.append({"object": "block", "type": "quote", "quote": {"rich_text": _rich_text(source_quote)}})
    children.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rich_text(_FOOTER)}})
    payload = {"parent": {"database_id": settings.notion_database_id}, "properties": properties, "children": children}
    headers = {
        "Authorization": f"Bearer {settings.notion_token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    try:
        if client is None:
            async with httpx.AsyncClient(timeout=10.0) as owned:
                response = await owned.post("https://api.notion.com/v1/pages", headers=headers, json=payload, timeout=10.0)
        else:
            response = await client.post("https://api.notion.com/v1/pages", headers=headers, json=payload, timeout=10.0)
        if response.status_code != 200:
            return _failed(f"HTTP {response.status_code}")
        try:
            result = response.json()
        except ValueError:
            return _failed("invalid response")
        page_url = result.get("url") if isinstance(result, dict) else None
        if not isinstance(page_url, str) or not page_url.strip():
            return _failed("response missing page URL")
        return page_url
    except httpx.TimeoutException:
        return _failed("request timed out")
    except Exception:
        # Keep credential-bearing exception strings and response bodies out of logs.
        return _failed("request failed")

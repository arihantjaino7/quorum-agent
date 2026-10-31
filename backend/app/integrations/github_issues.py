"""Create fallback tracker issues after approval, or keep work local on failure."""

import logging

import httpx

from app.config import get_settings

log = logging.getLogger("quorum.github")


def _failed(reason: str) -> None:
    log.warning("[github] %s; task kept locally", reason)


async def create_issue(
    title: str, body: str, labels: list[str] | None = None, *,
    client: httpx.AsyncClient | None = None,
) -> str | None:
    settings = get_settings()
    repo = settings.github_repo.strip()
    parts = repo.split("/")
    if not settings.github_enabled or len(parts) != 2 or not all(parts):
        log.info("[github] GITHUB_TOKEN or GITHUB_REPO missing; skipping, task kept locally")
        return None

    url = f"https://api.github.com/repos/{repo}/issues"
    headers = {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {"title": title, "body": body, "labels": labels if labels is not None else ["quorum"]}
    try:
        if client is None:
            async with httpx.AsyncClient(timeout=10.0) as owned:
                response = await owned.post(url, headers=headers, json=payload, timeout=10.0)
        else:
            response = await client.post(url, headers=headers, json=payload, timeout=10.0)
        if response.status_code != 201:
            return _failed(f"HTTP {response.status_code}")
        try:
            result = response.json()
        except ValueError:
            return _failed("invalid response")
        issue_url = result.get("html_url") if isinstance(result, dict) else None
        if not isinstance(issue_url, str) or not issue_url.strip():
            return _failed("response missing issue URL")
        return issue_url
    except httpx.TimeoutException:
        return _failed("request timed out")
    except Exception:
        # Responses and exception strings may contain credentials; log only fixed reasons.
        return _failed("request failed")


def task_issue_body(task: dict, meeting_title: str) -> str:
    title = task.get("title") or "Untitled task"
    owner = task.get("owner") or "Someone"
    due = task.get("due_date") or "No due date"
    raw = str(task.get("raw_due_phrase") or "").strip()
    quote = str(task.get("source_quote") or "").strip()
    deadline = f"{due} [{raw}]" if raw else str(due)
    sections = [
        f"## {title}",
        f"**Owner:** {owner}\n**Due:** {deadline}\n**Meeting:** {meeting_title}",
    ]
    if quote:
        sections.append("\n".join(f"> {line}" for line in quote.splitlines()))
    sections.append("_Created by Quorum after human approval._")
    return "\n\n".join(sections)

# Tasks for Codex (handed over by Claude Code, 31 Oct 2026)

Four small, self-contained backend modules. Each one is a stub today, has a fixed interface below, and is tested
without any network. Claude Code will wire them into the pipeline later (Phases 6, 10, 14), so **keep the interfaces
exactly as written**.

Paste the **shared rules** first, then the tasks one at a time (or all four together). Codex can do them in any order.

---

## Shared rules (paste this first)

```text
You're working in the quorum-agent repo. Read /AGENTS.md and /CLAUDE.md first.

Branch: create `codex/backend-modules` from `origin/claude/nice-mayer-1wmx7b`, and do all four tasks there
(one commit per task). Push that branch. Do not push to any other branch, and do not open a pull request.

Rules:
- Touch ONLY the files the task names. Do not edit config.py, CONTRACT.md, requirements.txt, README, the frontend,
  or any other module. If you think another file needs changing, write it in your final message instead.
- No network in tests: use httpx.MockTransport (httpx is already installed). No new dependencies.
- Never crash on a missing key or a failed request: log one clear line and return the "skipped" value.
- No model names or AI-tool names in code, comments or commit messages.
- Before each commit run `cd backend && pytest -q`; everything must pass (currently 133 passed, 2 skipped).
- Settings come from `app.config.get_settings()` (cached with lru_cache). In tests, set env vars with
  monkeypatch and call `get_settings.cache_clear()` before and after (use a fixture).
- When done, reply with: the commit list, the test count, and anything you were unsure about.
```

---

## Task 1: Transcript parsers

```text
Task 1: implement backend/app/services/ingest_parsing.py and add backend/tests/test_ingest_parsing.py.
Also add two sample files: backend/seed/samples/meeting1.vtt and backend/seed/samples/meeting1.srt, made from
backend/seed/meeting1.txt (same speakers and lines, plausible timestamps). Touch no other files.

Pure Python standard library only (do not use webvtt-py). Interface (keep it exactly):

    from dataclasses import dataclass

    class UnsupportedFormat(ValueError): ...

    @dataclass
    class ParsedTranscript:
        text: str            # one "Name: line" per line, joined with "\n"; lines without a speaker have no prefix
        speakers: list[str]  # unique speaker names in order of first appearance

    def parse_text(raw: str) -> ParsedTranscript
    def parse_vtt(content: str) -> ParsedTranscript
    def parse_srt(content: str) -> ParsedTranscript
    def parse_file(filename: str, data: bytes) -> ParsedTranscript

Rules:
- parse_text: accepts "Name: line", "NAME: line", "Name (PM): line" (speaker = "Name"), and an optional leading
  timestamp like "[00:01:02] Name: line" or "00:01 Name: line" (strip the timestamp). A line with no speaker
  continues the previous speaker's turn (append it to that line with a space). Blank lines are ignored.
  Don't treat "Note: ..." style prose as a speaker unless the name looks like a person: 1-3 words, each starting
  with a capital letter, no digits, at most 30 characters.
- parse_vtt: skip the WEBVTT header, NOTE/STYLE/REGION blocks, cue ids and timing lines. The speaker comes from a
  <v Name> voice tag or a "Name: " prefix in the cue text. Strip all other tags (<c>, <i>, <b>, timestamps).
  Merge consecutive cues by the same speaker into one line.
- parse_srt: skip index and timing lines; speaker from a "Name: " prefix; strip simple HTML tags; merge
  consecutive cues by the same speaker.
- parse_file: dispatch on the extension (.txt/.md → parse_text, .vtt → parse_vtt, .srt → parse_srt,
  case-insensitive); decode UTF-8 and strip a BOM; any other extension raises UnsupportedFormat with a message
  that lists the supported types.
- Collapse runs of whitespace inside lines and trim them.

Tests (at least 12): each format, voice tags, merging, continuation lines, timestamps, "(PM)" roles, BOM,
CRLF line endings, an unsupported extension, empty input, and that parsing samples/meeting1.vtt and
samples/meeting1.srt produces the same speakers ["Priya", "Rahul", "Ananya"] and the same text as
parse_text(meeting1.txt).
Commit message: "Transcript parsers for text, .vtt and .srt"
```

---

## Task 2: Telegram sender

```text
Task 2: implement backend/app/integrations/telegram.py and add backend/tests/test_telegram.py. Touch no other files.

Interface (keep it exactly):

    from dataclasses import dataclass

    @dataclass
    class SendResult:
        sent: bool
        channel: str   # "telegram" when delivered, "log" when skipped or failed
        detail: str    # short human-readable reason

    async def send_message(text: str, *, client: httpx.AsyncClient | None = None) -> SendResult
    def format_reminder(task: dict) -> str
    def format_heads_up(person: str, message_md: str) -> str

Rules:
- Settings: get_settings().telegram_enabled, .telegram_bot_token, .telegram_chat_id.
- Not configured: log exactly one line via logging.getLogger("quorum.telegram"):
  "[telegram] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing; skipping, message logged"
  plus the message text at INFO, and return SendResult(False, "log", "not configured").
- Configured: POST https://api.telegram.org/bot<token>/sendMessage with JSON
  {"chat_id": <chat_id>, "text": <text>, "disable_web_page_preview": true}, 10 s timeout. No parse_mode (plain text).
  Success = HTTP 200 and body {"ok": true} → SendResult(True, "telegram", "sent").
  Any HTTP error, timeout, or {"ok": false} → log one warning line (never include the token) and return
  SendResult(False, "log", <reason>). Never raise.
- If no client is passed, create one with `async with httpx.AsyncClient(...)`.
- Messages are addressed by name because everyone shares one group chat:
  format_reminder({"owner": "Ananya", "title": "Redo onboarding", "due_date": "2026-11-04"}) →
  "⏰ Ananya: \"Redo onboarding\" is due Wed 4 Nov." (owner missing → "Someone"; due_date None → "is due soon").
  format_heads_up("Rahul", md) → "📣 Rahul, here's what changed for you:\n\n" + md.

Tests (at least 8) with httpx.MockTransport: not configured; success (assert URL, JSON body, chat_id); HTTP 500;
{"ok": false}; timeout (transport raises httpx.ReadTimeout); the token never appears in log output; both formatters.
pytest-asyncio is installed with asyncio_mode = auto (backend/pytest.ini), so plain `async def test_...` works.
Commit message: "Telegram sender with graceful skip"
```

---

## Task 3: GitHub Issues fallback tracker

```text
Task 3: implement backend/app/integrations/github_issues.py and add backend/tests/test_github_issues.py.
Touch no other files.

Interface (keep it exactly):

    async def create_issue(title: str, body: str, labels: list[str] | None = None, *,
                           client: httpx.AsyncClient | None = None) -> str | None   # the issue's html_url
    def task_issue_body(task: dict, meeting_title: str) -> str

Rules:
- Settings: get_settings().github_enabled, .github_token, .github_repo ("owner/name").
- Not configured: log "[github] GITHUB_TOKEN or GITHUB_REPO missing; skipping, task kept locally" and return None.
- Configured: POST https://api.github.com/repos/<owner>/<name>/issues with headers
  Authorization: Bearer <token>, Accept: application/vnd.github+json, X-GitHub-Api-Version: 2022-11-28,
  JSON {"title", "body", "labels"} (labels default ["quorum"]). 10 s timeout. Return html_url on 201.
  Any other status, timeout or bad JSON → log one warning (never include the token) and return None. Never raise.
- task_issue_body: Markdown with the owner, due date (or "No due date") with the raw phrase in brackets when
  present, the meeting title, the source quote as a > blockquote, and a last line
  "_Created by Quorum after human approval._"
  Task dict keys: title, owner, due_date (ISO or None), raw_due_phrase, source_quote.

Tests (at least 7) with httpx.MockTransport: not configured; success (assert URL, headers, JSON); 422; 401;
timeout; token not in logs; body formatting with and without a due date.
Commit message: "GitHub Issues fallback tracker"
```

---

## Task 4: Notion task pages

```text
Task 4: implement backend/app/integrations/notion.py and add backend/tests/test_notion.py. Touch no other files.

Use httpx directly against the Notion REST API (not notion-client), so it can be tested with MockTransport.

Interface (keep it exactly):

    async def create_task_page(task: dict, meeting_title: str, *,
                               client: httpx.AsyncClient | None = None) -> str | None   # the page url

Rules:
- Settings: get_settings().notion_enabled, .notion_token, .notion_database_id.
- Not configured: log "[notion] NOTION_TOKEN or NOTION_DATABASE_ID missing; skipping, task kept locally" and
  return None.
- Configured: POST https://api.notion.com/v1/pages with headers Authorization: Bearer <token>,
  Notion-Version: 2022-06-28, Content-Type: application/json. 10 s timeout. Body:
    parent: {"database_id": <id>}
    properties (these exact property names; document them in the module docstring so the user can create the
    database):
      "Name":    title     = task title
      "Owner":   rich_text = owner (omit the property if empty)
      "Due":     date      = {"start": due_date} (omit if None)
      "Status":  select    = {"name": "To do"}
      "Meeting": rich_text = meeting_title
    children: one quote block with the source_quote (omit if empty) and one paragraph
      "Created by Quorum after human approval."
  Return the response's "url" on 200. Any other status, timeout or bad JSON → log one warning (never include
  the token) and return None. Never raise.
- Notion rejects rich_text content over 2000 characters: truncate safely.

Tests (at least 7) with httpx.MockTransport: not configured; success (assert URL, headers and the exact JSON);
owner/due omitted when empty; 400; 401; timeout; token not in logs; long text truncated.
Commit message: "Notion task pages"
```

---

## After Codex finishes

Tell Claude Code "Codex is done". Claude Code will review the `codex/backend-modules` branch, run the tests, merge it,
and wire the modules into the executor (Phase 6), reminders (Phase 10) and file upload (Phase 14).

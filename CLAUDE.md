# CLAUDE.md: Quorum ("meetings that remember")

Context for every Claude Code session in this repo. Read this first, then `PLAN_BACKEND.md` for the current phase.

## Standing rules (non-negotiable)
1. **VOICE_LOG first.** At the start of every task, append the user's exact prompt, verbatim with a UTC
   timestamp, to `VOICE_LOG.md` under a `## [Claude Code] <timestamp> — <label>` heading. Every prompt is
   dictated through Wispr Flow, and the log is our evidence for the judges. Also log answers to clarifying questions.
2. **Ownership.** Claude Code owns `/backend`, `/frontend` (since 31 Oct, by the user's decision) and the root files.
   Codex works only on tasks Claude hands over through the user. Stage paths explicitly (no `git add -A`).
3. **Contract.** `CONTRACT.md` is the source of truth. Changes are additive only: add the change to the
   Changes block at the top, then tell the user so they can relay it to Codex.
4. **Phases.** Work one phase of `PLAN_BACKEND.md` at a time. Finish its tests, commit, then stop and wait for "go".
5. **Never crash on a missing key.** Every integration checks its config, logs one clear line
   (`[notion] NOTION_TOKEN missing; skipping, task kept locally`), and degrades.
6. No model identifiers in commits, PRs, or code comments.
7. **Consult before deciding.** Any new product or design decision not already settled here or in
   `PLAN_BACKEND.md` goes to the user first (interactive question), before code. Improvement ideas go into
   `IDEAS.md` and are not built until the user reviews them (planned for the end).

## Settled decisions (log)
- Demo clock is **frozen**: it only moves when set via `POST /api/clock`.
- IDs: seed items get fixed readable IDs (`dec_m1_platform`); live items get prefixed short IDs
  (`mtg_`, `dec_`, `tsk_`, `cfl_`, `rpl_`, `q_`, `run_` + 8 hex chars).
- Telegram: **one team group chat** (`TELEGRAM_CHAT_ID`); messages are addressed by name.
- Replay mode for seed demo inputs; tests use recordings.
- Contract changes are additive only and logged in CONTRACT.md's Changes block.
- Replay pacing: each agent shows as working for at least `REPLAY_STEP_MS` (700ms) in replay mode only; 0 in tests.
- The SSE stream stays open after `review_ready` and also shows executor/memory_writer, ending with an `agent_end` from `pipeline`.
- Parallel pending runs per project are allowed; each is checked only against approved memory.
- An agent failure stops the run (`error` event); `POST /api/runs/{id}/retry` resumes from the failed agent.
- The first approve/reject wins (later ones → 409); pending reviews never expire.
- LLM calls: 2 retries on malformed structured output (each retry tells the model what was wrong); 30s timeout per call.
- Recordings are saved only when `QUORUM_RECORD=1`; nothing is auto-recorded.
- Groq availability: `GROQ_API_KEY` if set, otherwise a one-time probe of Groq's model list at startup (the key can
  live as a network secret that the proxy injects). Tests disable the probe (`GROQ_AUTODETECT=0`).
- Models are chosen by a bake-off (`scripts/bakeoff.py`) on debrief2; the user picks strong + fast from the results.
- Groq stays on the **free tier** (tight per-minute token limits); the seed demo relies on replay, and calls are paced.
- Rate limits (429): if Groq's suggested wait is ≤ 30s, wait and retry (counts as a retry) and show "waiting for Groq…"
  in the trace (`agent_progress` event); otherwise fail with a clear rate-limit error + Retry.
- Groq's own `json_validate_failed` counts as malformed output (retried with feedback).
- **Models (bake-off winner):** strong = `openai/gpt-oss-120b` at reasoning effort `low`; fast = `qwen/qwen3.8-27b`.
  `gpt-oss-20b` is unreliable here (invalid JSON, wrong dates). Separate models = separate free-tier quotas.
- **Frontend ownership changed:** Claude Code now owns `/frontend` too (Codex's prototype merged from
  `codex/quorum-frontend-prototype`). Codex only does small, self-contained tasks that Claude writes up for the user to hand over.
- **UI redesign:** one-screen "cockpit" layout (you said | agents → result | memory, approve bar at the bottom).
  Order: backend Phases 4–5 first, then the UI.
- **UI concept (31 Oct): "The Paper"**: a living newspaper (warm paper texture, giant condensed serif headlines, black bands,
  column rules). Decisions = headlines; a conflict = a red-ink CORRECTION striking through the old headline; approve = a
  rubber stamp; memory = archive of back issues; weekly digest = "this week's edition". UI weighs ~25% of the score.
- **First view:** only one giant question ("What happened in your meeting?"), a blinking cursor for Wispr, and a small
  "try the sample debrief" link. Nothing else.
- **Reveal:** the story unfolds downward, stage by stage (cleaned → agents → conflicts → approve stamp → memory updated);
  the top nav (Memory, Ask, Board, Digest, Radar…) fades in only after the first approval. Lots of smooth animation.
- External design references are never named in the product, repo or logs (links are redacted in VOICE_LOG).
- `source_quote` = the **exact spoken words** from the raw text. If the model's quote isn't found verbatim, snap it to
  the closest sentence of the raw text (logged).
- Transcripts ("Name: line") get **light cleanup**: speaker lines and attributions are kept; only fillers and small talk
  are removed, and dates are resolved. Voice debriefs get full cleanup.
- Fillers appear as **one summary correction** ("Removed N fillers: um, uh, …"), never one per word.
- qwen free-tier "request too large" (1,000 output tokens/min cap): the fast-tier call is retried once on the strong
  model (gpt-oss-120b @low), with an `agent_progress` note "qwen over free-tier limit; using backup model".
- Dates: a deterministic Python resolver (`services/dates.py`) checks the LLM's ISO dates and overrides them when it
  can parse the phrase.
- **Conflicts (Phase 5):** severity is set by the conflict agent using fixed rules (HIGH = reverses scope/vendor/platform
  or invalidates work underway; MEDIUM = moves a date or amends; LOW = minor). Python checks: deadline collision =
  medium, overload = low. Affected tasks are picked by the agent from the project's open tasks.
- Deadline collision = a task due after the newest launch/release date decision, or a new task due before the meeting
  date. Overload = 3+ tasks for one owner on one day, counting new and existing open tasks (flagged only if a new task is involved).
- Retrieval = same `topic_key` ∪ top embedding matches. If embeddings are unavailable it degrades to `topic_key` only.

## Hackathon
Product Space × Wispr Flow "Agentic AI Hackathon". Build by voice; the product's main input is speech via Wispr Flow.
Scoring: Wispr usage 20 · prototype quality/UX 20 · AI integration 20 · problem understanding 15 · LinkedIn 15 · innovation 10.
The judges are PMs, so the demo must be obvious and impressive in 2 minutes.
Required: transcript ingestion with speakers; extraction of decisions, tasks, owners, and deadlines; conflict detection
against stored memory; tracker integration; reminders; a weekly digest per person; confirmation before anything is posted.
**Core differentiator: cross-meeting memory and conflict detection.**

## Product
1. **Voice debrief**: hold Wispr and ramble, and the text lands in a textbox → clean → extract → check against memory.
2. **Transcript ingestion**: "Name: line" text, .vtt, .srt, audio (Groq Whisper).
3. **LangGraph pipeline**: normalizer → extractor → memory_retriever → conflict_detector (LLM + deterministic
   checks) → ripple → `interrupt()` for human review → review_editor (spoken edits) → executor (Notion/GitHub,
   reminders, heads-up) → memory_writer (supersede old decisions, keep lineage).
   - Normalizer: removes fillers and digressions, applies self-corrections, resolves dates, and returns `Correction[]`.
   - Extractor: decisions with `topic_key`, tasks with owner, ISO due date, `raw_due_phrase`, `source_quote`.
     "Rahul said X" → `made_by = Rahul`, not the speaker.
   - Conflict: the LLM judges reversals and contradictions; Python checks deadline collisions and overload (3+ tasks per owner on one day).
4. **Ask your meetings**: answers with citations (meeting + exact quote).
5. **Live agent trace**: every node emits `AgentEvent`s over SSE.
6. **Reminders**: an APScheduler job sends Telegram messages for tasks due within 24h, driven by the **demo clock**
   (a settings row, not the real clock).
7. **Weekly digest per person** in a sharp chief-of-staff voice.
8. **Integrations**: Notion (primary), GitHub Issues (fallback), Telegram.
9. **v1.1 differentiators**:
   - **Ripple Effect**: when a decision flips, find the existing tasks built on the old one, propose a
     reschedule, rescope, or cancel for each, flag new work nobody owns, and draft a "what changed for you" heads-up per person.
   - **Walk-in Brief**: a 60-second pre-meeting brief with open conflicts, overdue items, hot topics, and an agenda.
   - **Decision Time Machine**: what the team believed on any date, plus lineage per topic.
   - **Flip-flop Radar**: churn score per topic, so decision instability shows up as a risk.

## Stack & conventions
- Python 3.11+, FastAPI on port **8000**, every route under **/api**.
- LangGraph with a SQLite checkpointer; `langchain-groq` with Pydantic structured outputs.
- SQLModel on SQLite; fastembed for local embeddings (vectors stored in SQLite, cosine similarity in numpy).
- APScheduler, sse-starlette, notion-client, httpx (Telegram, GitHub).
- Model names come from config: `GROQ_MODEL_STRONG` (extractor, conflict, editor, ask, digest, brief) and
  `GROQ_MODEL_FAST` (normalizer). Never hard-code them.
- **Dates**: ISO, resolved relative to the meeting date. Always keep the raw phrase.
- **Replay mode** (`DEMO_REPLAY=1`, or no Groq key): LLM calls whose input hash matches a recording in
  `backend/app/replay/recordings/` return the recorded output. Seed demo inputs always have recordings,
  and tests run on them, so the demo and CI never depend on Groq being up.

## Layout
```
backend/
  app/main.py            FastAPI app, mounts routers under /api
  app/config.py          settings (env), integration availability flags
  app/schemas.py         Pydantic mirror of CONTRACT.md
  app/db.py, models.py   SQLModel tables + session
  app/graph.py           LangGraph wiring (nodes in app/agents/)
  app/agents/            one module per agent node
  app/services/          clock, reminders, digest, ask, brief, radar, time_machine, ripple, ingest parsing
  app/integrations/      groq/llm, notion, github_issues, telegram
  app/replay/            recorder/player + recordings/
  app/api/               routers
  seed/                  meeting1.txt, debrief2.txt (+ expected outputs)
  tests/                 pytest; test_golden_debrief2.py is the demo guardrail
```

## Seed demo (project "Pocket")
- **meeting1** (24 Oct 2026; Priya PM, Rahul eng lead, Ananya design). Decisions: v1 iOS only (Android → v2);
  launch 20 Nov; Razorpay, not Stripe. Tasks: Ananya onboarding screens by 3 Nov; Rahul TestFlight build by 10 Nov;
  Priya landing page copy by 6 Nov.
- **debrief2** (Priya's voice debrief, Sat 31 Oct 2026). Android back in v1 (Rahul: investors); launch
  "December 1st, no wait, November 28th"; Ananya redoes onboarding for Android "by, uh, next Wednesday" (→ 4 Nov);
  Rahul does the Play Store listing by the 20th (→ 20 Nov); coffee machine digression; Stripe because Razorpay KYC is slow;
  Priya sends the investor update Monday (→ 2 Nov).
- **Expected**: 3 conflicts (Android reversal, launch date change, Stripe reversal); corrections for Dec 1 → 28 Nov,
  next Wednesday → 4 Nov, and Monday → 2 Nov; the coffee digression removed. Enforced by `tests/test_golden_debrief2.py`.

## Commands
```bash
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
pytest -q
```

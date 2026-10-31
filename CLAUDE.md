# CLAUDE.md: Quorum ("meetings that remember")

Context for every Claude Code session in this repo. Read this first, then `PLAN_BACKEND.md` for the current phase.

## Standing rules (non-negotiable)
1. **No prompt log in the repo.** Do not keep or commit a log of the user's prompts (the user removed `VOICE_LOG.md` on 31 Oct).
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
- **UI design (31 Oct, revised):** the newspaper concept was dropped by the user. The UI uses **Codex's visual system**
  (warm stone, ink, burgundy accent, Inter Tight, rounded cards, light + dark) with rich motion: words rising into focus,
  a live voice waveform, a pulsing agent pipeline, old-vs-new "collision" cards with a drawn strike, count-ups, an
  approval seal with ripples. The user delegated the design details to Claude ("do whatever looks extraordinary").
- **First view:** one giant question ("What happened in your meeting?"), a one-line explanation, the voice box, a
  "play the sample debrief" chip, and three how-it-works steps. Nothing else.
- **Reveal:** the story unfolds downward, stage by stage (agents → conflicts → approve seal → workspace);
  the top nav (Memory, Ask, Board, Digest, Radar…) fades in only after the first approval. Lots of smooth animation.
- External design references are never named in the product, repo or logs (never write them anywhere).
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
- **Approve path (Phase 6, user decisions 31 Oct):** "keep previous" drops the new decision AND the new tasks that depend
  on it (the extractor marks each task's `depends_on_topic`; stored internally as `decision_id`, not in the wire contract).
  A meeting enters memory only on approve. A task with an open owner/date question is still created (unassigned/undated).
  A tracker failure falls back Notion → GitHub → local (`tracker_url` null) and never blocks the approve. A new decision
  that only repeats an active one on the same topic (no reversal found) is skipped ("confirms existing").
- **Delegated to Claude (user: "do whatever you think is good", 31 Oct):** ripple, brief, digest, radar, time machine and
  ask are **deterministic** (no model call), so they work offline and need no recordings; ripple proposes a date shift
  (same number of days a moved date moved) or a rescope for the tasks the conflict agent marked as affected. Voice edit
  uses the strong model to return structured operations that Python applies. Reminders cover open tasks due within 24h of
  the demo clock (or late) and send once per task. Embeddings load from the local cache before any network call.
- Retrieval = same `topic_key` ∪ top embedding matches. If embeddings are unavailable it degrades to `topic_key` only.
- **Deployment (31 Oct, user chose Render):** one Docker service serves the built website and the API from the same
  origin (`Dockerfile`, `render.yaml`, `DEPLOY.md`). The backend serves `frontend/dist` when present and seeds meeting 1 on
  the first start of an empty database. Free plan: `EMBEDDINGS_ENABLED=0` (topic-only recall), data resets on restart,
  `DEMO_REPLAY=1` stays on, secrets are set in Render's dashboard and never committed.
- **Guided example (31 Oct, user: "very simple, anyone can understand the conflict"):** the home page's sample is
  `backend/seed/simple.txt`: "the launch is moving from the 20th to the 28th of November… Rahul, please let the beta
  testers know by Monday." One decision, one task, one conflict (launch date), one affected task (landing page copy).
  Its saved conflict answer was trimmed by hand to that single task (see `curated_note` in the recording). debrief2 stays as
  the full regression test. The normalizer now re-checks dates written inside the clean text.
- **Inner pages (31 Oct):** Memory, Ask, Board and Digest share the home page's layout: floating top bar with always-visible
  nav pills (sliding active pill), demo clock pill, reminders, reset, theme and "New debrief"; rising two-line headlines;
  cards that rise in one after another; Lenis smooth scrolling. The old sidebar shell is gone. Small old type was lifted by
  `frontend/src/app/inner-scale.css` (generated once from `index.css`).

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

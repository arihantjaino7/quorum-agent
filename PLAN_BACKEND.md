# PLAN_BACKEND.md: Quorum backend build plan

One phase per session. Each phase ends green (`pytest -q`), is committed, and stops for your "go".
To start one, dictate: **"Go phase N."** The riskiest work is scheduled first: the pipeline mechanics
(LangGraph interrupt + SSE) in Phase 2, Groq structured outputs in Phase 3, and the core memory and
conflict moment in Phase 5. That way, if time runs out, what's missing is polish, not the demo.

---

## What wins this (research summary)

- Meeting tools broadly do transcription, summaries, and action items. Cross-meeting memory is where the
  category is heading, but **almost nothing ships "this decision contradicts what you decided last week"**.
  The closest we found is a hackathon prototype (ContextGuard, lablab.ai, May 2026). Conflict detection is
  our floor, not our differentiator.
- Wispr itself is moving into meetings (Notetaker terms; a $280M raise aimed at "meetings and team
  collaboration"). Pitching a **voice-first execution layer** on top of Wispr fits where the sponsor is going.
- The judges are PMs. What a PM feels as pain isn't missing notes. It's **stale plans**: a decision flips and
  three people keep executing the old one. So our headline is *what changed and who needs to know*, not
  *we detected a conflict*.

### The four differentiators (all planned)
| Feature | The PM "aha" | Phase |
|---|---|---|
| **Ripple Effect** ⭐ | "Android is back in" → Quorum flags Ananya's iOS-only onboarding as stale, proposes a rescope, and drafts her a heads-up. Detect → **re-plan**. | 7 |
| **Walk-in Brief** | A 60-second "here's what you need before the next meeting", grounded in memory. | 13 |
| **Decision Time Machine** | Scrub to 25 Oct and see what the team believed then, plus a lineage per topic. | 12 |
| **Flip-flop Radar** | "Platform scope reversed a week after it was set": decision churn surfaced as a project risk. | 12 |

All four are in `CONTRACT.md` v1.1 now, so Codex can build their UI in parallel from day one.

---

## The 2-minute stage demo (what every phase serves)
| t | Beat | Proves |
|---|---|---|
| 0:00 | "Last week's planning meeting is already in Quorum's memory." Show 3 decisions + 3 tasks. | memory exists |
| 0:10 | **Hold the Wispr key** and ramble the debrief live (coffee machine included). | Wispr is the input |
| 0:35 | Live agent trace lights up node by node. The "what we cleaned" diff shows Dec 1 → 28 Nov, next Wed → 4 Nov, coffee removed. | multi-agent, normalization |
| 0:50 | **3 red conflict cards**: Android reversal, launch date, Stripe reversal, each quoting the old meeting. | core differentiator |
| 1:05 | **Ripple panel**: Ananya's iOS onboarding is now stale → rescope. Heads-up drafts per person. | re-plan, not summarize |
| 1:20 | Say: *"approve all but make Rahul's deadline the 18th."* Diff appears → Approve → Notion tasks appear, Telegram heads-up lands on a phone. | voice edit, confirmation, integration |
| 1:40 | Ask: *"why did we drop Razorpay?"* → answer with a citation to the exact quote. Drag the clock to 3 Nov → reminder fires → open Walk-in Brief / Radar. | memory Q&A, reminders, digest |
| 2:00 | End. |  |

---

## Phases

### ✅ Phase 0: Foundation (done)
Repo, `.gitignore`, `.env.example`, README stub, CLAUDE.md, CONTRACT.md v1.1, VOICE_LOG.md, the backend
scaffold (health route, empty agent/service/integration modules, Pydantic contract mirror), seed data,
golden expectations, and the self-enabling golden test.
**Test:** `pytest -q` → 13 pass, 6 golden checks skip until their agents exist.

### ✅ Phase 1: Data layer + demo controls (done)
- **Build:** SQLModel tables (Project, Meeting, Decision, Task, Conflict, Run, Setting, Embedding), `db.py`,
  demo clock in Settings (`services/clock.now()` used everywhere), `seed/meeting1.json` (meeting 1's
  structured output, hand-checked, loaded with **no LLM** so reset is instant and deterministic),
  `POST /api/demo/reset`, `GET/POST /api/clock`, and the read routes: projects, meetings, people,
  decisions, decisions/graph, tasks, PATCH task.
- **Proves:** memory exists and the demo can be reset in under 1 second.
- **Test:** reset → 3 active decisions, 3 todo tasks, 3 people; clock round-trips; PATCH task → done.
- **Unlocks Codex:** dashboards, people, task list, decision list on real data.

### ✅ Phase 2: Walking skeleton (risk: LangGraph interrupt + SSE) (done)
- **Build:** `graph.py` with all 8 nodes as pass-through stubs, SQLite checkpointer, `interrupt()` before
  execution, resume on approve/reject; `services/runs.py` (per-thread event buffer + fan-out, late-join replay);
  `POST /api/ingest`, `GET /stream`, `GET /review`, `POST /approve`, `POST /reject`, `POST /retry`; replay pacing.
- **Proves:** the hardest plumbing (pause a graph mid-run for a human, stream every node, resume) works
  before any LLM is involved.
- **Test:** ingest → stream shows `agent_start`/`agent_end` for each node → `review_ready`; approve resumes to
  executor and memory_writer; reject ends the run; a late SSE client gets the full replay. The golden test's
  run fixture goes live here.
- **Unlocks Codex:** the live agent trace and the review screen, with real events.

### ✅ Phase 3: LLM harness + replay (risk: Groq structured outputs) (done)
- **Build:** `integrations/llm.py`: `structured(tier, Schema, messages)` via langchain-groq
  `with_structured_output`, retries on validation errors, and a timeout. `app/replay`: the key is
  sha256(agent + tier + normalized prompt); `QUORUM_RECORD=1` saves recordings; replay serves them when
  `DEMO_REPLAY=1` or there's no key. `scripts/check_models.py` lists Groq models and confirms the configured strong and fast models exist.
- **Proves:** our chosen models return valid Pydantic objects, and a recorded run replays byte-identically.
- **Test:** replay hit/miss/record unit tests (offline); `@live` smoke test for one structured call.
- **⚠ Needs:** a `GROQ_API_KEY` on a machine that can reach `api.groq.com`. **This cloud container's network
  policy currently blocks that host**, so either add `api.groq.com` under Allowed domains in the environment's
  Network access settings, or record on your laptop and commit the recordings.

### ✅ Phase 4: Normalizer + extractor (done)
- **Build:** the normalizer (fast model) → `clean_text` + `Correction[]`; the extractor (strong model) →
  decisions with `topic_key` (prompted with existing keys from memory), tasks, and questions. A **deterministic
  date resolver** in Python ("next Wednesday", "Monday", "the 20th", "Nov 28th") checks and overrides the
  LLM's ISO dates, since LLM date arithmetic is the most likely silent failure. Record debrief2 replays.
- **Proves:** messy speech → clean structure, with correct attribution ("Rahul said" → Rahul).
- **Test:** golden corrections, digression, decisions, and tasks checks go green; date-resolver unit table (15+ phrases).

### ✅ Phase 5: Memory + conflicts 🎯 (the core) (done)
- **Build:** `services/embeddings.py` (fastembed `bge-small`, float32 blobs, numpy cosine), the memory
  retriever (same topic_key ∪ top-k similar), and the conflict detector: the LLM judges reversal or
  contradiction with an explanation and resolution; Python checks deadline collisions and overload
  (3+ tasks per owner per day). The model downloads once and is cached; the cache path is in config.
- **Proves:** cross-meeting memory catches all three reversals and no false positives.
- **Test:** golden "exactly 3 semantic conflicts against meeting 1" goes green; overload/collision unit tests;
  a negative test (a debrief that agrees with meeting 1 → 0 conflicts).

### Phase 5½: Cockpit UI (frontend redesign) 🎨
Decided 31 Oct: Claude owns `/frontend`; one-screen cockpit layout; built after Phases 4–5 so it uses real data.
**Style (31 Oct, revised):** Codex's visual system plus rich motion (see CLAUDE.md); the newspaper version was removed.
- **Step 1 ✅ (31 Oct):** `/` is the focused home (`frontend/src/home/`): one question + voice card (live waveform) →
  agent pipeline → stats, conflict "collision" cards, decisions/tasks, cleaned transcript → approve bar → seal → the
  workspace nav unlocks. Fixed bugs 1, 4, 6, 7. Approve counts are hidden until Phase 6 makes them non-zero.
- **Step 2 (next):** polish the workspace pages (memory/time machine/radar, ask, board, digest, brief) with the same
  motion language; fixes bugs 2, 3, 5.
Known bugs from the 31 Oct live check:
1. Mock toggle: `.env.development` (`VITE_USE_MOCKS=true`) beats `.env.local`, so turning mocks off requires `.env.development.local`. Fix the defaults and docs.
2. The "Already in memory" panel labels decisions by position, not `topic_key` (mismatched labels).
3. After approve, the page refetches `/review`, which returns 409 (console error). Stop refetching once the run is approved.
4. `agent_progress` (contract v1.3) isn't handled by the SSE client.
5. Voice-edit suggestions are hard-coded, wrong for this data (Monday = 2 Nov), and shown even with 0 items.
6. The floating approve bar covers transcript text.
7. Giant hero headers push the actual work below the fold on every page.

### Phase 6: Approve path: memory writer + executor
- **Build:** memory writer (persist approved decisions + embeddings; `superseded_by` lineage; `keep_old` drops
  the new decision); executor: Notion → GitHub Issues → local-only, each with one clear log line when skipped.
- **Proves:** confirmation → real tracker writes, and memory updates correctly for the next meeting.
- **Test:** approve → 3 supersede edges in `/decisions/graph`; `keep_old` keeps the old one active; with no
  keys, tasks are created with `tracker_url: null` and nothing crashes; Notion/GitHub are mocked with httpx mock.

### Phase 7: Ripple Effect ⭐
- **Build:** a `ripple` node: for each reversal, find open tasks linked to the old decision (by meeting + topic +
  embedding similarity) and have the LLM propose `reschedule | rescope | cancel` with a reason; flag
  `unowned_work` (implied by the new decision, no owner); write a per-person `HeadsUp`. On approve, apply the
  chosen ripple actions and send heads-ups (Telegram or log).
- **Proves:** Quorum re-plans, not just detects.
- **Test:** golden "Ananya onboarding → rescope" green; skipping a ripple leaves the task untouched; `keep_old`
  suppresses its ripples.

### Phase 8: Voice edit
- **Build:** the review editor turns a spoken instruction into a structured patch (set field, remove item,
  resolve conflict, add task), applied to the checkpointed state, plus human-readable `changes`.
- **Test:** "approve all but make Rahul's deadline the 18th" → Play Store due 2026-11-18, one change line;
  "drop the investor update" removes that task; nonsense instructions → no changes plus a clear message.

### Phase 9: Ask your meetings
- **Build:** retrieve decisions, quotes, and superseded lineage → strong model answers with citations
  constrained to the retrieved quotes (no citation without a source).
- **Test:** "why did we drop Razorpay?" → cites the 31 Oct debrief quote about KYC; an unknown topic → "No
  meeting covers that yet."

### Phase 10: Reminders + Telegram + demo clock
- **Build:** an APScheduler interval job plus `POST /api/reminders/run`: open tasks due within 24h of the
  **demo clock**, sent once (`reminder_sent`). Telegram via httpx; a log line when not configured.
- **Test:** clock → 2026-11-03T10:00 → Ananya's 4 Nov task is reminded; running again sends nothing new.

### Phase 11: Weekly digest
- **Build:** per person: done / due / overdue / decisions that touched them / open conflicts →
  `summary_md` in a chief-of-staff voice (short, opinionated, names the one thing that matters).
- **Test:** Rahul's digest for week of 2 Nov lists the Play Store and TestFlight tasks and flags the
  Android reversal; the replayed summary stays under 120 words.

### Phase 12: Decision Time Machine + Flip-flop Radar
- **Build:** pure Python over the lineage: `/decisions/as-of`, `/decisions/timeline`, `/radar`
  (versions, flips, churn, risk, note).
- **Test:** as of 2026-10-25 → iOS only / 20 Nov / Razorpay; as of 2026-11-01 → the new ones;
  `changed_since` = 3 topics; radar ranks platform_scope, launch_date, and payments_provider with flips = 1.
- **Optional seed:** a third debrief that flips one topic back, so the radar shows a real "flip-flop" (ask first).

### Phase 13: Walk-in Brief
- **Build:** radar + open conflicts + overdue/due-soon tasks → a strong-model brief (headline, 60-second
  script, agenda).
- **Test:** the brief at 2026-11-03 mentions onboarding due tomorrow and the platform-scope churn; the agenda has
  at most 5 items.

### Phase 14: Transcript files + audio
- **Build:** `ingest_parsing`: "Name: line" text, `.vtt` (voice tags), `.srt` (speaker prefixes), audio via
  Groq Whisper; `POST /api/ingest/file`.
- **Test:** fixtures for each format → identical speaker-attributed text; audio skips cleanly without a key.

### Phase 15: Demo hardening
- Note from Phase 4: the seed cleanup recording was made by the backup model (qwen hit its free-tier cap), so its
  clean text reads slightly stiffly ("Priya said quick debrief"). Re-record when qwen has quota, then eyeball the output.
- Record replays for every demo utterance, including the voice-edit and Ask lines you'll actually say;
  `scripts/rehearse.py` runs the whole 2-minute demo headless and prints timings. Failure drills: no wifi, no
  Notion, Groq 429. Latency budget: review_ready in under 8 seconds live, under 1 second on replay.

---

## Stretch features (after Phase 15, if time). Tracked in IDEAS.md
| Idea | Why a PM cares | Effort |
|---|---|---|
| **Absent-stakeholder alert**: a decision affects someone who wasn't in the meeting → auto heads-up | the "nobody told me" problem | S |
| **Commitment detector**: catches soft promises ("I'll look into it") as low-confidence tasks | hidden work | S |
| **Speak to resolve**: hold Wispr on a conflict card and say "keep Razorpay for India" | more voice in the loop | S (reuses Phase 8) |
| **Decision confidence**: hard vs. tentative decisions; tentative ones get no ripple | fewer false alarms | M |
| **Calendar export**: .ics of deadlines | adoption | S |

## Risk register
| Risk | Mitigation |
|---|---|
| Groq unreachable, slow, or rate-limited on stage | Replay mode (Phase 3); rehearsal script (Phase 15) |
| LLM date math wrong | Deterministic resolver overrides (Phase 4) |
| Extra or missing conflicts on the golden debrief | Golden test pins exactly 3; deterministic checks unit-tested separately |
| `topic_key` drift ("launch" vs "launch_date") | Extractor is prompted with existing keys; retriever also matches by embedding |
| fastembed model download on venue wifi | Pre-download during setup; cache dir in config |
| Contract drift with Codex | `test_schema_fields_match_contract` fails when schemas.py and CONTRACT.md diverge |
| Replay keys include memory matches, which depend on the embedding model | Model cached in `backend/.cache/fastembed` (downloaded once, ~70MB); without it, retrieval degrades to topic_key matching, prompts differ, and replay misses with a clear error |
| A LangGraph upgrade changes interrupt semantics | Versions pinned in requirements.txt; Phase 2 tests cover interrupt/resume |

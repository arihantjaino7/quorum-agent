# Quorum — meetings that remember

## Ownership and session rules (updated 31 Oct by the user's decision)
- **Claude Code now owns `/frontend`, `/backend` and the root files.** Codex's prototype was merged into
  `claude/nice-mayer-1wmx7b`. Codex works only on tasks the user hands over from Claude Code, each scoped to
  named files. Don't touch other files or refactor beyond the task.
- At the start of **every task**, append the user's exact prompt with a timestamp under a `[Codex]` heading in
  `/VOICE_LOG.md` (append-only; never rewrite it). Prompts are dictated through Wispr Flow; the log is hackathon evidence.
- `/CONTRACT.md` is the API source of truth. Read it before API work. Don't change it; report discrepancies to the user.
- Work on the branch named in the task, and commit only the files the task names.
- Read `/CLAUDE.md` for current decisions. Your current task list is in `/CODEX_TASKS.md`.

## Product and hackathon
Product Space × Wispr Flow Agentic AI Hackathon. Scoring: Wispr 20, prototype/UX 20, AI 20, problem 15, LinkedIn 15, innovation 10. All prompts are dictated; Wispr types natural speech into the focused field. Make agent behavior and cross-meeting memory obvious to product-manager judges in a two-minute demo.

Quorum converts messy meeting debriefs or transcripts into decisions and tasks. Backend agents normalize speech, extract owners/deadlines, recall past decisions, detect conflicts, wait for human confirmation (including voice), create Notion tasks, schedule Telegram reminders and produce per-person weekly digests. Cross-meeting memory and conflict detection are the core.

## Frontend stack and design
Vite, React, TypeScript, Tailwind, shadcn/ui, TanStack Query, React Router, React Flow, framer-motion, react-markdown. Proxy `/api` to `http://localhost:8000`. Typed mocks in `src/mocks`, enabled with `VITE_USE_MOCKS=true`, must allow independent development.

Calm, premium, serious: Linear meets Granola. Strong type, generous whitespace, one accent; red/amber only for conflicts. Light/dark themes, keyboard access, reduced-motion support, thoughtful empty/loading/error states. Subtle arrival motion; polished conflict reveal is the demo highlight.

## Original screen brief (historical; superseded by the cockpit redesign in PLAN_BACKEND.md Phase 5½)
1. Capture: huge calm textbox, “Hold your Wispr key and talk”; Voice debrief/Transcript toggle; .vtt/.srt/.txt/audio upload; project, title, date, speaker.
2. Live trace: Normalizer → Extractor → Memory → Conflict check → Awaiting you. SSE lights each node and supplies one-line agent messages.
3. Review (first priority): cleaned text left with inline correction chips and raw-original hover; editable decisions/tasks right (owner, ISO due date, raw due phrase). Conflicts at top: old/new side by side, severity, source-meeting link, affected tasks, Accept new/Keep old. Inline missing-owner/date questions. Voice-edit box “Tell Quorum what to change” with returned diff. Approve & Send / Reject.
4. Memory: per-project decision timeline; superseded decisions struck through; React Flow lineage.
5. Ask: voice-first questions; answers with meeting/date/quote citation cards.
6. Board: tasks by owner, status, due date, tracker badge and reminder state.
7. Digest: person/week selection; markdown summary; done/due/overdue lists.
8. Global header: project switcher, demo clock “Now: 31 Oct 2026 · Jump to…”, POST clock, Run reminders, hidden Reset demo.

## Demo story
Project Pocket; Priya, Rahul, Ananya. Prior meeting: iOS-only v1, 20 Nov 2026 launch, Razorpay. New debrief: Android returns, launch moves to 28 Nov, switch to Stripe. Three conflicts; human review resolves them before execution.

## Contract from the initial brief
Strings unless otherwise specified; IDs are strings; due dates are ISO or null.
- Correction: original, resolved, kind (`self_correction|filler|digression|date_resolution`).
- Decision: id, topic_key, statement, made_by, meeting_id, date, status (`pending|active|superseded`), superseded_by (ID|null).
- Task: id, title, owner, due_date, raw_due_phrase, status (`pending|todo|done`), source_quote, meeting_id, tracker_url (string|null), reminder_sent (boolean).
- Conflict: id, type (`reversal|contradiction|deadline_collision|overload`), severity (`high|medium|low`), new_item_id, old_decision (Decision|null), affected_tasks (Task[]), explanation, suggested_resolution.
- Question: id, item_id, field (`owner|due_date`), prompt.
- ReviewPayload: thread_id, meeting {id,project,title,date,speaker,source_type (`voice|transcript|audio`)}, raw_text, clean_text, corrections[], decisions[], tasks[], conflicts[], questions[].
- AgentEvent: type (`agent_start|agent_end|review_ready|error`), agent, message, optional payload.

Endpoints (all prefixed `/api`):
- POST `/ingest` {project,title,date,speaker,source_type,text} → {thread_id}; POST `/ingest/file` multipart file + same metadata.
- GET `/runs/{thread_id}/stream` SSE AgentEvent; final review_ready includes ReviewPayload. GET `/runs/{thread_id}/review` → ReviewPayload.
- POST `/runs/{thread_id}/voice-edit` {instruction} → {review,changes:string[]}.
- POST `/runs/{thread_id}/approve` {resolutions:{[conflict_id]:`accept_new|keep_old`}} → {created_tasks:Task[],superseded_ids:string[]}.
- POST `/runs/{thread_id}/reject` → {ok}.
- GET `/projects`, `/meetings?project=`, `/people`.
- GET `/decisions?project=&include_superseded=true`.
- GET `/decisions/graph?project=` → {nodes:[{id,label,status,date,meeting_title}],edges:[{source,target,kind:`supersedes`}]}.
- GET `/tasks?project=&owner=`; PATCH `/tasks/{id}` {status}.
- POST `/ask` {project,question} → {answer,citations:[{meeting_id,meeting_title,date,quote}]}.
- GET `/digest/{person}?week_of=` → {person,week_of,summary_md,done:Task[],due:Task[],overdue:Task[],decisions:Decision[],conflicts:Conflict[]}.
- GET/POST `/clock` {now}; POST `/reminders/run` → {sent:[{task_id,owner,channel}]}.
- POST `/demo/reset`.

The brief does not specify project/people list item shapes, task-patch/reset return bodies, rejected-run behavior, or structured review editing beyond voice-edit. Track assumptions in the frontend; defer to CONTRACT.md when available.

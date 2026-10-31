# Voice Log

Every prompt in this project is dictated through **Wispr Flow**. Each coding agent appends the
user's exact prompt, with a timestamp, under its own heading at the start of each task. Prompts
are copied verbatim: no cleanup, typos and Wispr artifacts included. This file is our evidence for
the "Wispr usage" criterion.

Format:

```
## [Claude Code] YYYY-MM-DD HH:MM UTC — short label
> exact prompt
```

---

## [Claude Code] 2026-10-31 07:56 UTC — Session 1 brief (interrupted before work began)

> You're the backend and architecture lead on a hackathon project. Another coding agent (OpenAI Codex) works in this same folder at the same time and owns /frontend. You own /backend and the root files. Never edit anything inside /frontend.
>
> ## Context
> Hackathon: Product Space × Wispr Flow "Agentic AI Hackathon". The rule is that you build by voice: I dictate every prompt through Wispr Flow, and the product's main input is natural speech captured through Wispr. Scoring: Wispr usage 20, prototype quality and UX 20, AI integration 20, problem understanding 15, LinkedIn 15, innovation 10. The judges are product managers, so the demo has to be obvious and impressive in 2 minutes.
>
> Problem statement (meeting-to-execution agent). We must build:
> - transcript ingestion with speaker attribution
> - extraction of decisions, action items, owners, deadlines
> - detection of conflicts with earlier decisions stored in memory
> - creation of tasks in a tracker through an integration
> - reminders before deadlines
> - a weekly digest per person
> - a confirmation step before anything gets posted
> The brief says cross-meeting memory and conflict detection are what separate a real system from a transcript summarizer. That's our core.
>
> ## Product: Quorum — "meetings that remember"
> 1. Voice debrief: after a meeting I hold the Wispr key and ramble ("Rahul said Android's back in, launch moves to Dec 1st, no wait, 28th, side note the coffee machine broke..."). The text lands in a textbox. Quorum cleans it, extracts structure, and checks it against everything the team decided before.
> 2. Transcript ingestion: pasted text in "Name: line" format, .vtt and .srt files, and optionally audio via Groq Whisper.
> 3. Multi-agent LangGraph pipeline: normalizer (fillers, digressions, self-corrections, returns a list of corrections) → extractor (decisions with topic_key, tasks with owner, ISO due date, raw date phrase, source quote; "Rahul said X" means Rahul made the decision, not the speaker) → memory retriever (semantic search over past decisions using local embeddings, e.g. fastembed, stored in SQLite) → conflict agent (LLM judges semantic reversals and contradictions) + deterministic Python checks (deadline collisions, owner overload: 3+ tasks due the same day) → human confirmation via LangGraph interrupt() → review-editor agent (applies spoken edits like "approve all but make Rahul's deadline the 18th") → executor (Notion tasks, reminder scheduling) → memory writer (marks old decisions superseded and keeps lineage).
> 4. Ask your meetings: a spoken question like "why did we drop Razorpay?" gets an answer with citations to the exact meeting and quote.
> 5. Live agent trace: every node emits events over SSE so the UI can show the agents working in real time.
> 6. Reminders: an APScheduler job sends Telegram messages for tasks due within 24h, driven by a DEMO CLOCK stored in settings (not the real clock) so I can time-travel during the demo.
> 7. Weekly digest per person, written like a sharp chief of staff, not a report.
> 8. Integrations: Notion database (primary), GitHub Issues (fallback), Telegram bot. Everything must degrade gracefully if a key is missing, with a clear log and no crash.
>
> ## Stack
> Python, FastAPI, LangGraph (with a checkpointer), langchain-groq with Pydantic structured outputs, SQLite (SQLModel), APScheduler, sse-starlette, fastembed, notion-client, httpx for Telegram. Use the strongest Groq model available for the extractor and conflict agent and a fast small one for the normalizer; put model names in config. All dates are ISO and resolved relative to the meeting date, and we always keep the raw phrase. Backend runs on port 8000 and every route is under /api.
>
> ## API contract (shared with Codex — this is the source of truth; if you must change it, update CONTRACT.md and tell me)
> Types:
> - Correction {original, resolved, kind: "self_correction"|"filler"|"digression"|"date_resolution"}
> - Decision {id, topic_key, statement, made_by, meeting_id, date, status: "pending"|"active"|"superseded", superseded_by: id|null}
> - Task {id, title, owner, due_date: ISO|null, raw_due_phrase, status: "pending"|"todo"|"done", source_quote, meeting_id, tracker_url: string|null, reminder_sent: bool}
> - Conflict {id, type: "reversal"|"contradiction"|"deadline_collision"|"overload", severity: "high"|"medium"|"low", new_item_id, old_decision: Decision|null, affected_tasks: Task[], explanation, suggested_resolution}
> - Question {id, item_id, field: "owner"|"due_date", prompt}
> - ReviewPayload {thread_id, meeting {id, project, title, date, speaker, source_type: "voice"|"transcript"|"audio"}, raw_text, clean_text, corrections: Correction[], decisions: Decision[], tasks: Task[], conflicts: Conflict[], questions: Question[]}
> - AgentEvent {type: "agent_start"|"agent_end"|"review_ready"|"error", agent, message, payload?}
> Endpoints:
> - POST /api/ingest {project, title, date, speaker, source_type, text} → {thread_id}
> - POST /api/ingest/file (multipart: file + same fields) → {thread_id}
> - GET  /api/runs/{thread_id}/stream → SSE of AgentEvent; the final review_ready carries ReviewPayload
> - GET  /api/runs/{thread_id}/review → ReviewPayload
> - POST /api/runs/{thread_id}/voice-edit {instruction} → {review: ReviewPayload, changes: string[]}
> - POST /api/runs/{thread_id}/approve {resolutions: {[conflict_id]: "accept_new"|"keep_old"}} → {created_tasks: Task[], superseded_ids: string[]}
> - POST /api/runs/{thread_id}/reject → {ok}
> - GET  /api/projects · GET /api/meetings?project= · GET /api/people
> - GET  /api/decisions?project=&include_superseded=true
> - GET  /api/decisions/graph?project= → {nodes: [{id, label, status, date, meeting_title}], edges: [{source, target, kind: "supersedes"}]}
> - GET  /api/tasks?project=&owner= · PATCH /api/tasks/{id} {status}
> - POST /api/ask {project, question} → {answer, citations: [{meeting_id, meeting_title, date, quote}]}
> - GET  /api/digest/{person}?week_of= → {person, week_of, summary_md, done: Task[], due: Task[], overdue: Task[], decisions: Decision[], conflicts: Conflict[]}
> - GET/POST /api/clock {now} · POST /api/reminders/run → {sent: [{task_id, owner, channel}]}
> - POST /api/demo/reset → wipes the DB and reseeds meeting 1
>
> ## Seed data (create backend/seed/)
> meeting1.txt — project "Pocket", 24 Oct 2026, a transcript with speakers Priya (PM), Rahul (eng lead), Ananya (design). Decisions: v1 is iOS only (Android moves to v2), public launch 20 Nov, payments via Razorpay not Stripe. Tasks: Ananya onboarding screens by 3 Nov, Rahul TestFlight build by 10 Nov, Priya landing page copy by 6 Nov.
> debrief2.txt — Priya's messy spoken debrief on 31 Oct 2026: Rahul said investors want Android at launch so Android is back in v1; launch moves to "December 1st, no wait, November 28th"; Ananya redoes onboarding for Android "by, uh, next Wednesday"; Rahul takes the Play Store listing by the 20th; a digression about the broken coffee machine; switching to Stripe because Razorpay KYC is slow; Priya sends the investor update Monday.
> Expected on debrief2: 3 conflicts (Android reversal, launch date change, Stripe reversal), corrections for the Dec 1 → 28 Nov self-correction, "next Wednesday" → 4 Nov and "Monday" → 2 Nov, and the coffee digression removed. Turn this into a pytest so we always know the demo still works.
>
> ## First session — do only this, then stop
> 1. git init, plus .gitignore, .env.example (GROQ_API_KEY, NOTION_TOKEN, NOTION_DATABASE_ID, GITHUB_TOKEN, GITHUB_REPO, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID), and README.md as a stub.
> 2. CLAUDE.md with everything above, condensed, so future sessions keep the context.
> 3. CONTRACT.md with the exact API contract above (Codex reads this file).
> 4. VOICE_LOG.md. Standing rule for this whole project: at the start of every task, append my exact prompt with a timestamp under a "[Claude Code]" heading. Every prompt is dictated through Wispr Flow, and this log is our evidence for the judges.
> 5. Scaffold /backend: folder structure, requirements, a health route, and empty agent modules. No feature logic yet.
> 6. Then propose a phased build plan in PLAN_BACKEND.md (phases, what each phase proves, how we test it, the riskiest parts first). Wait for my approval before writing any feature code.
> Commit only files you own, with clear messages.

## [Claude Code] 2026-10-31 07:58 UTC — Override: find and build the winning feature

> What I want to do is read this complete plan and implement the best feature which I can imagine. If you want to search, you can search wherever you want across the complete globe and just find out the best feature which can make me win this acathlon. Yes, all the best.

## [Claude Code] 2026-10-31 08:06 UTC — Answers to clarifying questions (dictated)

> **Feature:** First of all, if possible, try to add all of them and just add as many good, decent, valuable features as possible. If all of these are not possible, then just do whatever you want.
>
> **Scope:** Within foundation, core, and feature, make sure to divide the work into smaller phases first so that I can do one phase at a time. Other than that, whatever you feel is the best thing you can do, just do that.
>
> **Contract:** Hey, you can add adaptive or additive only, or otherwise add new options / them in the changes section at the top of contractor.md for Codex. Everything you are saying, just do that. Whichever will be the right
>
> **Fallback:** Replay mode for saved data with demo replay. The seed deep uses recorded model output, so the terminal demo always works. The input seed goes to Groq. Post also uses these recordings, ok

## [Claude Code] 2026-10-31 08:27 UTC — Go phase 1 + consult-before-deciding rule

> All right, now let's start with phase one. First of all, I want to clarify one thing: if, at any point in the process, you have to make any decision, first clarify it with me. Ask me. Till now, any decision you have made with me, just follow that. For the new decision which you are about to make, first consult me, then only proceed forward. In between, if you have any idea to make this better, just tell me. We will implement that also.

## [Claude Code] 2026-10-31 08:32 UTC — Phase 1 decisions (dictated answers)

> **Clock:** Frozen (Recommended)
>
> **IDs:** Use prefix short IDs, which you are recommended to use as they're easy to read in logs and the UI, and the typo in a prefix is caught only
>
> **Telegram:** Go with one team group chat, which you are recommending
>
> **Extras:** Just keep them separately in a file. All the fixes which you are planning, we will go through every fix you can do. I will go through them last. First of all, make the basic demo version so I can see what is going on.

# Quorum API Contract

**This file is the source of truth for every frontend ↔ backend interaction.**
Owner: Claude Code (backend). Reader: Codex (frontend). If the backend has to change something, it
updates this file first and records the change in the Changes block below.

- Base URL: `http://localhost:8000`. Every route is under `/api`.
- JSON everywhere except `POST /api/ingest/file` (multipart) and the SSE stream.
- All dates are ISO-8601: `YYYY-MM-DD` for dates, `YYYY-MM-DDTHH:MM:SS` for timestamps (demo-clock time, no timezone).
- IDs are opaque strings. Don't parse them.
- Errors: HTTP 4xx/5xx with body `{"detail": string}`.
- Fields marked `?` may be missing. `T|null` is always present but may be null.

---

## Changes

- **v1.4 (31 Oct, additive):** `GET /api/runs/{id}/stream?until=review` ends the stream at `review_ready` or `error`
  (default unchanged: stays open). `POST /api/ingest/file` is implemented: `.txt/.md/.vtt/.srt` are parsed into
  speaker-attributed text (`source_type` becomes `transcript`), audio goes through Groq Whisper (422 if Groq is
  unavailable, 502 if transcription fails). `voice-edit`, `brief`, `radar`, `digest`, `ask`, `reminders/run`,
  `decisions/as-of` and `decisions/timeline` are live. `ReviewPayload` and the wire types are unchanged.

Every change so far is **additive**: nothing below the base contract was renamed or removed, and
a frontend built only against v1.0 keeps working.

### v1.3 (2026-10-31): progress events (Phase 3)
| Where | Change |
|---|---|
| `AgentEvent.type` | + `"agent_progress"`: an agent is still working but has news, e.g. "Waiting for Groq rate limit (11s)…". It arrives between that agent's `agent_start` and `agent_end`. Show it as a status line under the running agent; it is never terminal. Clients that ignore unknown types still work. |

### v1.2 (2026-10-31): run lifecycle (Phase 2)
| Where | Change |
|---|---|
| SSE stream | **Stays open after `review_ready`.** After approve, the stream shows `executor` and `memory_writer` events, then a final `agent_end` from agent `pipeline` with `payload.status = "approved"` (plus the approve result). Reject ends with `agent_end` `pipeline` with `{status: "rejected"}`. A client that stops reading at `review_ready` still works. |
| SSE stream | The first event is `agent_start` from agent `pipeline` ("Run started for …"). |
| `AgentEvent` (error) | `payload: { failed_agent: AgentName \| null, retryable: boolean }` |
| New | `POST /api/runs/{thread_id}/retry` resumes a failed run from the agent that failed |
| `approve` / `reject` | The first one wins; any later approve/reject gets **409**. Pending reviews never expire. |
| `approve` | **502** if execution fails after approval (the run becomes retryable) |
| Pacing | In replay mode each agent shows as working for at least ~700ms, so the trace is watchable |

### v1.1 (2026-10-31): Ripple Effect, Walk-in Brief, Decision Time Machine, Flip-flop Radar
| Where | Change |
|---|---|
| `Decision` | + `rationale: string\|null`, + `source_quote: string\|null` (used by Ask, Time Machine, and conflict cards) |
| `AgentEvent` | + `ts: string` (ISO timestamp), + `run_ms?: number` on `agent_end`. The full list of `agent` names is in the AgentEvent section |
| `ReviewPayload` | + `ripples: Ripple[]`, + `heads_up: HeadsUp[]` (new types) |
| `POST /approve` | request + optional `ripple_actions`; response + `updated_tasks`, `cancelled_task_ids`, `heads_up_sent` |
| New | `GET /api/health` |
| New | `GET /api/brief?project=` (Walk-in Brief) |
| New | `GET /api/decisions/as-of?project=&date=` (Time Machine snapshot) |
| New | `GET /api/decisions/timeline?project=&topic_key=` (Time Machine lineage) |
| New | `GET /api/radar?project=` (Flip-flop Radar) |

### v1.0 (2026-10-31): initial contract

---

## Types

```ts
type ISODate = string;      // "2026-11-28"
type ISODateTime = string;  // "2026-10-31T09:30:00"

type Correction = {
  original: string;         // what was said
  resolved: string;         // what it became ("" when removed)
  kind: "self_correction" | "filler" | "digression" | "date_resolution";
};

type Decision = {
  id: string;
  topic_key: string;        // stable slug, e.g. "platform_scope", "launch_date", "payments_provider"
  statement: string;        // "v1 ships on iOS and Android"
  made_by: string;          // who decided ("Rahul said X" → made_by = "Rahul")
  meeting_id: string;
  date: ISODate;            // meeting date
  status: "pending" | "active" | "superseded";
  superseded_by: string | null;   // id of the decision that replaced this one
  rationale: string | null;       // v1.1: "investors want Android at launch"
  source_quote: string | null;    // v1.1: exact span from the clean text
};

type Task = {
  id: string;
  title: string;
  owner: string;
  due_date: ISODate | null;
  raw_due_phrase: string;   // always kept, e.g. "by, uh, next Wednesday"
  status: "pending" | "todo" | "done";   // pending = awaiting approval
  source_quote: string;
  meeting_id: string;
  tracker_url: string | null;   // Notion page or GitHub issue once created
  reminder_sent: boolean;
};

type Conflict = {
  id: string;
  type: "reversal" | "contradiction" | "deadline_collision" | "overload";
  severity: "high" | "medium" | "low";
  new_item_id: string;      // id of the new Decision or Task that triggered it
  old_decision: Decision | null;   // null for deterministic task-only checks
  affected_tasks: Task[];
  explanation: string;
  suggested_resolution: string;
};

type Question = {           // something the pipeline couldn't resolve on its own
  id: string;
  item_id: string;          // task id
  field: "owner" | "due_date";
  prompt: string;           // "Who owns the investor deck?"
};

type Meeting = {
  id: string;
  project: string;
  title: string;
  date: ISODate;
  speaker: string;          // who dictated / uploaded
  source_type: "voice" | "transcript" | "audio";
};

type ReviewPayload = {
  thread_id: string;
  meeting: Meeting;
  raw_text: string;
  clean_text: string;
  corrections: Correction[];
  decisions: Decision[];    // the new ones, status "pending"
  tasks: Task[];            // the new ones, status "pending"
  conflicts: Conflict[];
  questions: Question[];
  ripples: Ripple[];        // v1.1
  heads_up: HeadsUp[];      // v1.1
};

type AgentEvent = {
  type: "agent_start" | "agent_progress" | "agent_end" | "review_ready" | "error";   // agent_progress: v1.3
  agent: AgentName;
  message: string;          // human sentence for the trace UI: "Found 3 conflicts with past decisions"
  payload?: any;            // review_ready → ReviewPayload; error → { failed_agent, retryable };
                            // agent_end from "pipeline" → { status: "approved" | "rejected", ...approve result }
  ts: ISODateTime;          // v1.1
  run_ms?: number;          // v1.1, on agent_end only
};

type AgentName =
  | "normalizer" | "extractor" | "memory_retriever" | "conflict_detector"
  | "ripple" | "review_editor" | "executor" | "memory_writer" | "pipeline";
```

### v1.1 types

```ts
// Ripple Effect: what a changed decision does to work that already exists.
type Ripple = {
  id: string;
  conflict_id: string | null;      // the conflict that caused it (null for unowned_work)
  decision_id: string;             // the NEW decision that causes the ripple
  kind: "reschedule" | "rescope" | "cancel" | "unowned_work";
  task: Task | null;               // existing task that is affected (null for unowned_work)
  reason: string;                  // "Onboarding screens were designed for iOS only; Android is back in v1"
  proposal: {                      // what Quorum would change if applied
    title?: string;
    owner?: string;
    due_date?: ISODate | null;
    raw_due_phrase?: string;
  };
  default_action: "apply" | "skip";
};

// One short, personal note per affected person: "what changed for you".
type HeadsUp = {
  person: string;
  message_md: string;              // 2–4 lines, chief-of-staff tone
  ripple_ids: string[];
  task_ids: string[];
};

type RadarTopic = {
  topic_key: string;
  label: string;                   // "Platform scope"
  versions: number;                // how many distinct decisions on this topic
  flips: number;                   // how many times it reversed (A→B→A counts 2)
  last_changed: ISODate;
  churn: number;                   // 0..1
  risk: "high" | "medium" | "low";
  statements: { decision_id: string; date: ISODate; statement: string; made_by: string }[];
  note: string;                    // "Android scope reversed a week after it was set. Lock it before Play Store work starts"
};
```

---

## Endpoints

### Health
`GET /api/health` → (v1.1)
```json
{ "ok": true, "version": "0.1.0", "replay": true, "clock": "2026-10-31T09:00:00",
  "integrations": { "groq": false, "notion": false, "github": false, "telegram": false } }
```
`integrations.*` is true when that key is configured. The UI can show "Notion not connected" chips.

### Ingest
`POST /api/ingest`
```json
{ "project": "Pocket", "title": "Investor sync debrief", "date": "2026-10-31",
  "speaker": "Priya", "source_type": "voice", "text": "so um Rahul said..." }
```
→ `{ "thread_id": "..." }`. The pipeline starts immediately in the background. Open the stream next.

`POST /api/ingest/file` multipart: `file` (.txt, .vtt, .srt, or audio: .mp3/.m4a/.wav/.webm) plus
the same fields as form fields (`text` omitted) → `{ "thread_id": "..." }`

### Runs
`GET /api/runs/{thread_id}/stream` → `text/event-stream`.
Each SSE message has `event: <AgentEvent.type>` and `data: <AgentEvent JSON>`.
If the client connects late, it gets the events emitted so far replayed first.

Lifecycle of one run (v1.2):
```
agent_start pipeline                    "Run started for Investor sync debrief"
agent_start/agent_end × 5               normalizer, extractor, memory_retriever, conflict_detector, ripple
  (agent_progress may appear between an agent's start and end, e.g. "Waiting for Groq rate limit (11s)…")
review_ready pipeline   payload: ReviewPayload        ← run pauses here for the human
   …the stream stays open…
   approve → agent_start/agent_end × 2  executor, memory_writer
             agent_end pipeline  payload: {status:"approved", created_tasks, …}   ← stream closes
   reject  → agent_end pipeline  payload: {status:"rejected"}                     ← stream closes
any agent fails → error <agent>  payload: {failed_agent, retryable:true}           ← stream closes
```
Terminal events (the server closes the stream after them): `error`, and `agent_end` from agent `pipeline`.
After `POST /retry`, open the stream again: the stale `error` is dropped from the replay and the
run continues from the failed agent. Earlier agents don't rerun.

`GET /api/runs/{thread_id}/review` → `ReviewPayload` (409 if the run is not paused for review yet)

`POST /api/runs/{thread_id}/voice-edit`
```json
{ "instruction": "approve all but make Rahul's deadline the 18th and drop the investor update" }
```
→ `{ "review": ReviewPayload, "changes": ["Rahul · Play Store listing: due 20 Nov → 18 Nov", "Removed task: Investor update"] }`

`POST /api/runs/{thread_id}/approve`
```json
{ "resolutions": { "<conflict_id>": "accept_new" },
  "ripple_actions": { "<ripple_id>": "apply" } }
```
- `resolutions`: one entry per conflict. A missing entry means `accept_new`.
- `ripple_actions` (v1.1, optional): a missing entry means that ripple's `default_action`. Ripples
  whose conflict was resolved `keep_old` are skipped automatically.

→
```json
{ "created_tasks": [Task], "superseded_ids": ["dec_..."],
  "updated_tasks": [Task], "cancelled_task_ids": ["tsk_..."],
  "heads_up_sent": [{ "person": "Ananya", "channel": "telegram" }] }
```
(`updated_tasks`, `cancelled_task_ids`, `heads_up_sent` are v1.1. `channel` is
`"telegram"` or `"log"` when Telegram isn't configured.)

Errors: **409** if the run isn't awaiting review (still processing, or already approved/rejected:
the first approve/reject wins). **502** if execution fails after approval; the stream shows the
failing agent and `POST /retry` finishes the run.

`POST /api/runs/{thread_id}/reject` → `{ "ok": true }` (409 like approve)

`POST /api/runs/{thread_id}/retry` (v1.2) → `{ "ok": true }`. Resumes a failed run in the background
from the agent that failed. 409 unless the run is in the failed state. Then reopen the stream.

All `/api/runs/{thread_id}/…` routes return 404 for an unknown run (including after `/api/demo/reset`).

### Directory
- `GET /api/projects` → `[{ "name": "Pocket", "meeting_count": 2, "last_meeting": "2026-10-31" }]`
- `GET /api/meetings?project=` → `Meeting[]` (newest first)
- `GET /api/people` → `[{ "name": "Rahul", "open_tasks": 2, "overdue": 0 }]`

### Decisions
- `GET /api/decisions?project=&include_superseded=true` → `Decision[]`
- `GET /api/decisions/graph?project=` →
  `{ "nodes": [{ "id", "label", "status", "date", "meeting_title" }], "edges": [{ "source", "target", "kind": "supersedes" }] }`
  `source` is the NEW decision, `target` is the one it superseded.
- `GET /api/decisions/as-of?project=&date=` (v1.1, Time Machine) →
  ```json
  { "project": "Pocket", "date": "2026-10-25",
    "decisions": [Decision],
    "changed_since": [{ "topic_key": "launch_date", "then": Decision, "now": Decision }] }
  ```
  `decisions` shows what the team believed on that date, with each `status` computed as of that date.
  `changed_since` lists topics whose current answer differs from the answer on that date.
- `GET /api/decisions/timeline?project=&topic_key=` (v1.1; omit `topic_key` for all topics) →
  ```json
  { "topics": [{ "topic_key": "platform_scope", "label": "Platform scope",
      "events": [{ "decision": Decision, "meeting_id": "...", "meeting_title": "...", "date": "2026-10-24",
                   "made_by": "Priya", "quote": "...", "change": "created" }] }] }
  ```
  `change` is `"created" | "reversed" | "amended"`.

### Tasks
- `GET /api/tasks?project=&owner=` → `Task[]` (excludes `pending`)
- `PATCH /api/tasks/{id}` `{ "status": "todo" | "done" }` → `Task`

### Ask your meetings
`POST /api/ask` `{ "project": "Pocket", "question": "why did we drop Razorpay?" }` →
```json
{ "answer": "Because Razorpay KYC was too slow for the 28 Nov launch...",
  "citations": [{ "meeting_id": "...", "meeting_title": "...", "date": "2026-10-31", "quote": "..." }] }
```

### Digest
`GET /api/digest/{person}?week_of=2026-10-26` (default: the week of the demo clock) →
`{ person, week_of, summary_md, done: Task[], due: Task[], overdue: Task[], decisions: Decision[], conflicts: Conflict[] }`

### Walk-in Brief (v1.1)
`GET /api/brief?project=Pocket` → a 60-second brief to read before the next meeting.
```json
{ "project": "Pocket", "as_of": "2026-11-03T09:00:00",
  "headline": "Launch is 28 Nov; Android re-entered scope 4 days ago and onboarding is due tomorrow.",
  "script_md": "...",
  "agenda": ["Lock platform scope (reversed on 31 Oct)", "..."],
  "open_conflicts": [Conflict], "overdue": [Task], "due_soon": [Task], "hot_topics": [RadarTopic] }
```

### Flip-flop Radar (v1.1)
`GET /api/radar?project=Pocket` → `{ "project": "Pocket", "topics": [RadarTopic] }` (highest churn first)

### Clock & reminders
- `GET /api/clock` → `{ "now": "2026-10-31T09:00:00" }`
- `POST /api/clock` `{ "now": "2026-11-09T10:00:00" }` → `{ "now": ... }` (demo time-travel)
- `POST /api/reminders/run` → `{ "sent": [{ "task_id", "owner", "channel" }] }`.
  Sends a reminder for every open task due within 24h of the demo clock that hasn't had one yet.

### Demo
`POST /api/demo/reset` → `{ "ok": true }`. Wipes the DB, reseeds meeting 1 (already approved), and resets the clock to `2026-10-31T09:00:00`.

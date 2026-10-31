"""Pydantic mirror of CONTRACT.md (v1.1). Keep this file and CONTRACT.md in lockstep.

These are the wire types. Database tables live in models.py, and LLM structured-output
schemas live next to each agent.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SourceType = Literal["voice", "transcript", "audio"]
AgentName = Literal[
    "normalizer",
    "extractor",
    "memory_retriever",
    "conflict_detector",
    "ripple",
    "review_editor",
    "executor",
    "memory_writer",
    "pipeline",
]


class Correction(BaseModel):
    original: str
    resolved: str
    kind: Literal["self_correction", "filler", "digression", "date_resolution"]


class Decision(BaseModel):
    id: str
    topic_key: str
    statement: str
    made_by: str
    meeting_id: str
    date: str
    status: Literal["pending", "active", "superseded"]
    superseded_by: str | None = None
    rationale: str | None = None
    source_quote: str | None = None


class Task(BaseModel):
    id: str
    title: str
    owner: str
    due_date: str | None = None
    raw_due_phrase: str = ""
    status: Literal["pending", "todo", "done"]
    source_quote: str = ""
    meeting_id: str
    tracker_url: str | None = None
    reminder_sent: bool = False


class Conflict(BaseModel):
    id: str
    type: Literal["reversal", "contradiction", "deadline_collision", "overload"]
    severity: Literal["high", "medium", "low"]
    new_item_id: str
    old_decision: Decision | None = None
    affected_tasks: list[Task] = Field(default_factory=list)
    explanation: str
    suggested_resolution: str


class Question(BaseModel):
    id: str
    item_id: str
    field: Literal["owner", "due_date"]
    prompt: str


class Meeting(BaseModel):
    id: str
    project: str
    title: str
    date: str
    speaker: str
    source_type: SourceType


class RippleProposal(BaseModel):
    title: str | None = None
    owner: str | None = None
    due_date: str | None = None
    raw_due_phrase: str | None = None


class Ripple(BaseModel):
    id: str
    conflict_id: str | None = None
    decision_id: str
    kind: Literal["reschedule", "rescope", "cancel", "unowned_work"]
    task: Task | None = None
    reason: str
    proposal: RippleProposal = Field(default_factory=RippleProposal)
    default_action: Literal["apply", "skip"] = "apply"


class HeadsUp(BaseModel):
    person: str
    message_md: str
    ripple_ids: list[str] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)


class ReviewPayload(BaseModel):
    thread_id: str
    meeting: Meeting
    raw_text: str
    clean_text: str
    corrections: list[Correction] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    questions: list[Question] = Field(default_factory=list)
    ripples: list[Ripple] = Field(default_factory=list)
    heads_up: list[HeadsUp] = Field(default_factory=list)


class AgentEvent(BaseModel):
    type: Literal["agent_start", "agent_end", "review_ready", "error"]
    agent: AgentName
    message: str
    payload: Any | None = None
    ts: str
    run_ms: int | None = None


class RadarStatement(BaseModel):
    decision_id: str
    date: str
    statement: str
    made_by: str


class RadarTopic(BaseModel):
    topic_key: str
    label: str
    versions: int
    flips: int
    last_changed: str
    churn: float
    risk: Literal["high", "medium", "low"]
    statements: list[RadarStatement] = Field(default_factory=list)
    note: str


# ---- Request bodies ----


class IngestRequest(BaseModel):
    project: str
    title: str
    date: str
    speaker: str
    source_type: SourceType = "voice"
    text: str


class VoiceEditRequest(BaseModel):
    instruction: str


class ApproveRequest(BaseModel):
    resolutions: dict[str, Literal["accept_new", "keep_old"]] = Field(default_factory=dict)
    ripple_actions: dict[str, Literal["apply", "skip"]] = Field(default_factory=dict)


class TaskPatch(BaseModel):
    status: Literal["todo", "done"]


class AskRequest(BaseModel):
    project: str
    question: str


class ClockSet(BaseModel):
    now: str

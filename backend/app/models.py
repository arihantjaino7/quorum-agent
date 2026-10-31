"""SQLModel tables. These are storage rows; app/schemas.py holds the wire types.

Only approved work lives here: pending review state lives in the LangGraph checkpoint (Phase 2)
until it is approved, so memory never contains unconfirmed decisions.
"""

from datetime import UTC, datetime

from sqlalchemy import JSON, Column, LargeBinary
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Project(SQLModel, table=True):
    name: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=_utcnow)


class Meeting(SQLModel, table=True):
    id: str = Field(primary_key=True)
    project: str = Field(index=True, foreign_key="project.name")
    title: str
    date: str  # ISO date
    speaker: str
    source_type: str  # voice | transcript | audio
    raw_text: str = ""
    clean_text: str = ""
    created_at: datetime = Field(default_factory=_utcnow)


class Decision(SQLModel, table=True):
    id: str = Field(primary_key=True)
    project: str = Field(index=True, foreign_key="project.name")
    topic_key: str = Field(index=True)
    statement: str
    made_by: str
    meeting_id: str = Field(index=True, foreign_key="meeting.id")
    date: str  # ISO date of the meeting
    status: str = "active"  # active | superseded (pending lives in the run checkpoint)
    superseded_by: str | None = None
    superseded_on: str | None = None  # ISO date the superseding decision was made (Time Machine)
    rationale: str | None = None
    source_quote: str | None = None


class Task(SQLModel, table=True):
    id: str = Field(primary_key=True)
    project: str = Field(index=True, foreign_key="project.name")
    title: str
    owner: str = Field(index=True)
    due_date: str | None = None
    raw_due_phrase: str = ""
    status: str = "todo"  # todo | done (pending lives in the run checkpoint)
    source_quote: str = ""
    meeting_id: str = Field(index=True, foreign_key="meeting.id")
    tracker_url: str | None = None
    reminder_sent: bool = False


class Conflict(SQLModel, table=True):
    """Conflicts recorded at approval time, with how they were resolved (for digest, brief, and radar)."""

    id: str = Field(primary_key=True)
    project: str = Field(index=True, foreign_key="project.name")
    meeting_id: str = Field(index=True)
    type: str
    severity: str
    new_item_id: str
    old_decision_id: str | None = None
    affected_task_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    explanation: str = ""
    suggested_resolution: str = ""
    resolution: str | None = None  # accept_new | keep_old | None (open)


class Run(SQLModel, table=True):
    thread_id: str = Field(primary_key=True)
    project: str
    status: str = "running"  # running | review | approved | rejected | error
    created_at: datetime = Field(default_factory=_utcnow)


class Setting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str


class Embedding(SQLModel, table=True):
    """float32 vector for a decision (or other item), used by the memory retriever (Phase 5)."""

    item_id: str = Field(primary_key=True)
    kind: str = "decision"
    model: str
    vector: bytes = Field(sa_column=Column(LargeBinary))

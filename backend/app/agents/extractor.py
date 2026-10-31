"""extractor agent (Phase 4).

Pulls structure out of the clean text. Decisions get a stable topic_key (reusing existing keys from
memory); tasks get owner, ISO due_date, raw_due_phrase and source_quote. Attribution rule: "Rahul said
X" means made_by = Rahul, not the speaker. A missing owner or due date becomes a Question instead of a guess.

Post-processing (deterministic): quotes are verified against the ORIGINAL words and snapped to the
closest real sentence when paraphrased; due dates are checked by app.services.dates; "I"/"me" owners
become the speaker; IDs and pending statuses are assigned here, never by the model.

Model tier: strong
Reads state:  clean_text, raw_text, meeting (+ memory: active decisions and known people)
Writes state: decisions: Decision[], tasks: Task[], questions: Question[]
"""

import logging
import re

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.agents.prompts import date_context
from app.db import get_engine
from app.ids import new_id
from app.integrations import llm
from app.models import Decision, Meeting, Task
from app.services import dates, quotes

log = logging.getLogger("quorum.extractor")


class DecisionOut(BaseModel):
    topic_key: str = Field(description="snake_case topic; reuse an existing key when it is the same subject")
    statement: str = Field(description="The decision as a short, self-contained sentence")
    made_by: str = Field(description="Who made or announced the decision")
    rationale: str | None
    source_quote: str = Field(description="Exact span from the ORIGINAL WORDS")


class TaskOut(BaseModel):
    title: str = Field(description="Short imperative title")
    owner: str | None = Field(description="Person responsible; null if nobody was named")
    due_date: str | None = Field(description="ISO date YYYY-MM-DD resolved against the meeting date; null if none")
    raw_due_phrase: str = Field(description="The deadline words exactly as said; empty string if none")
    source_quote: str = Field(description="Exact span from the ORIGINAL WORDS")
    depends_on_topic: str | None = Field(description="topic_key of a decision from this debrief that this task exists "
                                                     "because of; null if the task stands on its own")


class ExtractorOut(BaseModel):
    decisions: list[DecisionOut]
    tasks: list[TaskOut]


SYSTEM = """You extract decisions and action items from a meeting debrief or transcript.

Decisions:
- A decision is something the team settled (scope, dates, vendors, priorities), not a task.
- topic_key: reuse one of the EXISTING TOPIC KEYS below when the decision is about the same subject, even if
  it reverses it. Otherwise invent a short snake_case key.
- made_by: attribution matters. "Rahul said X" or "per Rahul, X" means made_by = "Rahul", not the speaker.
  Credit covers only the decision in that same statement (and its direct consequence, e.g. "because of that ...").
  A later, separate decision phrased as "we're switching to ..." or "we decided ..." is made by the speaker.
- statement: one short sentence stating the new state ("v1 ships on iOS and Android"), including the final
  value after any self-correction ("December 1st, no wait, November 28th" → 28 Nov).

Tasks:
- One task per concrete commitment with an owner ("X will/is going to/is taking/I'll ..."). "I" is the speaker.
- Skip chores that are not project work (office facilities, coffee machines) and anything nobody committed to.
- due_date: resolve against the meeting date and calendar below. "Next <weekday>" = first such weekday after
  the meeting date; a bare weekday = the next one after the meeting date; "the 20th" = next 20th on or after
  the meeting date. raw_due_phrase keeps the spoken words, fillers included (e.g. "by, uh, next Wednesday").
- depends_on_topic: if the task only makes sense because of one of the decisions you extracted (e.g. redoing
  onboarding for Android exists because of the platform decision), give that decision's topic_key; else null.
- source_quote must be copied exactly from the text."""


def build_messages(text: str, meeting_date: str, speaker: str, people: list[str],
                   existing: list[tuple[str, str]], raw_text: str | None = None) -> list[tuple[str, str]]:
    topics = "\n".join(f"  {k}: {stmt}" for k, stmt in existing) or "  (none yet)"
    system = (SYSTEM + "\n\n" + date_context(meeting_date)
              + f"\n\nKNOWN PEOPLE: {', '.join(people) or '(unknown)'}\nEXISTING TOPIC KEYS (current decisions):\n{topics}")
    if raw_text is None or raw_text.strip() == text.strip():
        return [("system", system), ("user", f"Speaker: {speaker}\n\n{text}")]
    return [
        ("system", system + "\n\nYou get the CLEANED TEXT (use it for meaning and dates) and the ORIGINAL WORDS. "
                            "Copy source_quote and raw_due_phrase from the ORIGINAL WORDS, verbatim."),
        ("user", f"Speaker: {speaker}\n\nCLEANED TEXT:\n{text}\n\nORIGINAL WORDS:\n{raw_text}"),
    ]


def memory_context(project: str, speaker: str) -> tuple[list[str], list[tuple[str, str]]]:
    """Known people and current decisions for the project, in a stable order (replay keys depend on it)."""
    with Session(get_engine()) as s:
        people = set(s.exec(select(Task.owner).where(Task.project == project)).all())
        people |= set(s.exec(select(Decision.made_by).where(Decision.project == project)).all())
        people |= set(s.exec(select(Meeting.speaker).where(Meeting.project == project)).all())
        active = s.exec(select(Decision).where(Decision.project == project, Decision.status == "active")).all()
    people.add(speaker)
    existing = sorted((d.topic_key, d.statement) for d in active)
    return sorted(p for p in people if p), existing


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "general"


def _person(name: str | None, speaker: str, people: list[str]) -> str:
    if not name or not name.strip():
        return ""
    name = name.strip()
    if name.lower() in {"i", "me", "myself", "speaker"}:
        return speaker
    return next((p for p in people if p.lower() == name.lower()), name)


def _valid_iso(value: str | None) -> str | None:
    if value and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            return dates.date.fromisoformat(value).isoformat()
        except ValueError:
            return None
    return None


def postprocess(out: ExtractorOut, *, raw_text: str, meeting: dict, people: list[str]) -> dict:
    speaker, mdate = meeting["speaker"], meeting["date"]

    def quote(q: str) -> str:
        snapped, changed = quotes.snap(q, raw_text)
        if changed and quotes.find_verbatim(q, raw_text) is None:
            log.info("[extractor] quote snapped to source: %r → %r", q[:60], snapped[:60])
        return snapped

    decisions = [{
        "id": new_id("dec"),
        "topic_key": _slug(d.topic_key),
        "statement": d.statement.strip(),
        "made_by": _person(d.made_by, speaker, people) or speaker,
        "meeting_id": meeting["id"],
        "date": mdate,
        "status": "pending",
        "superseded_by": None,
        "rationale": (d.rationale or "").strip() or None,
        "source_quote": quote(d.source_quote),
    } for d in out.decisions]

    tasks, questions = [], []
    for t in out.tasks:
        raw_phrase = quotes.find_verbatim(t.raw_due_phrase, raw_text) or t.raw_due_phrase.strip()
        due = _valid_iso(t.due_date)
        checked = dates.resolve(raw_phrase, mdate) if raw_phrase else None
        if checked is not None and checked.isoformat() != due:
            log.info("[extractor] due date fixed for %r: %s → %s", t.title, due, checked.isoformat())
            due = checked.isoformat()
        task = {
            "id": new_id("tsk"),
            "title": t.title.strip(),
            "owner": _person(t.owner, speaker, people),
            "due_date": due,
            "raw_due_phrase": raw_phrase,
            "status": "pending",
            "source_quote": quote(t.source_quote),
            "meeting_id": meeting["id"],
            "tracker_url": None,
            "reminder_sent": False,
            # Internal link used on approve ("keep previous" drops dependent tasks). Not part of the wire contract.
            "decision_id": next((d["id"] for d in decisions if d["topic_key"] == _slug(t.depends_on_topic or "")), None),
        }
        tasks.append(task)
        if not task["owner"]:
            questions.append({"id": new_id("q"), "item_id": task["id"], "field": "owner",
                              "prompt": f"Who owns “{task['title']}”?"})
        if not task["due_date"]:
            questions.append({"id": new_id("q"), "item_id": task["id"], "field": "due_date",
                              "prompt": f"When is “{task['title']}” due?"})
    return {"decisions": decisions, "tasks": tasks, "questions": questions}


async def run(state: dict) -> dict:
    meeting = state["meeting"]
    people, existing = memory_context(meeting["project"], meeting["speaker"])
    msgs = build_messages(state["clean_text"], meeting["date"], meeting["speaker"], people, existing,
                          raw_text=state["raw_text"])
    out = await llm.structured(NODE, "strong", ExtractorOut, msgs)
    return postprocess(out, raw_text=state["raw_text"], meeting=meeting, people=people)


def describe(update: dict) -> str:
    d, t, q = len(update.get("decisions", [])), len(update.get("tasks", [])), len(update.get("questions", []))
    msg = f"Found {d} decision{'s' * (d != 1)} and {t} task{'s' * (t != 1)}"
    return msg + (f"; {q} question{'s' * (q != 1)} for you" if q else "")


# Flipped to True when the real node lands; the golden test enables its checks on this flag.
IMPLEMENTED = True
NODE = "extractor"

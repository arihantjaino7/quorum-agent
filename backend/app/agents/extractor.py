"""extractor agent (Phase 4).

Pulls structure out of the clean text. Decisions get a stable topic_key (reusing existing keys
from memory where possible); tasks get owner, ISO due_date, raw_due_phrase, and source_quote.
Attribution rule: 'Rahul said X' means made_by = Rahul, not the speaker. Missing owner or
due date becomes a Question instead of a guess.

Model tier: strong
Reads state:  clean_text, meeting, known people/topic_keys
Writes state: decisions: Decision[], tasks: Task[], questions: Question[]
"""

from pydantic import BaseModel, Field

from app.agents.prompts import date_context


class DecisionOut(BaseModel):
    topic_key: str = Field(description="snake_case topic; reuse an existing key when it is the same subject")
    statement: str = Field(description="The decision as a short, self-contained sentence")
    made_by: str = Field(description="Who made or announced the decision")
    rationale: str | None
    source_quote: str = Field(description="Exact span from the text")


class TaskOut(BaseModel):
    title: str = Field(description="Short imperative title")
    owner: str | None = Field(description="Person responsible; null if nobody was named")
    due_date: str | None = Field(description="ISO date YYYY-MM-DD resolved against the meeting date; null if none")
    raw_due_phrase: str = Field(description="The deadline words exactly as said; empty string if none")
    source_quote: str = Field(description="Exact span from the text")


class ExtractorOut(BaseModel):
    decisions: list[DecisionOut]
    tasks: list[TaskOut]


SYSTEM = """You extract decisions and action items from a meeting debrief or transcript.

Decisions:
- A decision is something the team settled (scope, dates, vendors, priorities), not a task.
- topic_key: reuse one of the EXISTING TOPIC KEYS below when the decision is about the same subject, even if
  it reverses it. Otherwise invent a short snake_case key.
- made_by: attribution matters. "Rahul said X" or "per Rahul, X" means made_by = "Rahul", not the speaker.
  If nobody else is credited, made_by is the speaker.
- statement: one short sentence stating the new state ("v1 ships on iOS and Android"), including the final
  value after any self-correction ("December 1st, no wait, November 28th" → 28 Nov).

Tasks:
- One task per concrete commitment with an owner ("X will/is going to/is taking/I'll ..."). "I" is the speaker.
- Skip chores that are not project work (office facilities, coffee machines) and anything nobody committed to.
- due_date: resolve against the meeting date and calendar below. "Next <weekday>" = first such weekday after
  the meeting date; a bare weekday = the next one after the meeting date; "the 20th" = next 20th on or after
  the meeting date. raw_due_phrase keeps the spoken words, fillers included (e.g. "by, uh, next Wednesday").
- source_quote must be copied exactly from the text."""


def build_messages(text: str, meeting_date: str, speaker: str, people: list[str],
                   existing: list[tuple[str, str]]) -> list[tuple[str, str]]:
    topics = "\n".join(f"  {k}: {stmt}" for k, stmt in existing) or "  (none yet)"
    return [
        ("system", SYSTEM + "\n\n" + date_context(meeting_date)
         + f"\n\nKNOWN PEOPLE: {', '.join(people) or '(unknown)'}\nEXISTING TOPIC KEYS (current decisions):\n{topics}"),
        ("user", f"Speaker: {speaker}\n\n{text}"),
    ]


# Flipped to True when the real node lands; the golden test enables its checks on this flag.
IMPLEMENTED = False
NODE = "extractor"


async def run(state: dict) -> dict:
    """LangGraph node. Returns a partial state update."""
    raise NotImplementedError("extractor is built in Phase 4 (see PLAN_BACKEND.md)")

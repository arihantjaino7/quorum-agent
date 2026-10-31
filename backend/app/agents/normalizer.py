"""normalizer agent (Phase 4).

Cleans dictated speech: drops fillers ('uh', 'like'), cuts digressions (the coffee machine),
applies self-corrections ('December 1st, no wait, November 28th' → 28 Nov), and resolves relative
dates against the meeting date ('next Wednesday' → 2026-11-04). Every change is reported as a
Correction so the UI can show a 'what we cleaned' diff.

Model tier: fast
Reads state:  raw_text, meeting.date
Writes state: clean_text, corrections: Correction[]
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.agents.prompts import date_context


class CorrectionOut(BaseModel):
    original: str = Field(description="The exact words as spoken")
    resolved: str = Field(description="What it became; empty string when removed. Date resolutions must contain the ISO date.")
    kind: Literal["self_correction", "filler", "digression", "date_resolution"]


class NormalizerOut(BaseModel):
    clean_text: str
    corrections: list[CorrectionOut]


SYSTEM = """You clean up a dictated meeting debrief so it can be turned into decisions and tasks.

Rules:
- Remove filler words (um, uh, like, basically, yeah, so). Report them as ONE correction of kind "filler"
  whose original lists the removed words, comma-separated, and whose resolved is "".
- Remove digressions unrelated to the project's decisions or work (office chatter, small talk). Report each as
  kind "digression" with the full digression as original and resolved "".
- Apply self-corrections ("X, no wait, Y" means Y). Report each as kind "self_correction": original is the
  spoken phrase including the correction, resolved is the final value.
- Resolve every relative or partial date ("next Wednesday", "Monday", "the 20th", "December 1st") against the
  meeting date and calendar below. Report each as kind "date_resolution": original is the spoken phrase,
  resolved is "<weekday> <ISO date>", e.g. "Wednesday 2026-11-04". "Next <weekday>" means the first such
  weekday after the meeting date; a bare weekday means the next one after the meeting date; "the 20th" means
  the next 20th on or after the meeting date.
- In clean_text keep every decision, task, owner, reason and date; write resolved dates in clean_text as
  "<weekday> <ISO date> (said: '<original phrase>')". Keep the speaker's attributions ("Rahul said ...").
- Do not invent anything. Keep it in the first person of the speaker where they spoke that way."""


def build_messages(raw_text: str, meeting_date: str, speaker: str) -> list[tuple[str, str]]:
    return [
        ("system", SYSTEM + "\n\n" + date_context(meeting_date)),
        ("user", f"Debrief dictated by {speaker}:\n\n{raw_text}"),
    ]


# Flipped to True when the real node lands; the golden test enables its checks on this flag.
IMPLEMENTED = False
NODE = "normalizer"


async def run(state: dict) -> dict:
    """LangGraph node. Returns a partial state update."""
    raise NotImplementedError("normalizer is built in Phase 4 (see PLAN_BACKEND.md)")

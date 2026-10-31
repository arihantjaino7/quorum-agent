"""normalizer agent (Phase 4).

Cleans dictated speech: drops fillers ('uh', 'like'), cuts digressions (the coffee machine),
applies self-corrections ('December 1st, no wait, November 28th' → 28 Nov), and resolves relative
dates against the meeting date ('next Wednesday' → 2026-11-04). Every change is reported as a
Correction so the UI can show a 'what we cleaned' diff.

Post-processing (deterministic): all filler corrections are merged into ONE summary line, and every
date resolution is checked by app.services.dates (Python wins when it can parse the phrase).
Transcripts ("Name: line") get a light-touch prompt that keeps every speaker line.

Model tier: fast
Reads state:  raw_text, meeting
Writes state: clean_text, corrections: Correction[]
"""

import logging
import re
from typing import Literal

from pydantic import BaseModel, Field

from app.agents.prompts import date_context
from app.integrations import llm
from app.services import dates

log = logging.getLogger("quorum.normalizer")


class CorrectionOut(BaseModel):
    original: str = Field(description="The exact words as spoken")
    resolved: str = Field(description="What it became; empty string when removed. Date resolutions must contain the ISO date.")
    kind: Literal["self_correction", "filler", "digression", "date_resolution"]


class NormalizerOut(BaseModel):
    clean_text: str
    corrections: list[CorrectionOut]


_DATE_RULES = """- Resolve every relative or partial date ("next Wednesday", "Monday", "the 20th", "December 1st") against the
  meeting date and calendar below. Report each as kind "date_resolution": original is the spoken phrase,
  resolved is "<weekday> <ISO date>", e.g. "Wednesday 2026-11-04". "Next <weekday>" means the first such
  weekday after the meeting date; a bare weekday means the next one after the meeting date; "the 20th" means
  the next 20th on or after the meeting date."""

SYSTEM = f"""You clean up a dictated meeting debrief so it can be turned into decisions and tasks.

Rules:
- Remove filler words (um, uh, like, basically, yeah, so). Report them as ONE correction of kind "filler"
  whose original lists the removed words, comma-separated, and whose resolved is "".
- Remove digressions unrelated to the project's decisions or work (office chatter, small talk). Report each as
  kind "digression" with the full digression as original and resolved "".
- Apply self-corrections ("X, no wait, Y" means Y). Report each as kind "self_correction": original is the
  spoken phrase including the correction, resolved is the final value.
{_DATE_RULES}
- In clean_text keep every decision, task, owner, reason and date; write resolved dates in clean_text as
  "<weekday> <ISO date> (said: '<original phrase>')". Keep the speaker's attributions ("Rahul said ...").
- Do not invent anything. Keep it in the first person of the speaker where they spoke that way."""

SYSTEM_TRANSCRIPT = f"""You lightly clean a meeting transcript made of "Name: line" speaker turns.

Rules:
- Keep EVERY speaker turn, in order, with its "Name:" label exactly as written. Never merge, reorder or
  re-attribute turns. Never paraphrase what someone decided or committed to.
- Inside turns, remove filler words (um, uh, like, you know). Report them as ONE correction of kind "filler"
  whose original lists the removed words, comma-separated, and whose resolved is "".
- Remove turns or sentences that are pure small talk unrelated to the work. Report each as kind "digression".
- Apply explicit self-corrections ("X, no wait, Y" means Y) as kind "self_correction".
{_DATE_RULES}
- In clean_text append the resolved ISO date in brackets after each date phrase, e.g. "by November 3rd [2026-11-03]".
- Do not invent anything."""


def build_messages(raw_text: str, meeting_date: str, speaker: str,
                   source_type: str = "voice") -> list[tuple[str, str]]:
    if source_type == "transcript":
        return [("system", SYSTEM_TRANSCRIPT + "\n\n" + date_context(meeting_date)),
                ("user", f"Transcript (uploaded by {speaker}):\n\n{raw_text}")]
    return [
        ("system", SYSTEM + "\n\n" + date_context(meeting_date)),
        ("user", f"Debrief dictated by {speaker}:\n\n{raw_text}"),
    ]


_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")


def postprocess(out: NormalizerOut, raw_text: str, meeting_date: str) -> dict:
    corrections: list[dict] = []
    fillers: list[str] = []
    for c in out.corrections:
        if c.kind == "filler":
            for word in re.split(r"[,;]\s*", c.original):
                word = word.strip().strip("'\"").lower()
                if word and word not in fillers:
                    fillers.append(word)
            continue
        item = c.model_dump()
        if c.kind in ("date_resolution", "self_correction"):
            d = dates.resolve(c.original, meeting_date)
            if d is not None:
                iso = d.isoformat()
                found = _ISO.findall(item["resolved"])
                if c.kind == "date_resolution":
                    if found and found[-1] != iso:
                        log.info("[normalizer] date fixed: %r %s → %s", c.original, found[-1], iso)
                    item["resolved"] = f"{d:%A} {iso}"
                elif not found:
                    item["resolved"] = f"{item['resolved']} ({iso})".strip()
        corrections.append(item)
    if fillers:
        corrections.insert(0, {"original": ", ".join(fillers), "resolved": "", "kind": "filler"})
    clean = out.clean_text.strip() or raw_text
    return {"clean_text": clean, "corrections": corrections}


async def run(state: dict) -> dict:
    meeting = state["meeting"]
    msgs = build_messages(state["raw_text"], meeting["date"], meeting["speaker"], meeting["source_type"])
    out = await llm.structured(NODE, "fast", NormalizerOut, msgs)
    return postprocess(out, state["raw_text"], meeting["date"])


def describe(update: dict) -> str:
    counts: dict[str, int] = {}
    for c in update.get("corrections", []):
        counts[c["kind"]] = counts.get(c["kind"], 0) + 1
    parts = []
    if n := counts.get("self_correction"):
        parts.append(f"applied {n} self-correction{'s' * (n > 1)}")
    if n := counts.get("date_resolution"):
        parts.append(f"resolved {n} date{'s' * (n > 1)}")
    if n := counts.get("digression"):
        parts.append(f"cut {n} digression{'s' * (n > 1)}")
    filler = next((c for c in update.get("corrections", []) if c["kind"] == "filler"), None)
    if filler:
        parts.append(f"removed {len(filler['original'].split(','))} fillers")
    return (", ".join(parts) or "Nothing to clean").capitalize()


# Flipped to True when the real node lands; the golden test enables its checks on this flag.
IMPLEMENTED = True
NODE = "normalizer"

"""normalizer agent (Phase 4).

Cleans dictated speech: drops fillers ('uh', 'like'), cuts digressions (the coffee machine),
applies self-corrections ('December 1st, no wait, November 28th' → 28 Nov), and resolves relative
dates against the meeting date ('next Wednesday' → 2026-11-04). Every change is reported as a
Correction so the UI can show a 'what we cleaned' diff.

Model tier: fast
Reads state:  raw_text, meeting.date
Writes state: clean_text, corrections: Correction[]
"""

# Flipped to True when the real node lands; the golden test enables its checks on this flag.
IMPLEMENTED = False
NODE = "normalizer"


async def run(state: dict) -> dict:
    """LangGraph node. Returns a partial state update."""
    raise NotImplementedError("normalizer is built in Phase 4 (see PLAN_BACKEND.md)")

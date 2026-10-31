"""extractor agent (Phase 4).

Pulls structure out of the clean text. Decisions get a stable topic_key (reusing existing keys
from memory where possible); tasks get owner, ISO due_date, raw_due_phrase, and source_quote.
Attribution rule: 'Rahul said X' means made_by = Rahul, not the speaker. Missing owner or
due date becomes a Question instead of a guess.

Model tier: strong
Reads state:  clean_text, meeting, known people/topic_keys
Writes state: decisions: Decision[], tasks: Task[], questions: Question[]
"""

# Flipped to True when the real node lands; the golden test enables its checks on this flag.
IMPLEMENTED = False
NODE = "extractor"


async def run(state: dict) -> dict:
    """LangGraph node. Returns a partial state update."""
    raise NotImplementedError("extractor is built in Phase 4 (see PLAN_BACKEND.md)")

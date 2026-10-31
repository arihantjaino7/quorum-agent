"""review_editor agent (Phase 8).

Applies spoken edits to the pending review, e.g. 'approve all but make Rahul's deadline the 18th'.
Returns a structured patch (not free text) so every change is listed back to the user.

Model tier: strong
Reads state:  ReviewPayload, spoken instruction
Writes state: ReviewPayload (edited), changes: string[]
"""

# Flipped to True when the real node lands; the golden test enables its checks on this flag.
IMPLEMENTED = False
NODE = "review_editor"


async def run(state: dict) -> dict:
    """LangGraph node. Returns a partial state update."""
    raise NotImplementedError("review_editor is built in Phase 8 (see PLAN_BACKEND.md)")

"""ripple agent (Phase 7).

Ripple Effect. For every accepted-by-default reversal, trace the existing tasks that were built on
the old decision and propose reschedule / rescope / cancel; flag work the new decision implies
that nobody owns; and draft one short 'what changed for you' note per affected person.

Model tier: strong
Reads state:  conflicts, open tasks from memory
Writes state: ripples: Ripple[], heads_up: HeadsUp[]
"""

# Flipped to True when the real node lands; the golden test enables its checks on this flag.
IMPLEMENTED = False
NODE = "ripple"


async def run(state: dict) -> dict:
    """LangGraph node. Returns a partial state update."""
    raise NotImplementedError("ripple is built in Phase 7 (see PLAN_BACKEND.md)")

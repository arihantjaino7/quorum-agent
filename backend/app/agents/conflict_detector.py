"""conflict_detector agent (Phase 5).

Two layers. (1) The LLM judges whether a new decision reverses or contradicts a retrieved past
decision and explains why. (2) Deterministic Python checks: deadline collisions (a task due after
the date it depends on, or past the launch) and owner overload (3+ tasks due the same day).

Model tier: strong
Reads state:  decisions, tasks, related, open tasks
Writes state: conflicts: Conflict[]
"""

# Flipped to True when the real node lands; the golden test enables its checks on this flag.
IMPLEMENTED = False
NODE = "conflict_detector"


async def run(state: dict) -> dict:
    """LangGraph node. Returns a partial state update."""
    raise NotImplementedError("conflict_detector is built in Phase 5 (see PLAN_BACKEND.md)")

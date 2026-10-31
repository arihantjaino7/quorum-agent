"""executor agent (Phase 6).

Creates tasks in Notion (primary), falling back to GitHub Issues and then to local-only, applies ripple
actions, and sends heads-up messages over Telegram (or logs them). Never crashes on a missing key.

Model tier: none
Reads state:  approved ReviewPayload + resolutions + ripple_actions
Writes state: created/updated tasks with tracker_url
"""

# Flipped to True when the real node lands; the golden test enables its checks on this flag.
IMPLEMENTED = False
NODE = "executor"


async def run(state: dict) -> dict:
    """LangGraph node. Returns a partial state update."""
    raise NotImplementedError("executor is built in Phase 6 (see PLAN_BACKEND.md)")

"""memory_writer agent (Phase 6).

Persists approved decisions with embeddings, marks overridden decisions superseded (superseded_by
set) to keep lineage, and records keep_old resolutions so the new decision is dropped.

Model tier: none (local embeddings)
Reads state:  approved decisions + resolutions
Writes state: superseded_ids
"""

# Flipped to True when the real node lands; the golden test enables its checks on this flag.
IMPLEMENTED = False
NODE = "memory_writer"


async def run(state: dict) -> dict:
    """LangGraph node. Returns a partial state update."""
    raise NotImplementedError("memory_writer is built in Phase 6 (see PLAN_BACKEND.md)")

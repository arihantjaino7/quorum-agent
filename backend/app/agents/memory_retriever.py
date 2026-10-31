"""memory_retriever agent (Phase 5).

Semantic search over past active decisions in the same project using fastembed vectors stored
in SQLite. Same-topic_key matches are always included; embedding similarity catches the rest.

Model tier: none (local embeddings)
Reads state:  decisions (new)
Writes state: related: {new_decision_id: [past Decision + score]}
"""

# Flipped to True when the real node lands; the golden test enables its checks on this flag.
IMPLEMENTED = False
NODE = "memory_retriever"


async def run(state: dict) -> dict:
    """LangGraph node. Returns a partial state update."""
    raise NotImplementedError("memory_retriever is built in Phase 5 (see PLAN_BACKEND.md)")

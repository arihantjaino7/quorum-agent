"""memory_retriever agent (Phase 5).

For every new decision, find the past ACTIVE decisions in the same project it might conflict with:
same topic_key (always included) ∪ the closest past decisions by embedding similarity (local fastembed
vectors stored in SQLite). No LLM. If embeddings are unavailable it degrades to topic_key matching.

Model tier: none (local embeddings)
Reads state:  decisions (new), meeting.project
Writes state: related: {new_decision_id: [{"decision": Decision, "score": float, "why": "same_topic"|"similar"}]}
"""

import asyncio

import numpy as np
from sqlmodel import Session, select

from app import views
from app.db import get_engine
from app.models import Decision
from app.services import embeddings

TOP_K = 3
MIN_SIMILARITY = 0.55


def find_related(project: str, new_decisions: list[dict]) -> dict[str, list[dict]]:
    with Session(get_engine()) as s:
        rows = s.exec(select(Decision).where(Decision.project == project, Decision.status == "active")
                      .order_by(Decision.date, Decision.id)).all()
        past = [views.decision(r).model_dump() for r in rows]  # plain data before any commit expires the rows
        if not past or not new_decisions:
            return {d["id"]: [] for d in new_decisions}
        past_vecs = embeddings.vectors_for(s, {p["id"]: embeddings.decision_text(p["topic_key"], p["statement"])
                                               for p in past})
    new_vecs = embeddings.embed([embeddings.decision_text(d["topic_key"], d["statement"]) for d in new_decisions]) \
        if past_vecs else None

    related: dict[str, list[dict]] = {}
    for i, d in enumerate(new_decisions):
        hits: dict[str, dict] = {}
        for p in past:
            if p["topic_key"] == d["topic_key"]:
                score = float(np.dot(new_vecs[i], past_vecs[p["id"]])) if new_vecs is not None else 1.0
                hits[p["id"]] = {"decision": p, "score": round(score, 3), "why": "same_topic"}
        if new_vecs is not None:
            scored = sorted(((float(np.dot(new_vecs[i], past_vecs[p["id"]])), p) for p in past), key=lambda x: -x[0])
            for score, p in scored[:TOP_K]:
                if score >= MIN_SIMILARITY and p["id"] not in hits:
                    hits[p["id"]] = {"decision": p, "score": round(score, 3), "why": "similar"}
        related[d["id"]] = sorted(hits.values(), key=lambda h: (h["why"] != "same_topic", -h["score"]))
    return related


async def run(state: dict) -> dict:
    # Embedding (and the first-use model load) is CPU work: keep it off the event loop so SSE keeps flowing.
    related = await asyncio.to_thread(find_related, state["meeting"]["project"], state.get("decisions", []))
    return {"related": related}


def describe(update: dict) -> str:
    related = update.get("related", {})
    n_new = len(related)
    linked = {h["decision"]["id"] for hits in related.values() for h in hits}
    if not n_new:
        return "No new decisions to check"
    return f"Matched {n_new} new decision{'s' * (n_new != 1)} to {len(linked)} past decision{'s' * (len(linked) != 1)}"


# Flipped to True when the real node lands; the golden test enables its checks on this flag.
IMPLEMENTED = True
NODE = "memory_retriever"

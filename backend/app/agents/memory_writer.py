"""memory_writer agent (Phase 6).

Persists approved decisions with embeddings, marks overridden decisions superseded (superseded_by
set) to keep lineage, and records how every conflict was resolved. Rejected or kept-previous decisions are
never stored, so memory only holds what a human confirmed.

Model tier: none (local embeddings)
Reads state:  decisions, conflicts, review_action (resolutions)
Writes state: result.superseded_ids
"""

import asyncio
import logging

from sqlmodel import Session, select

from app import models
from app.db import get_engine
from app.services import approval, embeddings
from app.services.persist import ensure_meeting

log = logging.getLogger("quorum.memory")


def _write(state: dict) -> list[str]:
    p = approval.plan(state)
    meeting = state["meeting"]
    superseded: list[str] = []
    with Session(get_engine()) as s:
        ensure_meeting(s, state)
        saved = {d["id"]: d for d in p["save"]}
        for d in p["save"]:
            if s.get(models.Decision, d["id"]) is None:
                s.add(models.Decision(id=d["id"], project=meeting["project"], topic_key=d["topic_key"],
                                      statement=d["statement"], made_by=d["made_by"], meeting_id=meeting["id"],
                                      date=meeting["date"], status="active", rationale=d.get("rationale"),
                                      source_quote=d.get("source_quote")))
        s.flush()
        for new_id, olds in p["supersedes"].items():
            if new_id not in saved:
                continue
            targets = set(olds)
            targets |= {i for t, i in p["active_by_topic"].items() if t == saved[new_id]["topic_key"]}
            for old_id in targets:
                old = s.get(models.Decision, old_id)
                if old is not None and old.status == "active" and old.id != new_id:
                    old.status, old.superseded_by, old.superseded_on = "superseded", new_id, meeting["date"]
                    s.add(old)
                    superseded.append(old.id)
        for c in state.get("conflicts", []):
            if s.get(models.Conflict, c["id"]) is None:
                s.add(models.Conflict(
                    id=c["id"], project=meeting["project"], meeting_id=meeting["id"], type=c["type"],
                    severity=c["severity"], new_item_id=c["new_item_id"],
                    old_decision_id=(c.get("old_decision") or {}).get("id"),
                    affected_task_ids=[t["id"] for t in c.get("affected_tasks", [])],
                    explanation=c.get("explanation", ""), suggested_resolution=c.get("suggested_resolution", ""),
                    resolution=p["resolutions"].get(c["id"], "accept_new")))
        s.commit()
        try:  # embeddings are a nice-to-have for retrieval; never fail an approval over them
            embeddings.vectors_for(s, {d["id"]: embeddings.decision_text(d["topic_key"], d["statement"]) for d in p["save"]})
        except Exception as e:  # pragma: no cover - model unavailable
            log.warning("[memory] embeddings skipped: %s", type(e).__name__)
    for item in p["skipped"]:
        log.info("[memory] decision %s not stored (%s)", item["id"], item["why"])
    return superseded


async def run(state: dict) -> dict:
    superseded = await asyncio.to_thread(_write, state)
    return {"result": {**(state.get("result") or {}), "superseded_ids": superseded}}


def describe(update: dict) -> str:
    n = len(update["result"]["superseded_ids"])
    return f"Memory updated; {n} earlier decision{'s' * (n != 1)} retired" if n else "Memory updated"


# Flipped to True when the real node lands; the golden test enables its checks on this flag.
IMPLEMENTED = True
NODE = "memory_writer"

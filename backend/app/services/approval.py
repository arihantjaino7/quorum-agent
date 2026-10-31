"""Decides what an approval actually changes. Shared by the executor and the memory writer.

Rules (user decisions, 31 Oct):
- "keep previous" on a conflict drops the new decision AND every new task that depends on it.
- A new decision that only repeats an active decision on the same topic (no reversal/contradiction found) is skipped.
- Conflicts left without a ruling count as "accept new".
"""

from sqlmodel import Session, select

from app.db import get_engine
from app.models import Decision


def plan(state: dict) -> dict:
    action = state.get("review_action") or {}
    resolutions: dict = action.get("resolutions") or {}
    kept: set[str] = set()
    supersedes: dict[str, set[str]] = {}
    for c in state.get("conflicts", []):
        if resolutions.get(c["id"], "accept_new") == "keep_old":
            kept.add(c["new_item_id"])
        elif c.get("old_decision") and c["type"] in ("reversal", "contradiction"):
            supersedes.setdefault(c["new_item_id"], set()).add(c["old_decision"]["id"])

    project = state["meeting"]["project"]
    with Session(get_engine()) as s:
        active = {d.topic_key: d.id for d in s.exec(
            select(Decision).where(Decision.project == project, Decision.status == "active")).all()}

    save, skipped = [], []
    for d in state.get("decisions", []):
        if d["id"] in kept:
            skipped.append({"id": d["id"], "why": "kept previous"})
        elif d["id"] not in supersedes and d["topic_key"] in active:
            skipped.append({"id": d["id"], "why": "confirms existing"})
        else:
            save.append(d)

    tasks, dropped = [], []
    for t in state.get("tasks", []):
        if t["id"] in kept or (t.get("decision_id") and t["decision_id"] in kept):
            dropped.append(t["id"])
        else:
            tasks.append(t)
    return {"kept": kept, "supersedes": supersedes, "save": save, "skipped": skipped, "tasks": tasks,
            "dropped": dropped, "resolutions": resolutions, "active_by_topic": active}

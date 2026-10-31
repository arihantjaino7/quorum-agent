"""executor agent (Phase 6).

Creates the approved tasks (Notion, then GitHub Issues, then local-only), applies the chosen ripple actions to
existing tasks, and sends one heads-up per affected person (Telegram, or a log line). Safe to run twice: tasks
that already exist are reused, so Retry never duplicates anything. Never crashes on a missing key.

Model tier: none
Reads state:  tasks, ripples, heads_up, review_action
Writes state: result (created_tasks, updated_tasks, cancelled_task_ids, heads_up_sent)
"""

import logging

from sqlmodel import Session

from app import models, views
from app.db import get_engine
from app.integrations import trackers
from app.services import approval
from app.services.persist import ensure_meeting

log = logging.getLogger("quorum.executor")


async def run(state: dict) -> dict:
    p = approval.plan(state)
    meeting = state["meeting"]
    created, updated, cancelled, heads = [], [], [], []

    with Session(get_engine()) as s:
        ensure_meeting(s, state)
    for t in p["tasks"]:
        with Session(get_engine()) as s:
            row = s.get(models.Task, t["id"])
            if row is None:
                url = await trackers.create_task_link(t, meeting["title"])
                row = models.Task(id=t["id"], project=meeting["project"], title=t["title"], owner=t.get("owner") or "",
                                  due_date=t.get("due_date"), raw_due_phrase=t.get("raw_due_phrase", ""), status="todo",
                                  source_quote=t.get("source_quote", ""), meeting_id=meeting["id"], tracker_url=url)
                s.add(row)
                s.commit()
                s.refresh(row)
            created.append(views.task(row).model_dump())

    # Ripples: apply what the user left switched on, skipping any whose conflict was kept-previous.
    actions = (state.get("review_action") or {}).get("ripple_actions") or {}
    applied: set[str] = set()
    for r in state.get("ripples", []):
        if r["decision_id"] in p["kept"] or p["resolutions"].get(r.get("conflict_id") or "", "accept_new") == "keep_old":
            continue
        if actions.get(r["id"], r.get("default_action", "apply")) != "apply" or not r.get("task"):
            continue
        with Session(get_engine()) as s:
            row = s.get(models.Task, r["task"]["id"])
            if row is None:
                continue
            if r["kind"] == "cancel":
                s.delete(row)
                s.commit()
                cancelled.append(r["task"]["id"])
            else:
                prop = r.get("proposal") or {}
                for field in ("title", "owner", "due_date", "raw_due_phrase"):
                    if prop.get(field):
                        setattr(row, field, prop[field])
                s.add(row)
                s.commit()
                s.refresh(row)
                updated = [u for u in updated if u["id"] != row.id] + [views.task(row).model_dump()]
        applied.add(r["id"])

    for h in state.get("heads_up", []):
        if not set(h.get("ripple_ids", [])) & applied:
            continue
        channel = await trackers.send_chat(f"📣 {h['person']}, here's what changed for you:\n\n{h['message_md']}")
        heads.append({"person": h["person"], "channel": channel})

    result = {**(state.get("result") or {}), "created_tasks": created, "updated_tasks": updated,
              "cancelled_task_ids": cancelled, "heads_up_sent": heads}
    return {"result": result}


def describe(update: dict) -> str:
    r = update["result"]
    parts = [f"created {len(r['created_tasks'])} task{'s' * (len(r['created_tasks']) != 1)}"]
    linked = sum(1 for t in r["created_tasks"] if t.get("tracker_url"))
    parts.append(f"{linked} linked in the tracker" if linked else "kept locally")
    if r["updated_tasks"] or r["cancelled_task_ids"]:
        parts.append(f"updated {len(r['updated_tasks']) + len(r['cancelled_task_ids'])} existing")
    if r["heads_up_sent"]:
        parts.append(f"{len(r['heads_up_sent'])} heads-ups")
    return ", ".join(parts).capitalize()


# Flipped to True when the real node lands; the golden test enables its checks on this flag.
IMPLEMENTED = True
NODE = "executor"

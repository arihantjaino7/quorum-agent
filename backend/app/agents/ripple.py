"""ripple agent (Phase 7).

Ripple Effect. For every accepted-by-default reversal, finds the existing tasks that were built on the old
decision (the conflict agent already named them) and proposes a change for each: a date move when the decision
moved a date (the task shifts by the same number of days), otherwise a rescope. Then drafts one short
"what changed for you" note per affected person. Deterministic: no model call, so it is fast and can't drift.

Model tier: none
Reads state:  conflicts, decisions
Writes state: ripples: Ripple[], heads_up: HeadsUp[]
"""

import re
from datetime import date, timedelta

from app.ids import new_id
from app.services import dates

_MONTH_WORDS = re.compile(
    r"\b(?:\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?[A-Za-z]{3,9}|[A-Za-z]{3,9}\.?\s+\d{1,2}(?:st|nd|rd|th)?)\b")


def _date_in(text: str, base: str) -> date | None:
    for m in _MONTH_WORDS.finditer(text):
        found = dates.resolve(m.group(0), base)
        if found:
            return found
    return None


def _short(d: str) -> str:
    return f"{date.fromisoformat(d):%-d %b}"


def build(state: dict) -> dict:
    meeting_date = state["meeting"]["date"]
    decisions = {d["id"]: d for d in state.get("decisions", [])}
    ripples: list[dict] = []
    for c in state.get("conflicts", []):
        old, new = c.get("old_decision"), decisions.get(c["new_item_id"])
        if not old or not new or c["type"] not in ("reversal", "contradiction"):
            continue
        before, after = _date_in(old["statement"], old["date"]), _date_in(new["statement"], meeting_date)
        delta = (after - before).days if before and after and before != after else 0
        for task in c.get("affected_tasks", []):
            if delta and task.get("due_date"):
                moved = (date.fromisoformat(task["due_date"]) + timedelta(days=delta)).isoformat()
                ripples.append({
                    "id": new_id("rpl"), "conflict_id": c["id"], "decision_id": new["id"], "kind": "reschedule", "task": task,
                    "reason": f"{new['made_by']} moved the date from {_short(before.isoformat())} to {_short(after.isoformat())} "
                              f"({delta:+d} days), so this shifts with it.",
                    "proposal": {"due_date": moved, "raw_due_phrase": f"moved with the launch ({delta:+d} days)"},
                    "default_action": "apply"})
            else:
                label = new["statement"].rstrip(".")
                ripples.append({
                    "id": new_id("rpl"), "conflict_id": c["id"], "decision_id": new["id"], "kind": "rescope", "task": task,
                    "reason": f"“{old['statement']}” was replaced by “{new['statement']}”, so this work needs a fresh scope.",
                    "proposal": {"title": f"{task['title']} (rescoped: {label})"[:120]},
                    "default_action": "apply"})
    heads: list[dict] = []
    for person in dict.fromkeys(r["task"]["owner"] for r in ripples if r["task"].get("owner")):
        mine = [r for r in ripples if r["task"].get("owner") == person]
        lines = []
        for r in mine:
            if r["kind"] == "reschedule":
                lines.append(f"- **{r['task']['title']}** moves to {_short(r['proposal']['due_date'])} "
                             f"(was {_short(r['task']['due_date'])}).")
            else:
                lines.append(f"- **{r['task']['title']}** needs a new scope: {r['reason']}")
        heads.append({"person": person, "message_md": "\n".join(lines), "ripple_ids": [r["id"] for r in mine],
                      "task_ids": list(dict.fromkeys(r["task"]["id"] for r in mine))})
    return {"ripples": ripples, "heads_up": heads}


async def run(state: dict) -> dict:
    return build(state)


def describe(update: dict) -> str:
    ripples = update.get("ripples", [])
    n = len(ripples)
    tasks = len({r["task"]["id"] for r in ripples})
    return f"{tasks} existing task{'s' * (tasks != 1)} affected; {n} change{'s' * (n != 1)} proposed" if n else "No existing work affected"


# Flipped to True when the real node lands; the golden test enables its checks on this flag.
IMPLEMENTED = True
NODE = "ripple"

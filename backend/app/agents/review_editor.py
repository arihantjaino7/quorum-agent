"""review_editor agent (Phase 8).

Applies spoken edits to the pending review, e.g. 'make Rahul's deadline the 18th and drop the investor update'.
The model returns a structured list of operations (not free text); Python applies them, resolves dates with the
deterministic resolver, and lists every change back to the user.

Model tier: strong
Reads state:  decisions, tasks, questions, conflicts, review_action.instruction
Writes state: the edited decisions/tasks/questions/conflicts, ripples, heads_up, changes: string[]
"""

import logging
from typing import Literal

from pydantic import BaseModel, Field

from app.agents import ripple
from app.agents.prompts import date_context
from app.integrations import llm
from app.services import dates

log = logging.getLogger("quorum.editor")


class Op(BaseModel):
    action: Literal["set_owner", "set_due", "set_title", "drop_task", "set_statement", "drop_decision"]
    ref: str = Field(description="Label of the item: T1, T2… for tasks, D1, D2… for decisions")
    value: str | None = Field(description="New owner, due date phrase, title or statement; null for drop actions")


class EditOut(BaseModel):
    ops: list[Op]


SYSTEM = """You turn one spoken instruction into edits on a pending meeting review.
Items are labelled T1, T2… (tasks) and D1, D2… (decisions). Allowed actions:
set_owner (value = person), set_due (value = the date as spoken, e.g. "the 18th" or "2026-11-18"),
set_title, drop_task, set_statement, drop_decision.
Only do what was asked; "approve" or "looks good" means no edits. Match items by owner, title words or topic."""


def _labels(state: dict):
    return ({f"T{i + 1}": t for i, t in enumerate(state.get("tasks", []))},
            {f"D{i + 1}": d for i, d in enumerate(state.get("decisions", []))})


def build_messages(state: dict, instruction: str):
    t_map, d_map = _labels(state)
    lines = ["TASKS:"] + [f"  {k}: {t['owner'] or 'nobody'} · \"{t['title']}\" · due {t['due_date'] or 'none'}" for k, t in t_map.items()]
    lines += ["DECISIONS:"] + [f"  {k}: [{d['topic_key']}] \"{d['statement']}\"" for k, d in d_map.items()]
    lines += ["", f"INSTRUCTION: {instruction}"]
    return [("system", SYSTEM + "\n\n" + date_context(state["meeting"]["date"])), ("user", "\n".join(lines))]


def apply(state: dict, out: EditOut, instruction: str) -> dict:
    t_map, d_map = _labels(state)
    tasks, decisions = list(state.get("tasks", [])), list(state.get("decisions", []))
    questions, conflicts = list(state.get("questions", [])), list(state.get("conflicts", []))
    people = {t["owner"] for t in tasks if t["owner"]} | {state["meeting"]["speaker"]}
    changes: list[str] = []
    for op in out.ops:
        ref = op.ref.strip().upper()
        if ref in t_map:
            t = next((x for x in tasks if x["id"] == t_map[ref]["id"]), None)
            if t is None:
                continue
            if op.action == "drop_task":
                tasks.remove(t)
                questions = [q for q in questions if q["item_id"] != t["id"]]
                changes.append(f"Dropped task “{t['title']}”")
            elif op.action == "set_owner" and op.value:
                owner = next((p for p in people if p.lower() == op.value.strip().lower()), op.value.strip())
                changes.append(f"“{t['title']}” owner: {t['owner'] or 'nobody'} → {owner}")
                t["owner"] = owner
                questions = [q for q in questions if not (q["item_id"] == t["id"] and q["field"] == "owner")]
            elif op.action == "set_due" and op.value:
                due = dates.resolve(op.value, state["meeting"]["date"])
                if due is None:
                    log.info("[editor] could not resolve date %r", op.value)
                    continue
                changes.append(f"“{t['title']}” due: {t['due_date'] or 'none'} → {due.isoformat()}")
                t["due_date"], t["raw_due_phrase"] = due.isoformat(), op.value
                questions = [q for q in questions if not (q["item_id"] == t["id"] and q["field"] == "due_date")]
            elif op.action == "set_title" and op.value:
                changes.append(f"Renamed “{t['title']}” → “{op.value.strip()}”")
                t["title"] = op.value.strip()
        elif ref in d_map:
            d = next((x for x in decisions if x["id"] == d_map[ref]["id"]), None)
            if d is None:
                continue
            if op.action == "drop_decision":
                decisions.remove(d)
                conflicts = [c for c in conflicts if c["new_item_id"] != d["id"]]
                changes.append(f"Dropped decision “{d['statement']}”")
            elif op.action == "set_statement" and op.value:
                changes.append(f"Decision reworded: “{d['statement']}” → “{op.value.strip()}”")
                d["statement"] = op.value.strip()
    if not changes:
        changes = [f"No edits matched: “{instruction}”"]
    edited = {**state, "tasks": tasks, "decisions": decisions, "questions": questions, "conflicts": conflicts}
    rebuilt = ripple.build(edited)
    return {"tasks": tasks, "decisions": decisions, "questions": questions, "conflicts": conflicts,
            "ripples": rebuilt["ripples"], "heads_up": rebuilt["heads_up"], "changes": changes}


async def run(state: dict) -> dict:
    instruction = ((state.get("review_action") or {}).get("instruction") or "").strip()
    out = await llm.structured(NODE, "strong", EditOut, build_messages(state, instruction))
    return apply(state, out, instruction)


def describe(update: dict) -> str:
    n = len(update.get("changes", []))
    return f"Applied {n} edit{'s' * (n != 1)}"


# Flipped to True when the real node lands; the golden test enables its checks on this flag.
IMPLEMENTED = True
NODE = "review_editor"

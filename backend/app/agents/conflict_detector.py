"""conflict_detector agent (Phase 5).

Two layers.
1. LLM (strong tier, ONE call for the whole debrief): for each new decision and its retrieved past
   decisions, judge reversal / contradiction / none, severity by fixed rules, explanation, suggested
   resolution, and which existing open tasks the old decision shaped (affected tasks).
2. Deterministic Python checks:
   - deadline collision (medium): a task due after the newest launch/release date decision, or a new task
     due before the meeting date (late at birth);
   - owner overload (low): 3+ tasks for one owner on one day, counting new + existing open tasks,
     flagged only when a new task is involved.
Prompt items use short labels (N1, P1, T1), never generated IDs, so replay recordings stay stable.

Model tier: strong
Reads state:  decisions, tasks, related, meeting (+ memory: open tasks, active decisions)
Writes state: conflicts: Conflict[]
"""

import logging
from collections import defaultdict
from typing import Literal

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app import views
from app.db import get_engine
from app.ids import new_id
from app.integrations import llm
from app.models import Decision, Task
from app.services import dates

log = logging.getLogger("quorum.conflicts")

LAUNCH_WORDS = ("launch", "release", "ship", "go_live", "golive")


class Judgement(BaseModel):
    new_ref: str = Field(description="Label of the new decision, e.g. N1")
    past_ref: str = Field(description="Label of the past decision, e.g. P2")
    verdict: Literal["reversal", "contradiction", "none"]
    severity: Literal["high", "medium", "low"]
    explanation: str = Field(description="One or two sentences a PM understands at a glance")
    suggested_resolution: str = Field(description="One concrete next step")
    affected_task_refs: list[str] = Field(description="Labels (T1...) of existing open tasks the past decision shaped")


class ConflictOut(BaseModel):
    judgements: list[Judgement]


SYSTEM = """You check new meeting decisions against the team's past decisions and flag conflicts.

For EVERY pair (new decision, past decision) listed, return one judgement:
- "reversal": the new decision changes the value the past decision set on the same subject: a different scope,
  platform, vendor, owner, OR DATE. A moved date is always a reversal, even by a few days (past "launch 20 Nov"
  vs new "launch 28 Nov" = reversal, severity medium). Size goes into severity, never into "none".
- "contradiction": the two can't both hold, but it isn't a straight replacement (different subjects that clash).
- "none": the new decision restates the past one, is compatible with it, or is about something unrelated.

Severity rules (apply exactly):
- high: reverses scope, platform, vendor or provider, or invalidates work already underway.
- medium: moves a date or deadline, or amends a decision without overturning it.
- low: minor clarification. Use low for "none" verdicts.

affected_task_refs: the existing open tasks (T labels) whose work was shaped by the PAST decision and now needs a
second look because of the change. Only include tasks clearly affected; empty list if none. Use [] for "none".
explanation: name what changed and who said it, in one or two plain sentences.
suggested_resolution: one concrete next step (who should do what)."""


def _open_tasks(project: str) -> list[Task]:
    with Session(get_engine()) as s:
        return s.exec(select(Task).where(Task.project == project, Task.status == "todo")
                      .order_by(Task.due_date, Task.id)).all()


def build_messages(new_decisions: list[dict], related: dict, open_tasks: list[Task], meeting: dict):
    n_labels = {d["id"]: f"N{i + 1}" for i, d in enumerate(new_decisions)}
    past: dict[str, dict] = {}
    for d in new_decisions:
        for hit in related.get(d["id"], []):
            past.setdefault(hit["decision"]["id"], hit["decision"])
    p_labels = {pid: f"P{i + 1}" for i, pid in enumerate(past)}
    t_labels = {t.id: f"T{i + 1}" for i, t in enumerate(open_tasks)}

    lines = [f"Meeting: {meeting['title']} on {meeting['date']}, reported by {meeting['speaker']}.", "", "PAST DECISIONS:"]
    for pid, p in past.items():
        lines.append(f"  {p_labels[pid]} [{p['topic_key']}] \"{p['statement']}\" (by {p['made_by']}, {p['date']})")
    lines += ["", "NEW DECISIONS:"]
    for d in new_decisions:
        lines.append(f"  {n_labels[d['id']]} [{d['topic_key']}] \"{d['statement']}\" (by {d['made_by']})")
    lines += ["", "PAIRS TO JUDGE:"]
    for d in new_decisions:
        for hit in related.get(d["id"], []):
            lines.append(f"  {n_labels[d['id']]} vs {p_labels[hit['decision']['id']]}")
    lines += ["", "EXISTING OPEN TASKS:"]
    lines += [f"  {t_labels[t.id]} {t.owner}: \"{t.title}\" due {t.due_date or 'no date'}" for t in open_tasks] or ["  (none)"]
    msgs = [("system", SYSTEM), ("user", "\n".join(lines))]
    return msgs, n_labels, p_labels, t_labels, past


def semantic_conflicts(out: ConflictOut, *, new_decisions, related, open_tasks, n_labels, p_labels, t_labels, past):
    by_n = {v: k for k, v in n_labels.items()}
    by_p = {v: k for k, v in p_labels.items()}
    by_t = {v: t for t in open_tasks for k, v in t_labels.items() if k == t.id}
    allowed = {(d["id"], h["decision"]["id"]) for d in new_decisions for h in related.get(d["id"], [])}
    conflicts, seen = [], set()
    for j in out.judgements:
        nid, pid = by_n.get(j.new_ref.strip()), by_p.get(j.past_ref.strip())
        if j.verdict == "none" or nid is None or pid is None or (nid, pid) not in allowed or (nid, pid) in seen:
            continue
        seen.add((nid, pid))
        affected = [views.task(by_t[r.strip()]).model_dump() for r in j.affected_task_refs if r.strip() in by_t]
        conflicts.append({
            "id": new_id("cfl"),
            "type": j.verdict,
            "severity": j.severity,
            "new_item_id": nid,
            "old_decision": past[pid],
            "affected_tasks": affected,
            "explanation": j.explanation.strip(),
            "suggested_resolution": j.suggested_resolution.strip(),
        })
    return conflicts


def _launch_date(new_decisions: list[dict], project: str, meeting_date: str):
    """Newest launch/release decision with a parseable date: this debrief's first, else memory's."""
    def is_launch(topic: str) -> bool:
        return any(w in topic for w in LAUNCH_WORDS)

    for d in new_decisions:
        if is_launch(d["topic_key"]) and (when := dates.resolve(d["statement"], meeting_date)):
            return when, d
    with Session(get_engine()) as s:
        active = s.exec(select(Decision).where(Decision.project == project, Decision.status == "active")
                        .order_by(Decision.date.desc())).all()
    for d in active:
        if is_launch(d.topic_key) and (when := dates.resolve(d.statement, d.date)):
            return when, views.decision(d).model_dump()
    return None, None


def deterministic_conflicts(new_tasks: list[dict], new_decisions: list[dict], open_tasks: list[Task], meeting: dict):
    conflicts = []
    existing = [views.task(t).model_dump() for t in open_tasks]
    launch, launch_decision = _launch_date(new_decisions, meeting["project"], meeting["date"])

    if launch is not None:
        for t in new_tasks + existing:
            if t["due_date"] and t["due_date"] > launch.isoformat():
                conflicts.append({
                    "id": new_id("cfl"), "type": "deadline_collision", "severity": "medium",
                    "new_item_id": t["id"], "old_decision": launch_decision, "affected_tasks": [t],
                    "explanation": f"“{t['title']}” ({t['owner']}) is due {t['due_date']}, after the launch on {launch.isoformat()}.",
                    "suggested_resolution": f"Pull it in before {launch.isoformat()} or confirm it's post-launch work.",
                })
    for t in new_tasks:
        if t["due_date"] and t["due_date"] < meeting["date"]:
            conflicts.append({
                "id": new_id("cfl"), "type": "deadline_collision", "severity": "medium",
                "new_item_id": t["id"], "old_decision": None, "affected_tasks": [t],
                "explanation": f"“{t['title']}” is due {t['due_date']}, before this meeting ({meeting['date']}). It's late on arrival.",
                "suggested_resolution": f"Agree a realistic new date with {t['owner'] or 'the owner'}.",
            })

    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for t in new_tasks + existing:
        if t["owner"] and t["due_date"]:
            groups[(t["owner"], t["due_date"])].append(t)
    new_ids = {t["id"] for t in new_tasks}
    for (owner, day), tasks in sorted(groups.items()):
        fresh = [t for t in tasks if t["id"] in new_ids]
        if len(tasks) >= 3 and fresh:
            conflicts.append({
                "id": new_id("cfl"), "type": "overload", "severity": "low",
                "new_item_id": fresh[0]["id"], "old_decision": None, "affected_tasks": tasks,
                "explanation": f"{owner} has {len(tasks)} tasks due on {day}.",
                "suggested_resolution": f"Move one of {owner}'s {day} tasks or hand it to someone else.",
            })
    return conflicts


async def run(state: dict) -> dict:
    meeting = state["meeting"]
    new_decisions, related = state.get("decisions", []), state.get("related", {})
    open_tasks = _open_tasks(meeting["project"])
    conflicts: list[dict] = []
    if any(related.get(d["id"]) for d in new_decisions):
        msgs, n_labels, p_labels, t_labels, past = build_messages(new_decisions, related, open_tasks, meeting)
        out = await llm.structured(NODE, "strong", ConflictOut, msgs)
        conflicts += semantic_conflicts(out, new_decisions=new_decisions, related=related, open_tasks=open_tasks,
                                        n_labels=n_labels, p_labels=p_labels, t_labels=t_labels, past=past)
    conflicts += deterministic_conflicts(state.get("tasks", []), new_decisions, open_tasks, meeting)
    return {"conflicts": conflicts}


def describe(update: dict) -> str:
    conflicts = update.get("conflicts", [])
    if not conflicts:
        return "No conflicts with past decisions"
    by_sev = defaultdict(int)
    for c in conflicts:
        by_sev[c["severity"]] += 1
    detail = ", ".join(f"{by_sev[s]} {s}" for s in ("high", "medium", "low") if by_sev[s])
    return f"Found {len(conflicts)} conflict{'s' * (len(conflicts) != 1)} ({detail})"


# Flipped to True when the real node lands; the golden test enables its checks on this flag.
IMPLEMENTED = True
NODE = "conflict_detector"

"""Read-side views built from stored memory: time machine, flip-flop radar, brief, digest, ask.

Everything here is deterministic (no model call), so the pages work offline and replay never needs a recording.
"""

import re
from datetime import date, datetime, timedelta

from sqlmodel import Session, select

from app import models, views
from app.services import clock

LABELS = {"platform_scope": "Platform scope", "launch_date": "Launch date", "payments_provider": "Payments provider"}
FLIP_TYPES = ("reversal", "contradiction")


def label(topic_key: str) -> str:
    return LABELS.get(topic_key, topic_key.replace("_", " ").capitalize())


def _decisions(s: Session, project: str) -> list[models.Decision]:
    return s.exec(select(models.Decision).where(models.Decision.project == project)
                  .order_by(models.Decision.date, models.Decision.id)).all()


def _meeting_titles(s: Session) -> dict[str, str]:
    return {m.id: m.title for m in s.exec(select(models.Meeting)).all()}


def _flipped_ids(s: Session, project: str) -> set[str]:
    rows = s.exec(select(models.Conflict).where(models.Conflict.project == project,
                                                models.Conflict.resolution == "accept_new")).all()
    return {c.new_item_id for c in rows if c.type in FLIP_TYPES}


# ---- Time machine ----

def as_of(s: Session, project: str, on: str) -> dict:
    decisions = _decisions(s, project)
    made = [d for d in decisions if d.date <= on]
    shown = []
    for d in made:
        view = views.decision(d).model_dump()
        if d.superseded_by and (d.superseded_on or "9999") <= on:
            view["status"] = "superseded"
        else:
            view["status"], view["superseded_by"] = "active", None
        shown.append(view)
    then = {}
    for d in shown:
        if d["status"] == "active":
            then[d["topic_key"]] = d
    now = {d.topic_key: views.decision(d).model_dump() for d in decisions if d.status == "active"}
    changed = [{"topic_key": k, "then": then[k], "now": now[k]} for k in then if k in now and now[k]["id"] != then[k]["id"]]
    return {"project": project, "date": on, "decisions": shown, "changed_since": changed}


def timeline(s: Session, project: str, topic_key: str | None) -> dict:
    titles, flipped = _meeting_titles(s), _flipped_ids(s, project)
    topics: dict[str, list[models.Decision]] = {}
    for d in _decisions(s, project):
        if topic_key in (None, d.topic_key):
            topics.setdefault(d.topic_key, []).append(d)
    out = []
    for key, items in topics.items():
        events = [{"decision": views.decision(d).model_dump(), "meeting_id": d.meeting_id,
                   "meeting_title": titles.get(d.meeting_id, "Meeting"), "date": d.date, "made_by": d.made_by,
                   "quote": d.source_quote or d.statement,
                   "change": "created" if i == 0 else ("reversed" if d.id in flipped else "amended")}
                  for i, d in enumerate(items)]
        out.append({"topic_key": key, "label": label(key), "events": events})
    return {"topics": out}


# ---- Flip-flop radar ----

def radar(s: Session, project: str) -> dict:
    today = clock.today(s)
    flipped = _flipped_ids(s, project)
    by_topic: dict[str, list[models.Decision]] = {}
    for d in _decisions(s, project):
        by_topic.setdefault(d.topic_key, []).append(d)
    topics = []
    for key, items in by_topic.items():
        flips = sum(1 for d in items if d.id in flipped)
        last = items[-1].date
        recent = (today - date.fromisoformat(last)).days <= 14
        risk = "high" if flips >= 2 else "medium" if flips == 1 and recent else "low"
        note = (f"Changed {flips}× since {items[0].date}; last on {last}." if flips else "Stable since it was decided.")
        topics.append({"topic_key": key, "label": label(key), "versions": len(items), "flips": flips,
                       "last_changed": last, "churn": round(min(1.0, flips / 3), 2), "risk": risk,
                       "statements": [{"decision_id": d.id, "date": d.date, "statement": d.statement, "made_by": d.made_by}
                                      for d in items], "note": note})
    topics.sort(key=lambda t: (-t["churn"], -date.fromisoformat(t["last_changed"]).toordinal()))
    return {"project": project, "topics": topics}


# ---- Conflicts as wire objects ----

def conflict_view(s: Session, c: models.Conflict) -> dict:
    old = s.get(models.Decision, c.old_decision_id) if c.old_decision_id else None
    tasks = [s.get(models.Task, i) for i in c.affected_task_ids]
    return {"id": c.id, "type": c.type, "severity": c.severity, "new_item_id": c.new_item_id,
            "old_decision": views.decision(old).model_dump() if old else None,
            "affected_tasks": [views.task(t).model_dump() for t in tasks if t],
            "explanation": c.explanation, "suggested_resolution": c.suggested_resolution}


# ---- Walk-in brief ----

def _open_tasks(s: Session, project: str) -> list[models.Task]:
    return s.exec(select(models.Task).where(models.Task.project == project, models.Task.status == "todo")).all()


def brief(s: Session, project: str) -> dict:
    now, today = clock.now(s), clock.today(s)
    tasks = _open_tasks(s, project)
    overdue = sorted((t for t in tasks if t.due_date and t.due_date < today.isoformat()), key=lambda t: t.due_date)
    soon = sorted((t for t in tasks if t.due_date and today.isoformat() <= t.due_date <= (today + timedelta(days=3)).isoformat()),
                  key=lambda t: t.due_date)
    open_task_ids = {t.id for t in tasks}
    conflicts = [c for c in s.exec(select(models.Conflict).where(models.Conflict.project == project)).all()
                 if c.resolution == "accept_new" and open_task_ids & set(c.affected_task_ids)]
    hot = [t for t in radar(s, project)["topics"] if t["risk"] != "low"][:3]

    def when(d: str) -> str:
        n = (date.fromisoformat(d) - today).days
        return "today" if n == 0 else "tomorrow" if n == 1 else f"in {n} days" if n > 1 else f"{-n} day{'s' * (-n != 1)} ago"

    agenda = [f"Re-confirm {t['label'].lower()}: it changed on {t['last_changed']}" for t in hot]
    agenda += [f"Unblock {t.title} ({t.owner or 'no owner'}, was due {t.due_date})" for t in overdue]
    agenda += [f"Check in on {t.title} ({t.owner or 'no owner'}, due {when(t.due_date)})" for t in soon]
    agenda.append("Capture any new decisions out loud before leaving the room")
    parts = []
    if hot:
        parts.append(f"{hot[0]['label']} changed on {hot[0]['last_changed']}")
    if overdue:
        parts.append(f"{len(overdue)} task{'s' * (len(overdue) != 1)} overdue")
    if soon:
        parts.append(f"{soon[0].title} is due {when(soon[0].due_date)}")
    headline = "; ".join(parts) + "." if parts else "Nothing is on fire. A good day for a short meeting."
    script = "\n\n".join([f"**Before you walk in ({now:%a %-d %b}).** {headline}"]
                         + [f"- {a}" for a in agenda[:5]])
    return {"project": project, "as_of": clock.fmt(now), "headline": headline, "script_md": script, "agenda": agenda,
            "open_conflicts": [conflict_view(s, c) for c in conflicts], "overdue": [views.task(t).model_dump() for t in overdue],
            "due_soon": [views.task(t).model_dump() for t in soon], "hot_topics": hot}


# ---- Weekly digest ----

def digest(s: Session, person: str, week_of: str | None) -> dict:
    today = clock.today(s)
    monday = date.fromisoformat(week_of) if week_of else today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    mine = s.exec(select(models.Task).where(models.Task.owner == person, models.Task.status != "pending")).all()
    done = [t for t in mine if t.status == "done"]
    horizon = (sunday + timedelta(days=7)).isoformat()  # this week plus the next, so a Saturday digest still looks ahead
    due = [t for t in mine if t.status == "todo" and t.due_date and today.isoformat() <= t.due_date <= horizon]
    late = [t for t in mine if t.status == "todo" and t.due_date and t.due_date < today.isoformat()]
    decisions = [d for d in s.exec(select(models.Decision).where(models.Decision.made_by == person)).all()
                 if monday.isoformat() <= d.date <= sunday.isoformat()]
    my_ids = {t.id for t in mine}
    conflicts = [c for c in s.exec(select(models.Conflict)).all()
                 if my_ids & set(c.affected_task_ids) or c.new_item_id in {d.id for d in decisions}]
    lines = [f"## {person}, your week of {monday:%-d %b}", ""]
    lines.append(f"**{len(late)} overdue, {len(due)} coming up, {len(done)} done.**"
                 if (late or due or done) else "Nothing assigned to you this week. Enjoy the quiet.")
    if late:
        lines += ["", "**Fix first:**"] + [f"- {t.title} (was due {t.due_date})" for t in late]
    if due:
        lines += ["", "**Coming up:**"] + [f"- {t.title}, due {t.due_date}" for t in sorted(due, key=lambda t: t.due_date)]
    if decisions:
        lines += ["", "**You decided:**"] + [f"- {d.statement}" for d in decisions]
    if conflicts:
        lines += ["", f"**Heads up:** {len(conflicts)} change{'s' * (len(conflicts) != 1)} touched your work: "
                  + "; ".join(c.explanation.rstrip('.') for c in conflicts[:2]) + "."]
    return {"person": person, "week_of": monday.isoformat(), "summary_md": "\n".join(lines),
            "done": [views.task(t).model_dump() for t in done], "due": [views.task(t).model_dump() for t in due],
            "overdue": [views.task(t).model_dump() for t in late],
            "decisions": [views.decision(d).model_dump() for d in decisions],
            "conflicts": [conflict_view(s, c) for c in conflicts]}


# ---- Ask your meetings ----

_STOP = set("a an and are as at be by did do does for from had has have how i if in is it its me my of on or our so than "
            "that the their there they this to was we were what when where which who why will with you your".split())


def _stem(word: str) -> str:
    """Crude stem so "launching", "launched" and "launch" match; "moved" and "move" meet at "mov"."""
    for suffix in ("ing", "ed", "es", "s", "ly"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            word = word[: -len(suffix)]
            break
    return word[:-1] if word.endswith("e") and len(word) > 3 else word


def _words(text: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOP and len(w) > 1}


def ask(s: Session, project: str, question: str) -> dict:
    q = _words(question)
    titles = _meeting_titles(s)
    scored = []
    for d in _decisions(s, project):
        text = f"{d.topic_key.replace('_', ' ')} {d.statement} {d.rationale or ''} {d.source_quote or ''}"
        hits = len(q & _words(text))
        if hits:
            scored.append((hits + (0.5 if d.status == "active" else 0), d))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        return {"answer": "I couldn't find anything about that in your team's meetings yet.", "citations": []}
    top = [d for _, d in scored[:3]]
    cites, seen, parts = [], set(), []
    for d in top:
        if d.id in seen:
            continue
        seen.add(d.id)
        cites.append({"meeting_id": d.meeting_id, "meeting_title": titles.get(d.meeting_id, "Meeting"), "date": d.date,
                      "quote": d.source_quote or d.statement})
        if d.status == "superseded":
            newer = s.get(models.Decision, d.superseded_by) if d.superseded_by else None
            parts.append(f"On {d.date}, {d.made_by} had decided: “{d.statement}”."
                         + (f" That was replaced on {newer.date} when {newer.made_by} said: “{newer.statement}”."
                            + (f" The reason: {newer.rationale}" if newer.rationale else "") if newer else ""))
        else:
            parts.append(f"On {d.date}, {d.made_by} decided: “{d.statement}”." + (f" Reason: {d.rationale}" if d.rationale else ""))
    return {"answer": " ".join(parts), "citations": cites}


# ---- Reminders ----

def due_reminders(s: Session) -> list[models.Task]:
    """Open tasks due within 24h of the demo clock (or already late) that haven't been reminded yet."""
    now = clock.now(s).replace(tzinfo=None)
    out = []
    for t in s.exec(select(models.Task).where(models.Task.status == "todo", models.Task.reminder_sent == False)).all():  # noqa: E712
        if t.due_date and datetime.fromisoformat(f"{t.due_date}T23:59:59") <= now + timedelta(hours=24):
            out.append(t)
    return out


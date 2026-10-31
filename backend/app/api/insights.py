"""Read-side routes: time machine, radar, walk-in brief, digest, ask, reminders."""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db import get_session
from app.integrations import trackers
from app.schemas import AskRequest
from app.services import clock, insights

router = APIRouter(tags=["insights"])


@router.get("/decisions/as-of")
def decisions_as_of(project: str, date: str, session: Session = Depends(get_session)) -> dict:
    try:
        on = clock.parse(date).date().isoformat()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return insights.as_of(session, project, on)


@router.get("/decisions/timeline")
def decisions_timeline(project: str = "Pocket", topic_key: str | None = None, session: Session = Depends(get_session)) -> dict:
    return insights.timeline(session, project, topic_key)


@router.get("/radar")
def get_radar(project: str = "Pocket", session: Session = Depends(get_session)) -> dict:
    return insights.radar(session, project)


@router.get("/brief")
def get_brief(project: str = "Pocket", session: Session = Depends(get_session)) -> dict:
    return insights.brief(session, project)


@router.get("/digest/{person}")
def get_digest(person: str, week_of: str | None = None, session: Session = Depends(get_session)) -> dict:
    return insights.digest(session, person, week_of)


@router.post("/ask")
def ask(body: AskRequest, session: Session = Depends(get_session)) -> dict:
    if not body.question.strip():
        raise HTTPException(status_code=422, detail="question is empty")
    return insights.ask(session, body.project, body.question)


@router.post("/reminders/run")
async def run_reminders(session: Session = Depends(get_session)) -> dict:
    sent = []
    for task in insights.due_reminders(session):
        who = task.owner or "Someone"
        due = task.due_date
        channel = await trackers.send_chat(f"⏰ {who}: “{task.title}” is due {due}.")
        task.reminder_sent = True
        session.add(task)
        sent.append({"task_id": task.id, "owner": task.owner, "channel": channel})
    session.commit()
    return {"sent": sent}

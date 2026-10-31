from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app import views
from app.db import get_session
from app.models import Decision, Meeting
from app.schemas import Decision as DecisionOut

router = APIRouter(tags=["decisions"])


@router.get("/decisions", response_model=list[DecisionOut])
def list_decisions(
    project: str | None = None, include_superseded: bool = False, session: Session = Depends(get_session)
):
    q = select(Decision).order_by(Decision.date.desc(), Decision.topic_key)
    if project:
        q = q.where(Decision.project == project)
    if not include_superseded:
        q = q.where(Decision.status == "active")
    return [views.decision(d) for d in session.exec(q).all()]


@router.get("/decisions/graph")
def decision_graph(project: str | None = None, session: Session = Depends(get_session)) -> dict:
    q = select(Decision, Meeting.title).join(Meeting, Meeting.id == Decision.meeting_id).order_by(Decision.date)
    if project:
        q = q.where(Decision.project == project)
    rows = session.exec(q).all()
    nodes = [
        {"id": d.id, "label": d.statement, "status": d.status, "date": d.date, "meeting_title": title}
        for d, title in rows
    ]
    edges = [
        {"source": d.superseded_by, "target": d.id, "kind": "supersedes"} for d, _ in rows if d.superseded_by
    ]
    return {"nodes": nodes, "edges": edges}

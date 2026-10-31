from fastapi import APIRouter, Depends
from sqlmodel import Session, func, select

from app import views
from app.db import get_session
from app.models import Decision, Meeting, Project, Task
from app.schemas import Meeting as MeetingOut
from app.services import clock

router = APIRouter(tags=["directory"])


@router.get("/projects")
def list_projects(session: Session = Depends(get_session)) -> list[dict]:
    out = []
    for p in session.exec(select(Project).order_by(Project.name)).all():
        count, last = session.exec(
            select(func.count(Meeting.id), func.max(Meeting.date)).where(Meeting.project == p.name)
        ).one()
        out.append({"name": p.name, "meeting_count": count, "last_meeting": last})
    return out


@router.get("/meetings", response_model=list[MeetingOut])
def list_meetings(project: str | None = None, session: Session = Depends(get_session)):
    q = select(Meeting).order_by(Meeting.date.desc(), Meeting.created_at.desc())
    if project:
        q = q.where(Meeting.project == project)
    return [views.meeting(m) for m in session.exec(q).all()]


@router.get("/people")
def list_people(session: Session = Depends(get_session)) -> list[dict]:
    """Everyone who owns a task, made a decision, or spoke a meeting. Overdue is relative to the demo clock."""
    today = clock.today(session).isoformat()
    names = set(session.exec(select(Task.owner)).all())
    names |= set(session.exec(select(Decision.made_by)).all())
    names |= set(session.exec(select(Meeting.speaker)).all())
    open_tasks = session.exec(select(Task).where(Task.status == "todo")).all()
    return [
        {
            "name": n,
            "open_tasks": sum(t.owner == n for t in open_tasks),
            "overdue": sum(t.owner == n and t.due_date is not None and t.due_date < today for t in open_tasks),
        }
        for n in sorted(names)
    ]

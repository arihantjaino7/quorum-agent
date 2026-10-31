from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app import views
from app.db import get_session
from app.models import Task
from app.schemas import Task as TaskOut
from app.schemas import TaskPatch

router = APIRouter(tags=["tasks"])


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(project: str | None = None, owner: str | None = None, session: Session = Depends(get_session)):
    q = select(Task).where(Task.status != "pending")
    if project:
        q = q.where(Task.project == project)
    if owner:
        q = q.where(Task.owner == owner)
    rows = session.exec(q).all()
    # Due date ascending, undated last.
    rows.sort(key=lambda t: (t.due_date is None, t.due_date or "", t.owner))
    return [views.task(t) for t in rows]


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def patch_task(task_id: str, body: TaskPatch, session: Session = Depends(get_session)):
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"task {task_id} not found")
    if task.status == "pending":
        raise HTTPException(status_code=409, detail=f"task {task_id} is awaiting approval")
    task.status = body.status
    session.add(task)
    session.commit()
    session.refresh(task)
    return views.task(task)

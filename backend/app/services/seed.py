"""Demo seed: loads meeting 1 (already approved) from seed/meeting1.json. No LLM involved."""

import json

from sqlmodel import Session, select

from app.config import BACKEND_DIR
from app.models import Decision, Meeting, Project, Task

SEED_DIR = BACKEND_DIR / "seed"


def load_meeting1(session: Session) -> None:
    data = json.loads((SEED_DIR / "meeting1.json").read_text())
    raw = (SEED_DIR / "meeting1.txt").read_text()
    project, m = data["project"], data["meeting"]

    session.add(Project(name=project))
    session.add(Meeting(project=project, raw_text=raw, clean_text=raw, **m))
    for d in data["decisions"]:
        session.add(Decision(project=project, meeting_id=m["id"], date=m["date"], status="active", **d))
    for t in data["tasks"]:
        session.add(Task(project=project, meeting_id=m["id"], status="todo", **t))
    session.commit()


def seed_if_empty(session: Session) -> bool:
    """First start on an empty database: load meeting 1 so the demo has memory to check against."""
    if session.exec(select(Project)).first() is not None:
        return False
    load_meeting1(session)
    return True

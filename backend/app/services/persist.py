"""Idempotent writes shared by the executor and the memory writer (a retry may run either twice)."""

from sqlmodel import Session

from app import models


def ensure_meeting(s: Session, state: dict) -> None:
    m = state["meeting"]
    if s.get(models.Project, m["project"]) is None:
        s.add(models.Project(name=m["project"]))
        s.flush()
    if s.get(models.Meeting, m["id"]) is None:
        s.add(models.Meeting(id=m["id"], project=m["project"], title=m["title"], date=m["date"], speaker=m["speaker"],
                             source_type=m["source_type"], raw_text=state.get("raw_text", ""),
                             clean_text=state.get("clean_text", "")))
        s.commit()

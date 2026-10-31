from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db import get_session, reset_db
from app.services import clock, seed

router = APIRouter(tags=["demo"])


@router.post("/demo/reset")
def demo_reset(session: Session = Depends(get_session)) -> dict:
    """Wipe the DB, reseed meeting 1 (approved), and reset the demo clock."""
    session.close()
    reset_db()
    # Phase 2: also clear LangGraph checkpoints and the in-memory run registry here.
    seed.load_meeting1(session)
    clock.reset(session)
    return {"ok": True}

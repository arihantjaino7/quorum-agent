from fastapi import APIRouter, Depends
from sqlmodel import Session

from app import pipeline
from app.db import get_session, reset_db
from app.services import clock, seed

router = APIRouter(tags=["demo"])


@router.post("/demo/reset")
async def demo_reset(session: Session = Depends(get_session)) -> dict:
    """Cancel runs, wipe checkpoints + DB, reseed meeting 1 (approved), and reset the demo clock."""
    await pipeline.reset()
    session.close()
    reset_db()
    seed.load_meeting1(session)
    clock.reset(session)
    return {"ok": True}

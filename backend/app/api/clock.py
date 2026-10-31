from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db import get_session
from app.schemas import ClockSet
from app.services import clock

router = APIRouter(tags=["clock"])


@router.get("/clock")
def get_clock(session: Session = Depends(get_session)) -> dict:
    return {"now": clock.fmt(clock.now(session))}


@router.post("/clock")
def set_clock(body: ClockSet, session: Session = Depends(get_session)) -> dict:
    try:
        dt = clock.set_now(session, body.now)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return {"now": clock.fmt(dt)}

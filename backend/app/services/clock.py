"""Demo clock, stored in the Setting table. It is **frozen**: it only moves when set.

Use ``now()`` / ``today()`` everywhere instead of datetime.now(), so the demo can time-travel.
"""

from datetime import date, datetime

from sqlmodel import Session

from app.config import get_settings
from app.models import Setting

KEY = "demo_clock"


def parse(value: str) -> datetime:
    """Accepts ISO date or datetime; drops timezone and sub-second precision."""
    try:
        dt = datetime.fromisoformat(value.strip())
    except (ValueError, AttributeError) as e:
        raise ValueError(f"not an ISO date/time: {value!r}") from e
    return dt.replace(tzinfo=None, microsecond=0)


def fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def now(session: Session) -> datetime:
    row = session.get(Setting, KEY)
    return parse(row.value if row else get_settings().demo_clock_start)


def today(session: Session) -> date:
    return now(session).date()


def set_now(session: Session, value: str) -> datetime:
    dt = parse(value)
    row = session.get(Setting, KEY) or Setting(key=KEY, value="")
    row.value = fmt(dt)
    session.add(row)
    session.commit()
    return dt


def reset(session: Session) -> datetime:
    return set_now(session, get_settings().demo_clock_start)

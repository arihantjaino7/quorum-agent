"""Run event registry: thread_id → buffered AgentEvents + live subscribers (for SSE).

Late subscribers get every event emitted so far, then live events, until the channel closes.
A channel closes on a terminal event: ``error``, or ``agent_end`` from agent ``pipeline``
(approved / rejected). Retry reopens it and drops the trailing error, so a fresh subscriber
sees a clean history.
"""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from sqlmodel import Session

from app.db import get_engine
from app.schemas import AgentEvent
from app.services import clock


@dataclass
class Channel:
    events: list[AgentEvent] = field(default_factory=list)
    subscribers: set[asyncio.Queue] = field(default_factory=set)
    closed: bool = False


_channels: dict[str, Channel] = {}


def open_channel(thread_id: str) -> Channel:
    return _channels.setdefault(thread_id, Channel())


def has_channel(thread_id: str) -> bool:
    return thread_id in _channels


def emit(thread_id: str, type: str, agent: str, message: str, payload=None, run_ms: int | None = None) -> AgentEvent:
    with Session(get_engine()) as s:
        ts = clock.fmt(clock.now(s))
    event = AgentEvent(type=type, agent=agent, message=message, payload=payload, ts=ts, run_ms=run_ms)
    ch = open_channel(thread_id)
    ch.events.append(event)
    for q in ch.subscribers:
        q.put_nowait(event)
    return event


def close(thread_id: str) -> None:
    ch = open_channel(thread_id)
    ch.closed = True
    for q in ch.subscribers:
        q.put_nowait(None)


def reopen_for_retry(thread_id: str) -> None:
    ch = open_channel(thread_id)
    while ch.events and ch.events[-1].type == "error":
        ch.events.pop()
    ch.closed = False


async def subscribe(thread_id: str) -> AsyncIterator[AgentEvent]:
    ch = open_channel(thread_id)
    q: asyncio.Queue = asyncio.Queue()
    backlog = list(ch.events)
    closed = ch.closed
    ch.subscribers.add(q)
    try:
        for e in backlog:
            yield e
        if closed:
            return
        while (e := await q.get()) is not None:
            yield e
    finally:
        ch.subscribers.discard(q)


def clear() -> None:
    for tid in list(_channels):
        close(tid)
    _channels.clear()

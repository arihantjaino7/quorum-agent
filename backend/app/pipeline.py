"""Pipeline driver: owns the compiled graph + checkpointer and moves runs between states.

Run.status: running → review → approving → approved
                            ↘ rejected
            any step failing → error (retry resumes from the failed agent)

Only the first approve/reject wins (conditional status update); later ones get 409.
"""

import asyncio
import logging

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from sqlalchemy import update
from sqlmodel import Session

from app import graph as graph_mod
from app.config import get_settings
from app.db import get_engine
from app.models import Run
from app.schemas import ReviewPayload
from app.services import runs

log = logging.getLogger("quorum.pipeline")

EMPTY_RESULT = {
    "created_tasks": [],
    "superseded_ids": [],
    "updated_tasks": [],
    "cancelled_task_ids": [],
    "heads_up_sent": [],
}


class RunConflict(Exception):
    """The run is not in a state that allows this action (→ HTTP 409)."""


class _Engine:
    conn: aiosqlite.Connection | None = None
    saver: AsyncSqliteSaver | None = None
    graph = None
    tasks: set[asyncio.Task] = set()


_e = _Engine()


async def startup() -> None:
    _e.conn = await aiosqlite.connect(get_settings().checkpoint_db)
    _e.saver = AsyncSqliteSaver(_e.conn)
    await _e.saver.setup()
    _e.graph = graph_mod.build(_e.saver)
    # Runs interrupted by a restart (e.g. uvicorn --reload) become retryable instead of stuck.
    with Session(get_engine()) as s:
        s.exec(update(Run).where(Run.status.in_(["running", "approving"])).values(status="error"))
        s.commit()


async def shutdown() -> None:
    for t in list(_e.tasks):
        t.cancel()
    if _e.conn is not None:
        await _e.conn.close()
        _e.conn = None


async def reset() -> None:
    """Cancel in-flight runs, drop all checkpoints and event channels (called by /api/demo/reset)."""
    for t in list(_e.tasks):
        t.cancel()
    _e.tasks.clear()
    runs.clear()
    if _e.conn is not None:
        await _e.conn.execute("DELETE FROM checkpoints")
        await _e.conn.execute("DELETE FROM writes")
        await _e.conn.commit()


def _cfg(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _status(thread_id: str) -> str | None:
    with Session(get_engine()) as s:
        run = s.get(Run, thread_id)
        return run.status if run else None


def _set_status(thread_id: str, status: str, *, only_if: str | None = None) -> bool:
    with Session(get_engine()) as s:
        q = update(Run).where(Run.thread_id == thread_id)
        if only_if is not None:
            q = q.where(Run.status == only_if)
        changed = s.exec(q.values(status=status)).rowcount == 1
        s.commit()
        return changed


def review_payload(values: dict) -> ReviewPayload:
    keys = ["thread_id", "meeting", "raw_text", "clean_text", "corrections", "decisions", "tasks",
            "conflicts", "questions", "ripples", "heads_up"]
    return ReviewPayload.model_validate({k: values[k] for k in keys if k in values})


async def get_review(thread_id: str) -> ReviewPayload:
    status = _status(thread_id)
    if status is None:
        raise KeyError(thread_id)
    if status != "review":
        raise RunConflict(f"run is {status}, not awaiting review")
    state = await _e.graph.aget_state(_cfg(thread_id))
    return review_payload(state.values)


async def _drive(thread_id: str, graph_input) -> dict | None:
    """Advance the graph, then publish whatever state it stopped in. Returns the final state values."""
    try:
        await _e.graph.ainvoke(graph_input, _cfg(thread_id))
    except asyncio.CancelledError:
        raise
    except Exception as e:
        _set_status(thread_id, "error")
        agent = e.agent if isinstance(e, graph_mod.AgentFailed) else None
        log.error("run %s failed in %s: %s", thread_id, agent or "pipeline", e)
        runs.emit(thread_id, "error", agent or "pipeline", str(e) if agent else f"pipeline failed: {e}",
                  payload={"failed_agent": agent, "retryable": True})
        runs.close(thread_id)
        return None

    state = await _e.graph.aget_state(_cfg(thread_id))
    if state.interrupts:
        _set_status(thread_id, "review")
        payload = review_payload(state.values)
        n = len(payload.conflicts)
        runs.emit(thread_id, "review_ready", "pipeline",
                  f"Ready for review: {len(payload.decisions)} decisions, {len(payload.tasks)} tasks, "
                  f"{n} conflict{'s' if n != 1 else ''}",
                  payload=payload.model_dump())
        return state.values

    action = (state.values.get("review_action") or {}).get("action")
    if action == "approve":
        _set_status(thread_id, "approved")
        result = {**EMPTY_RESULT, **(state.values.get("result") or {})}
        runs.emit(thread_id, "agent_end", "pipeline", "Approved and executed",
                  payload={"status": "approved", **result})
    else:
        _set_status(thread_id, "rejected")
        runs.emit(thread_id, "agent_end", "pipeline", "Rejected; nothing was posted",
                  payload={"status": "rejected"})
    runs.close(thread_id)
    return state.values


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _e.tasks.add(task)
    task.add_done_callback(_e.tasks.discard)


def start(thread_id: str, project: str, initial_state: dict) -> None:
    with Session(get_engine()) as s:
        s.add(Run(thread_id=thread_id, project=project, status="running"))
        s.commit()
    runs.open_channel(thread_id)
    runs.emit(thread_id, "agent_start", "pipeline", f"Run started for {initial_state['meeting']['title']}")
    _spawn(_drive(thread_id, initial_state))


async def approve(thread_id: str, resolutions: dict, ripple_actions: dict) -> dict:
    _claim(thread_id, "approving")
    action = {"action": "approve", "resolutions": resolutions, "ripple_actions": ripple_actions}
    values = await _drive(thread_id, Command(resume=action))
    if values is None:
        raise RuntimeError("execution failed after approval; see the run stream, then POST /retry")
    return {**EMPTY_RESULT, **(values.get("result") or {})}


async def reject(thread_id: str) -> None:
    _claim(thread_id, "rejected")
    await _drive(thread_id, Command(resume={"action": "reject"}))


async def retry(thread_id: str) -> None:
    status = _status(thread_id)
    if status is None:
        raise KeyError(thread_id)
    if not _set_status(thread_id, "running", only_if="error"):
        raise RunConflict(f"run is {status}; only failed runs can be retried")
    runs.reopen_for_retry(thread_id)
    runs.emit(thread_id, "agent_start", "pipeline", "Retrying from the failed step")
    _spawn(_drive(thread_id, None))


def _claim(thread_id: str, new_status: str) -> None:
    """First approve/reject wins: atomically move review → new_status, else 409."""
    status = _status(thread_id)
    if status is None:
        raise KeyError(thread_id)
    if not _set_status(thread_id, new_status, only_if="review"):
        raise RunConflict(f"run is already {status}" if status != "running" else "run is still processing")


async def ensure_channel(thread_id: str) -> None:
    """After a server restart the event buffer is gone; rebuild what we can from the checkpoint."""
    if runs.has_channel(thread_id):
        return
    status = _status(thread_id)
    if status is None:
        raise KeyError(thread_id)
    runs.open_channel(thread_id)
    if status == "review":
        payload = await get_review(thread_id)
        runs.emit(thread_id, "review_ready", "pipeline", "Ready for review (restored)", payload=payload.model_dump())
    elif status in ("approved", "rejected"):
        runs.emit(thread_id, "agent_end", "pipeline", f"Run {status}", payload={"status": status})
        runs.close(thread_id)
    elif status == "error":
        runs.emit(thread_id, "error", "pipeline", "Run was interrupted; POST /retry to resume",
                  payload={"failed_agent": None, "retryable": True})
        runs.close(thread_id)

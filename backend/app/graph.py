"""LangGraph wiring.

normalizer → extractor → memory_retriever → conflict_detector → ripple
  → review (interrupt) ─approve→ executor → memory_writer → END
                       ─edit──→ review_editor → review
                       ─reject→ END

Every agent node is wrapped by ``instrument``, which emits agent_start/agent_end/error events,
paces the trace in replay mode, and runs the module's real ``run`` once ``IMPLEMENTED`` is True
(until then the node passes state through unchanged). The review node is not instrumented: LangGraph
re-executes it on resume, so ``review_ready`` is emitted by the driver in app/pipeline.py instead.
"""

import asyncio
import importlib
import time
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.config import get_settings
from app.services import runs

PRE_REVIEW = ["normalizer", "extractor", "memory_retriever", "conflict_detector", "ripple"]
POST_REVIEW = ["executor", "memory_writer"]

START_MESSAGES = {
    "normalizer": "Cleaning up the transcript",
    "extractor": "Extracting decisions, tasks, owners and deadlines",
    "memory_retriever": "Searching past decisions",
    "conflict_detector": "Checking against earlier decisions",
    "ripple": "Tracing what these changes break downstream",
    "review_editor": "Applying your spoken edits",
    "executor": "Creating tasks and scheduling reminders",
    "memory_writer": "Updating team memory",
}


class RunState(TypedDict, total=False):
    thread_id: str
    meeting: dict
    raw_text: str
    clean_text: str
    corrections: list[dict]
    decisions: list[dict]
    tasks: list[dict]
    conflicts: list[dict]
    questions: list[dict]
    ripples: list[dict]
    heads_up: list[dict]
    related: dict  # memory_retriever output: new decision id → past decisions
    review_action: dict  # resume value: {"action": "approve"|"reject"|"edit", ...}
    result: dict  # executor + memory_writer output, returned by /approve


class AgentFailed(Exception):
    """Raised by an instrumented node. The driver marks the run failed, then emits the error event,
    so a client reacting to the event can retry immediately."""

    def __init__(self, agent: str, cause: BaseException):
        super().__init__(f"{agent} failed: {cause}")
        self.agent = agent


def instrument(name: str):
    async def node(state: RunState) -> dict[str, Any]:
        tid = state["thread_id"]
        settings = get_settings()
        runs.emit(tid, "agent_start", name, START_MESSAGES[name])
        t0 = time.perf_counter()
        module = importlib.import_module(f"app.agents.{name}")
        try:
            if module.IMPLEMENTED:
                update = await module.run(state) or {}
                describe = getattr(module, "describe", None)
                message = describe(update) if describe else "Done"
            else:
                update, message = {}, "Not built yet; passed through"
        except Exception as e:
            raise AgentFailed(name, e) from e
        if settings.replay_active and settings.replay_step_ms > 0:
            remaining = settings.replay_step_ms / 1000 - (time.perf_counter() - t0)
            if remaining > 0:
                await asyncio.sleep(remaining)
        run_ms = int((time.perf_counter() - t0) * 1000)
        runs.emit(tid, "agent_end", name, message, run_ms=run_ms)
        return update

    node.__name__ = name
    return node


async def review(state: RunState) -> dict:
    action = interrupt({"thread_id": state["thread_id"]})
    return {"review_action": action}


def _after_review(state: RunState) -> str:
    return {"approve": "executor", "edit": "review_editor"}.get(state["review_action"]["action"], END)


def build(checkpointer):
    g = StateGraph(RunState)
    for name in PRE_REVIEW + POST_REVIEW + ["review_editor"]:
        g.add_node(name, instrument(name))
    g.add_node("review", review)

    g.add_edge(START, PRE_REVIEW[0])
    for a, b in zip(PRE_REVIEW, PRE_REVIEW[1:]):
        g.add_edge(a, b)
    g.add_edge(PRE_REVIEW[-1], "review")
    g.add_conditional_edges("review", _after_review, ["executor", "review_editor", END])
    g.add_edge("review_editor", "review")
    g.add_edge("executor", "memory_writer")
    g.add_edge("memory_writer", END)
    return g.compile(checkpointer=checkpointer)

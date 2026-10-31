"""Guards on the scaffold itself: seed data, contract mirror, agent modules."""

import importlib
import inspect
import re
from pathlib import Path

import pytest

from app import schemas

REPO = Path(__file__).resolve().parents[2]
AGENTS = [
    "normalizer", "extractor", "memory_retriever", "conflict_detector",
    "ripple", "review_editor", "executor", "memory_writer",
]


def test_seed_debrief_contains_demo_beats(seed_dir):
    text = (seed_dir / "debrief2.txt").read_text()
    for beat in ["Android", "December 1st, no wait, November 28th", "next Wednesday",
                 "Play Store", "coffee machine", "Stripe", "Razorpay KYC", "Monday"]:
        assert beat in text, beat


def test_seed_meeting1_has_three_speakers(seed_dir):
    speakers = {line.split(":", 1)[0] for line in (seed_dir / "meeting1.txt").read_text().splitlines() if ":" in line}
    assert speakers == {"Priya", "Rahul", "Ananya"}


@pytest.mark.parametrize("name", AGENTS)
def test_agent_modules_expose_async_run(name):
    mod = importlib.import_module(f"app.agents.{name}")
    assert mod.NODE == name
    assert inspect.iscoroutinefunction(mod.run)


def test_schema_fields_match_contract():
    """Every field in the Pydantic mirror must be written in CONTRACT.md's type block (drift guard)."""
    contract = (REPO / "CONTRACT.md").read_text()
    for model in [schemas.Correction, schemas.Decision, schemas.Task, schemas.Conflict, schemas.Question,
                  schemas.Meeting, schemas.ReviewPayload, schemas.AgentEvent, schemas.Ripple,
                  schemas.HeadsUp, schemas.RadarTopic]:
        block = re.search(rf"type {model.__name__} = \{{(.*?)\n\}};", contract, re.S)
        assert block, f"type {model.__name__} missing from CONTRACT.md"
        for field in model.model_fields:
            assert re.search(rf"\b{field}\??:", block.group(1)), f"{model.__name__}.{field} not in CONTRACT.md"

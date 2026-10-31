"""THE demo guardrail. If this is green, the 2-minute stage demo works.

Drives the real HTTP contract: reset → ingest debrief2 → read the SSE stream to review_ready →
assert on the ReviewPayload. Runs on replay recordings, so it needs neither network nor keys.
Each check skips itself until its routes exist (Phase 2) and its agent's IMPLEMENTED flag is True
(normalizer/extractor Phase 4, conflict_detector Phase 5, ripple Phase 7), then turns on with no edits.
"""

import importlib
import json

import pytest

from tests.conftest import route_exists

pytestmark = pytest.mark.golden


def needs(*agents: str) -> None:
    pending = [a for a in agents if not importlib.import_module(f"app.agents.{a}").IMPLEMENTED]
    if pending:
        pytest.skip(f"agent not built yet: {', '.join(pending)}")


def _run_debrief2(client, seed_dir, expected) -> dict:
    if not (route_exists(client, "POST", "/api/demo/reset") and route_exists(client, "POST", "/api/ingest")):
        pytest.skip("pipeline routes not built yet (Phase 2)")
    assert client.post("/api/demo/reset").status_code == 200
    body = {**expected["meeting"], "text": (seed_dir / "debrief2.txt").read_text()}
    r = client.post("/api/ingest", json=body)
    assert r.status_code == 200, r.text
    thread_id = r.json()["thread_id"]

    review = None
    with client.stream("GET", f"/api/runs/{thread_id}/stream?until=review") as s:
        for line in s.iter_lines():
            if not line.startswith("data:"):
                continue
            event = json.loads(line[5:].strip())
            if event["type"] == "error":
                pytest.fail(f"pipeline error from {event['agent']}: {event['message']}")
            if event["type"] == "review_ready":
                review = event["payload"]
                break
    assert review is not None, "stream ended without review_ready"
    return review


@pytest.fixture(scope="module")
def review(client, seed_dir, expected_debrief2):
    return _run_debrief2(client, seed_dir, expected_debrief2)


def test_corrections(review, expected_debrief2):
    needs("normalizer")
    for exp in expected_debrief2["corrections_must_include"]:
        hits = [c for c in review["corrections"]
                if c["kind"] == exp["kind"] and exp["original_contains"].lower() in c["original"].lower()]
        assert hits, f"missing correction {exp}; got {review['corrections']}"
        if "resolved_contains" in exp:
            assert any(exp["resolved_contains"] in c["resolved"] for c in hits), hits
        if "resolved_date" in exp:
            assert any(exp["resolved_date"] in c["resolved"] for c in hits), hits


def test_digression_removed(review, expected_debrief2):
    needs("normalizer")
    for word in expected_debrief2["clean_text_must_not_contain"]:
        assert word.lower() not in review["clean_text"].lower(), word


def test_decisions(review, expected_debrief2):
    needs("extractor")
    by_topic = {d["topic_key"]: d for d in review["decisions"]}
    for topic, exp in expected_debrief2["decisions_topics"].items():
        assert topic in by_topic, f"no decision for {topic}; got {list(by_topic)}"
        d = by_topic[topic]
        assert exp["statement_contains"].lower() in d["statement"].lower(), d
        if "made_by" in exp:
            assert d["made_by"] == exp["made_by"], f"attribution wrong for {topic}: {d['made_by']}"


def test_tasks(review, expected_debrief2):
    needs("extractor")
    for exp in expected_debrief2["tasks"]:
        hits = [t for t in review["tasks"]
                if t["owner"] == exp["owner"] and exp["title_contains"].lower() in t["title"].lower()]
        assert hits, f"missing task {exp}; got {[(t['owner'], t['title']) for t in review['tasks']]}"
        t = hits[0]
        assert t["due_date"] == exp["due_date"], t
        assert exp["raw_due_phrase_contains"].lower() in t["raw_due_phrase"].lower(), t


def test_three_semantic_conflicts_against_meeting1(review, expected_debrief2):
    needs("memory_retriever", "conflict_detector")
    exp = expected_debrief2["conflicts"]
    semantic = [c for c in review["conflicts"] if c["type"] in exp["types"]]
    assert len(semantic) == exp["semantic_count"], [c["explanation"] for c in semantic]
    old_topics = sorted(c["old_decision"]["topic_key"] for c in semantic)
    assert old_topics == sorted(exp["old_topics"])
    assert all(c["old_decision"]["status"] == "active" for c in semantic)


def test_ripple_effect(review, expected_debrief2):
    needs("ripple")
    for exp in expected_debrief2["ripples_must_include"]:
        assert any(
            r["kind"] == exp["kind"] and r["task"] and r["task"]["owner"] == exp["task_owner"]
            and exp["task_title_contains"].lower() in r["task"]["title"].lower()
            for r in review["ripples"]
        ), review["ripples"]

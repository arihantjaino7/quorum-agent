"""Phase 2: walking skeleton — LangGraph interrupt/resume, SSE trace, approve/reject/retry."""

import json

import pytest

from app.graph import POST_REVIEW, PRE_REVIEW

@pytest.fixture(autouse=True)
def stub_agents(monkeypatch):
    """These tests cover pipeline plumbing, so every agent runs as a pass-through stub (no LLM, no recordings)."""
    import importlib

    for name in PRE_REVIEW + POST_REVIEW + ["review_editor"]:
        monkeypatch.setattr(importlib.import_module(f"app.agents.{name}"), "IMPLEMENTED", False)


BODY = {"project": "Pocket", "title": "Investor sync debrief", "date": "2026-10-31",
        "speaker": "Priya", "source_type": "voice", "text": "so um Rahul said Android is back in"}


def events(client, tid, stop_at=("review_ready",)):
    """Read the SSE stream until an event whose type is in stop_at, or until the server closes it."""
    out = []
    with client.stream("GET", f"/api/runs/{tid}/stream") as s:
        assert s.status_code == 200
        for line in s.iter_lines():
            if line.startswith("data:"):
                e = json.loads(line[5:].strip())
                out.append(e)
                if e["type"] in stop_at:
                    break
    return out


def ingest(client, **over) -> str:
    r = client.post("/api/ingest", json={**BODY, **over})
    assert r.status_code == 200, r.text
    return r.json()["thread_id"]


def trace(evts):
    return [(e["type"], e["agent"]) for e in evts]


def test_trace_runs_every_agent_then_pauses_for_review(fresh):
    tid = ingest(fresh)
    assert tid.startswith("run_")
    evts = events(fresh, tid)
    expected = [("agent_start", "pipeline")]
    for a in PRE_REVIEW:
        expected += [("agent_start", a), ("agent_end", a)]
    expected += [("review_ready", "pipeline")]
    assert trace(evts) == expected
    assert all(isinstance(e["run_ms"], int) for e in evts if e["type"] == "agent_end")
    assert all(e["ts"] == "2026-10-31T09:00:00" for e in evts)  # frozen demo clock

    review = evts[-1]["payload"]
    assert review["thread_id"] == tid
    assert review["meeting"]["id"].startswith("mtg_") and review["meeting"]["project"] == "Pocket"
    assert review["raw_text"] == BODY["text"]
    assert fresh.get(f"/api/runs/{tid}/review").json() == review


def test_approve_resumes_through_executor_and_memory_writer(fresh):
    tid = ingest(fresh)
    events(fresh, tid)
    r = fresh.post(f"/api/runs/{tid}/approve", json={"resolutions": {}})
    assert r.status_code == 200
    assert r.json() == {"created_tasks": [], "superseded_ids": [], "updated_tasks": [],
                        "cancelled_task_ids": [], "heads_up_sent": []}

    # The same stream stays open after review_ready and ends with the pipeline's final agent_end.
    evts = events(fresh, tid, stop_at=())
    tail = trace(evts)[trace(evts).index(("review_ready", "pipeline")) + 1:]
    expected = []
    for a in POST_REVIEW:
        expected += [("agent_start", a), ("agent_end", a)]
    assert tail == expected + [("agent_end", "pipeline")]
    assert evts[-1]["payload"]["status"] == "approved"


def test_first_approve_wins(fresh):
    tid = ingest(fresh)
    events(fresh, tid)
    assert fresh.post(f"/api/runs/{tid}/approve", json={}).status_code == 200
    second = fresh.post(f"/api/runs/{tid}/approve", json={})
    assert second.status_code == 409 and "approved" in second.json()["detail"]
    assert fresh.post(f"/api/runs/{tid}/reject").status_code == 409
    assert fresh.get(f"/api/runs/{tid}/review").status_code == 409


def test_reject_ends_run_and_posts_nothing(fresh):
    tid = ingest(fresh)
    events(fresh, tid)
    assert fresh.post(f"/api/runs/{tid}/reject").json() == {"ok": True}
    evts = events(fresh, tid, stop_at=())
    assert trace(evts)[-1] == ("agent_end", "pipeline") and evts[-1]["payload"] == {"status": "rejected"}
    assert not any(e["agent"] in POST_REVIEW for e in evts)
    assert fresh.post(f"/api/runs/{tid}/approve", json={}).status_code == 409


def test_parallel_runs_are_independent(fresh):
    a, b = ingest(fresh), ingest(fresh, title="Design review")
    assert events(fresh, a)[-1]["type"] == "review_ready"
    assert events(fresh, b)[-1]["payload"]["meeting"]["title"] == "Design review"
    fresh.post(f"/api/runs/{a}/reject")
    assert fresh.get(f"/api/runs/{b}/review").status_code == 200


@pytest.fixture
def failing_agent(monkeypatch):
    """Make an agent fail on its first call only; returns the call counter."""

    def install(name: str):
        import importlib

        mod = importlib.import_module(f"app.agents.{name}")
        calls = {"n": 0}

        async def run(state):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("Groq 503")
            return {}

        monkeypatch.setattr(mod, "IMPLEMENTED", True)
        monkeypatch.setattr(mod, "run", run)
        return calls

    return install


def test_failed_agent_stops_run_and_retry_resumes_from_it(fresh, failing_agent):
    calls = failing_agent("extractor")
    tid = ingest(fresh)
    evts = events(fresh, tid, stop_at=("error", "review_ready"))
    err = evts[-1]
    assert (err["type"], err["agent"]) == ("error", "extractor")
    assert err["payload"] == {"failed_agent": "extractor", "retryable": True}
    assert "Groq 503" in err["message"]
    assert fresh.get(f"/api/runs/{tid}/review").status_code == 409

    assert fresh.post(f"/api/runs/{tid}/retry").json() == {"ok": True}
    evts = events(fresh, tid)
    assert evts[-1]["type"] == "review_ready"
    assert not any(e["type"] == "error" for e in evts)  # stale error dropped from the replay
    assert sum(e == ("agent_start", "normalizer") for e in trace(evts)) == 1  # earlier agents did not rerun
    assert calls["n"] == 2


def test_failure_after_approve_returns_502_and_retry_finishes(fresh, failing_agent):
    failing_agent("executor")
    tid = ingest(fresh)
    events(fresh, tid)
    r = fresh.post(f"/api/runs/{tid}/approve", json={})
    assert r.status_code == 502 and "/retry" in r.json()["detail"]
    assert fresh.post(f"/api/runs/{tid}/retry").status_code == 200
    evts = events(fresh, tid, stop_at=())
    assert evts[-1]["payload"]["status"] == "approved"


def test_retry_only_for_failed_runs(fresh):
    tid = ingest(fresh)
    events(fresh, tid)
    assert fresh.post(f"/api/runs/{tid}/retry").status_code == 409


def test_unknown_run_is_404(fresh):
    for method, path in [("GET", "stream"), ("GET", "review"), ("POST", "approve"), ("POST", "reject"), ("POST", "retry")]:
        kwargs = {"json": {}} if method == "POST" else {}
        assert fresh.request(method, f"/api/runs/run_nope/{path}", **kwargs).status_code == 404, path


def test_ingest_validation(fresh):
    assert fresh.post("/api/ingest", json={**BODY, "text": "   "}).status_code == 422
    assert fresh.post("/api/ingest", json={**BODY, "date": "last friday"}).status_code == 422
    assert fresh.post("/api/ingest", json={**BODY, "source_type": "fax"}).status_code == 422


def test_reset_clears_runs(fresh):
    tid = ingest(fresh)
    events(fresh, tid)
    fresh.post("/api/demo/reset")
    assert fresh.get(f"/api/runs/{tid}/review").status_code == 404


def test_stream_survives_lost_event_buffer(fresh):
    """After a server restart the in-memory buffer is gone; the stream is rebuilt from the checkpoint."""
    from app.services import runs

    tid = ingest(fresh)
    review = events(fresh, tid)[-1]["payload"]
    runs._channels.pop(tid)
    evts = events(fresh, tid)
    assert evts[-1]["type"] == "review_ready" and evts[-1]["payload"] == review


def test_replay_pacing_slows_each_agent(fresh, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "replay_step_ms", 60)
    evts = events(fresh, ingest(fresh))
    assert all(e["run_ms"] >= 60 for e in evts if e["type"] == "agent_end")


def test_long_waits_show_as_progress_in_the_trace(fresh, monkeypatch):
    import app.agents.extractor as ex
    from app.integrations import llm

    async def run(state):
        llm._report("Waiting for Groq rate limit (11s)…")
        return {}

    monkeypatch.setattr(ex, "IMPLEMENTED", True)
    monkeypatch.setattr(ex, "run", run)
    evts = events(fresh, ingest(fresh))
    i = trace(evts).index(("agent_start", "extractor"))
    assert trace(evts)[i + 1] == ("agent_progress", "extractor")
    assert evts[i + 1]["message"] == "Waiting for Groq rate limit (11s)…"
    assert trace(evts)[i + 2] == ("agent_end", "extractor")

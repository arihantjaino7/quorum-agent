"""Phase 3: LLM harness + replay. Offline (Groq is faked), plus one opt-in live test."""

import asyncio
import json
import logging
import os

import pytest
from pydantic import BaseModel

from app.config import get_settings
from app.integrations import llm
from app.replay import store


class Out(BaseModel):
    answer: str
    due: str | None


MSGS = [("system", "Extract the answer."), ("user", "The launch   moves to\nNovember 28th.")]


@pytest.fixture
def env(monkeypatch, tmp_path):
    """Isolated recordings dir + controllable settings and Groq availability."""
    monkeypatch.setattr(store, "RECORDINGS_DIR", tmp_path)
    s = get_settings()
    for k, v in {"demo_replay": True, "quorum_record": False, "groq_max_retries": 2, "groq_timeout_s": 30.0,
                 "groq_reasoning_strong": "", "groq_reasoning_fast": "", "quorum_record_only": ""}.items():
        monkeypatch.setattr(s, k, v)
    monkeypatch.setattr(llm, "_available", True)
    return s


@pytest.fixture
def fake(monkeypatch):
    """Script Groq's answers: each item is a dict result, or an exception to raise."""
    calls = []

    def install(*answers):
        queue = list(answers)
        calls.clear()

        async def _complete(model, schema, messages, reasoning=None):
            calls.append({"model": model, "messages": messages, "reasoning": reasoning})
            a = queue.pop(0)
            if isinstance(a, BaseException):
                raise a
            return a

        monkeypatch.setattr(llm, "_complete", _complete)
        return calls

    return install


def ok(answer="28 Nov", due="2026-11-28"):
    return {"raw": json.dumps({"answer": answer, "due": due}), "parsed": Out(answer=answer, due=due), "error": None}


def bad(msg="missing field 'due'"):
    return {"raw": '{"answer": "28 Nov"}', "parsed": None, "error": msg}


def run(coro):
    return asyncio.run(coro)


def test_replay_hit_never_calls_groq(env, fake):
    calls = fake()  # any call would fail: the queue is empty
    key = store.make_key("extractor", "strong", Out, MSGS)
    store.save("extractor", key, tier="strong", model=llm.model_for("strong"), schema=Out,
               messages=MSGS, output={"answer": "recorded", "due": None}, latency_ms=5)
    assert run(llm.structured("extractor", "strong", Out, MSGS)) == Out(answer="recorded", due=None)
    assert calls == []


def test_miss_without_groq_is_a_clear_error(env, monkeypatch):
    monkeypatch.setattr(llm, "_available", False)
    with pytest.raises(llm.LLMUnavailable, match="no replay recording"):
        run(llm.structured("extractor", "strong", Out, MSGS))


def test_record_only_when_asked(env, fake, tmp_path):
    fake(ok())
    run(llm.structured("extractor", "strong", Out, MSGS))
    assert list(tmp_path.rglob("*.json")) == []  # QUORUM_RECORD off → nothing saved

    env.quorum_record = True
    fake(ok("live"))
    run(llm.structured("extractor", "strong", Out, MSGS))
    files = list(tmp_path.rglob("*.json"))
    assert len(files) == 1
    rec = json.loads(files[0].read_text())
    assert rec["output"] == {"answer": "live", "due": "2026-11-28"} and rec["model"] == llm.model_for("strong")
    assert rec["agent"] == "extractor" and rec["messages"][0]["role"] == "system"

    env.quorum_record = False
    calls = fake()
    assert run(llm.structured("extractor", "strong", Out, MSGS)).answer == "live"  # now served from replay
    assert calls == []


def test_record_only_limits_which_agents_go_live(env, fake, monkeypatch):
    key = store.make_key("extractor", "strong", Out, MSGS)
    store.save("extractor", key, tier="strong", model="m", schema=Out, messages=MSGS,
               output={"answer": "recorded", "due": None}, latency_ms=1)
    env.quorum_record = True
    monkeypatch.setattr(env, "quorum_record_only", "conflict_detector")
    calls = fake()
    assert run(llm.structured("extractor", "strong", Out, MSGS)).answer == "recorded"  # not listed → replay
    assert calls == []


def test_demo_replay_off_ignores_recordings(env, fake):
    key = store.make_key("extractor", "strong", Out, MSGS)
    store.save("extractor", key, tier="strong", model="m", schema=Out, messages=MSGS,
               output={"answer": "recorded", "due": None}, latency_ms=1)
    env.demo_replay = False
    fake(ok("live"))
    assert run(llm.structured("extractor", "strong", Out, MSGS)).answer == "live"


def test_malformed_output_is_retried_with_feedback(env, fake):
    calls = fake(bad("missing field 'due'"), ok())
    assert run(llm.structured("extractor", "strong", Out, MSGS)).due == "2026-11-28"
    assert len(calls) == 2
    retry_msgs = calls[1]["messages"]
    assert retry_msgs[:2] == MSGS
    assert retry_msgs[2][0] == "assistant" and "missing field 'due'" in retry_msgs[3][1]


def test_gives_up_after_two_retries(env, fake):
    calls = fake(bad(), bad(), bad(), ok())
    with pytest.raises(llm.LLMFailed, match="after 3 attempts"):
        run(llm.structured("extractor", "strong", Out, MSGS))
    assert len(calls) == 3


def test_timeout_fails_immediately(env, fake):
    calls = fake(asyncio.TimeoutError(), ok())
    with pytest.raises(llm.LLMFailed, match="timed out after 30s"):
        run(llm.structured("extractor", "strong", Out, MSGS))
    assert len(calls) == 1


class _Http503(Exception):
    status_code = 503


def test_transient_error_is_retried(env, fake):
    calls = fake(_Http503("service unavailable"), ok())
    assert run(llm.structured("extractor", "strong", Out, MSGS)).answer == "28 Nov"
    assert len(calls) == 2


def test_groq_json_validation_failure_counts_as_malformed(env, fake):
    err = Exception("Error code: 400 - {'error': {'code': 'json_validate_failed', 'failed_generation': ''}}")
    calls = fake(err, ok())
    assert run(llm.structured("extractor", "strong", Out, MSGS)).answer == "28 Nov"
    assert len(calls) == 2 and "failed JSON validation" in calls[1]["messages"][-1][1]


def _429(wait_text):
    return Exception("Error code: 429 - {'error': {'message': 'Rate limit reached for model on tokens per minute "
                     f"(TPM): Limit 8000, Used 7612, Requested 1799. Please try again in {wait_text}.', "
                     "'code': 'rate_limit_exceeded'}}")


def test_rate_limit_waits_when_it_fits_and_reports_progress(env, fake, monkeypatch):
    slept, seen = [], []

    async def fake_sleep(secs):
        slept.append(secs)

    monkeypatch.setattr(llm.asyncio, "sleep", fake_sleep)
    calls = fake(_429("10.58s"), ok())
    token = llm.progress.set(seen.append)
    try:
        assert run(llm.structured("extractor", "strong", Out, MSGS)).answer == "28 Nov"
    finally:
        llm.progress.reset(token)
    assert len(calls) == 2 and slept and 10.5 < slept[0] < 11.5
    assert seen == ["Waiting for Groq rate limit (11s)…"]


def test_rate_limit_longer_than_budget_fails_clearly(env, fake):
    calls = fake(_429("47.82s"), ok())
    with pytest.raises(llm.LLMFailed, match=r"rate limit \(free tier\); try again in 48s"):
        run(llm.structured("extractor", "strong", Out, MSGS))
    assert len(calls) == 1


def test_rate_limit_wait_parsing():
    assert llm.rate_limit_wait(_429("1m2.5s")) == 62.5
    assert llm.rate_limit_wait(ValueError("nope")) is None


def test_request_too_large_fails_fast(env, fake):
    calls = fake(Exception("Error code: 429 - Request too large for model on output tokens per minute (OTPM): "
                           "Limit 1000, Requested 1015. 'code': 'rate_limit_exceeded'"), ok())
    with pytest.raises(llm.LLMFailed, match="request too large"):
        run(llm.structured("extractor", "strong", Out, MSGS))
    assert len(calls) == 1


TOO_LARGE = "Error code: 429 - Request too large for model on output tokens per minute (OTPM): " \
            "Limit 1000, Requested 1015. 'code': 'rate_limit_exceeded'"


def test_fast_tier_too_large_falls_back_to_strong_model(env, fake):
    env.groq_reasoning_strong = "low"
    seen = []
    calls = fake(Exception(TOO_LARGE), ok("from backup"))
    token = llm.progress.set(seen.append)
    try:
        assert run(llm.structured("normalizer", "fast", Out, MSGS)).answer == "from backup"
    finally:
        llm.progress.reset(token)
    assert [c["model"] for c in calls] == [llm.model_for("fast"), llm.model_for("strong")]
    assert calls[1]["reasoning"] == "low"
    assert seen and "backup model" in seen[0]


def test_fallback_recording_names_the_model_actually_used(env, fake, tmp_path):
    env.quorum_record = True
    fake(Exception(TOO_LARGE), ok())
    run(llm.structured("normalizer", "fast", Out, MSGS))
    rec = json.loads(next(tmp_path.rglob("*.json")).read_text())
    assert rec["model"] == llm.model_for("strong") and rec["tier"] == "fast"


def test_strong_tier_too_large_has_no_fallback(env, fake):
    calls = fake(Exception(TOO_LARGE), ok())
    with pytest.raises(llm.RequestTooLarge):
        run(llm.structured("extractor", "strong", Out, MSGS))
    assert len(calls) == 1


def test_reasoning_effort_comes_from_config(env, fake):
    env.groq_reasoning_strong = "low"
    calls = fake(ok())
    run(llm.structured("extractor", "strong", Out, MSGS))
    assert calls[0]["reasoning"] == "low"
    env.groq_reasoning_strong = ""
    calls = fake(ok())
    run(llm.structured("extractor", "strong", Out, MSGS))
    assert calls[0]["reasoning"] is None


def test_non_transient_error_fails_fast(env, fake):
    calls = fake(ValueError("bad request: unknown model"), ok())
    with pytest.raises(llm.LLMFailed, match="unknown model"):
        run(llm.structured("extractor", "strong", Out, MSGS))
    assert len(calls) == 1


def test_key_ignores_whitespace_but_not_meaning():
    k = store.make_key("extractor", "strong", Out, MSGS)
    assert k == store.make_key("extractor", "strong", Out, [("system", " Extract  the answer. "),
                                                             ("user", "The launch moves to November 28th.")])
    assert k != store.make_key("normalizer", "strong", Out, MSGS)
    assert k != store.make_key("extractor", "fast", Out, MSGS)
    assert k != store.make_key("extractor", "strong", Out, [MSGS[0], ("user", "Launch moves to December 1st.")])

    class Out2(BaseModel):
        answer: str

    assert k != store.make_key("extractor", "strong", Out2, MSGS)


def test_model_mismatch_is_logged_not_fatal(env, fake, caplog):
    key = store.make_key("extractor", "strong", Out, MSGS)
    store.save("extractor", key, tier="strong", model="some-old-model", schema=Out, messages=MSGS,
               output={"answer": "recorded", "due": None}, latency_ms=1)
    with caplog.at_level(logging.INFO, logger="quorum.llm"):
        assert run(llm.structured("extractor", "strong", Out, MSGS)).answer == "recorded"
    assert "some-old-model" in caplog.text


def test_probe_rules(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "groq_api_key", "gsk_test")
    assert llm.probe() is True
    monkeypatch.setattr(s, "groq_api_key", "")
    monkeypatch.setattr(s, "groq_autodetect", False)
    assert llm.probe() is False
    assert llm.replay_active() is True


def test_health_reports_groq_and_replay(client):
    body = client.get("/api/health").json()
    assert body["integrations"]["groq"] is False and body["replay"] is True


@pytest.mark.live
@pytest.mark.skipif(os.environ.get("QUORUM_LIVE_TESTS") != "1", reason="set QUORUM_LIVE_TESTS=1 to call real Groq")
def test_live_structured_call(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "RECORDINGS_DIR", tmp_path)
    s = get_settings()
    monkeypatch.setattr(s, "demo_replay", False)
    monkeypatch.setattr(s, "groq_autodetect", True)
    llm.reset_probe()
    try:
        out = run(llm.structured("extractor", "strong", Out, [
            ("system", "Return the final launch date as answer, and due as an ISO date. Meeting date: 2026-10-31."),
            ("user", "launch moves to December 1st, no wait, November 28th"),
        ]))
    finally:
        llm.reset_probe()
    assert out.due == "2026-11-28"

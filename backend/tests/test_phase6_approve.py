"""Phases 6-8 and the read side, end to end on the seed debrief (replay recordings, no network, no keys)."""

import json

import pytest

DEBRIEF = {"project": "Pocket", "title": "Investor sync debrief", "date": "2026-10-31", "speaker": "Priya",
           "source_type": "voice"}


def run_to_review(client) -> dict:
    assert client.post("/api/demo/reset").status_code == 200
    from pathlib import Path

    text = (Path(__file__).resolve().parent.parent / "seed" / "debrief2.txt").read_text()
    tid = client.post("/api/ingest", json={**DEBRIEF, "text": text}).json()["thread_id"]
    with client.stream("GET", f"/api/runs/{tid}/stream?until=review") as s:
        for line in s.iter_lines():
            if line.startswith("data:"):
                e = json.loads(line[5:].strip())
                assert e["type"] != "error", e
                if e["type"] == "review_ready":
                    return {"tid": tid, **e["payload"]}
    raise AssertionError("no review_ready")


@pytest.fixture
def review(fresh):
    return run_to_review(fresh)


def topic_conflict(review, old_topic):
    return next(c for c in review["conflicts"] if (c["old_decision"] or {}).get("topic_key") == old_topic)


def accept_all(review):
    return {c["id"]: "accept_new" for c in review["conflicts"]}


def test_ripple_proposes_rescope_and_date_shift(review):
    kinds = {(r["kind"], r["task"]["title"]) for r in review["ripples"]}
    assert any(k == "rescope" and "onboarding" in t.lower() for k, t in kinds)
    shifted = [r for r in review["ripples"] if r["kind"] == "reschedule"]
    assert shifted and all(r["proposal"]["due_date"] > r["task"]["due_date"] for r in shifted)
    assert {h["person"] for h in review["heads_up"]} >= {"Ananya"}


def test_approve_updates_memory_tasks_and_lineage(fresh, review):
    r = fresh.post(f"/api/runs/{review['tid']}/approve", json={"resolutions": accept_all(review)})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["created_tasks"]) == 3
    assert all(t["tracker_url"] is None for t in body["created_tasks"])  # no keys: kept locally
    assert len(body["superseded_ids"]) == 3
    graph = fresh.get("/api/decisions/graph?project=Pocket").json()
    assert len(graph["edges"]) == 3
    active = {d["topic_key"]: d["statement"] for d in fresh.get("/api/decisions?project=Pocket").json()}
    assert "Android" in active["platform_scope"] and "Stripe" in active["payments_provider"]
    assert fresh.get("/api/projects").json()[0]["meeting_count"] == 2
    tasks = fresh.get("/api/tasks?project=Pocket").json()
    assert len(tasks) == 6
    onboarding = next(t for t in tasks if t["id"] == "tsk_m1_onboarding")
    assert "rescoped" in onboarding["title"]  # ripple applied
    assert body["updated_tasks"] and {h["person"] for h in body["heads_up_sent"]} >= {"Ananya"}


def test_keep_previous_drops_the_decision_and_its_tasks(fresh, review):
    res = accept_all(review)
    res[topic_conflict(review, "platform_scope")["id"]] = "keep_old"
    body = fresh.post(f"/api/runs/{review['tid']}/approve", json={"resolutions": res}).json()
    titles = {t["title"] for t in body["created_tasks"]}
    assert not any("Android" in t or "Play Store" in t for t in titles)
    assert any("investor" in t.lower() for t in titles)
    active = {d["topic_key"]: d["statement"] for d in fresh.get("/api/decisions?project=Pocket").json()}
    assert "iOS only" in active["platform_scope"]
    assert len(body["superseded_ids"]) == 2


def test_skipping_a_ripple_leaves_the_task_untouched(fresh, review):
    skip = {r["id"]: "skip" for r in review["ripples"]}
    body = fresh.post(f"/api/runs/{review['tid']}/approve",
                      json={"resolutions": accept_all(review), "ripple_actions": skip}).json()
    assert body["updated_tasks"] == [] and body["heads_up_sent"] == []
    onboarding = next(t for t in fresh.get("/api/tasks?project=Pocket").json() if t["id"] == "tsk_m1_onboarding")
    assert onboarding["title"] == "Design onboarding screens" and onboarding["due_date"] == "2026-11-03"


def test_reject_stores_nothing(fresh, review):
    assert fresh.post(f"/api/runs/{review['tid']}/reject").status_code == 200
    assert fresh.get("/api/projects").json()[0]["meeting_count"] == 1
    assert len(fresh.get("/api/decisions?project=Pocket").json()) == 3


def test_second_approve_is_409(fresh, review):
    assert fresh.post(f"/api/runs/{review['tid']}/approve", json={"resolutions": accept_all(review)}).status_code == 200
    assert fresh.post(f"/api/runs/{review['tid']}/approve", json={"resolutions": {}}).status_code == 409


def test_voice_edit_applies_structured_changes(fresh, review, monkeypatch):
    from app.agents import review_editor as ed
    from app.integrations import llm

    async def fake(agent, tier, schema, messages):
        assert agent == "review_editor"
        tasks = [m for m in messages if m[0] == "user"][0][1]
        t = {line.split(":")[0].strip(): line for line in tasks.splitlines() if line.strip().startswith("T")}
        play = next(k for k, v in t.items() if "Play Store" in v)
        invest = next(k for k, v in t.items() if "investor" in v)
        return ed.EditOut(ops=[ed.Op(action="set_due", ref=play, value="the 18th"), ed.Op(action="drop_task", ref=invest, value=None)])

    monkeypatch.setattr(llm, "structured", fake)
    r = fresh.post(f"/api/runs/{review['tid']}/voice-edit", json={"instruction": "make Rahul's date the 18th and drop the investor update"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["changes"]) == 2
    tasks = {t["title"]: t for t in body["review"]["tasks"]}
    assert len(tasks) == 2 and tasks["Complete Play Store listing"]["due_date"] == "2026-11-18"
    assert fresh.post(f"/api/runs/{review['tid']}/approve", json={"resolutions": accept_all(body["review"])}).status_code == 200


def test_read_side_after_approval(fresh, review):
    fresh.post(f"/api/runs/{review['tid']}/approve", json={"resolutions": accept_all(review)})
    tl = fresh.get("/api/decisions/timeline?project=Pocket").json()["topics"]
    launch = next(t for t in tl if t["topic_key"] == "launch_date")
    assert [e["change"] for e in launch["events"]] == ["created", "reversed"]
    past = fresh.get("/api/decisions/as-of?project=Pocket&date=2026-10-25").json()
    assert {d["status"] for d in past["decisions"]} == {"active"} and len(past["changed_since"]) == 3
    topics = fresh.get("/api/radar?project=Pocket").json()["topics"]
    assert all(t["flips"] == 1 and t["risk"] == "medium" for t in topics)
    ans = fresh.post("/api/ask", json={"project": "Pocket", "question": "why did we drop Razorpay?"}).json()
    assert "Stripe" in ans["answer"] and ans["citations"]
    digest = fresh.get("/api/digest/Ananya").json()
    assert digest["person"] == "Ananya" and digest["due"] and digest["summary_md"].startswith("## Ananya")
    fresh.post("/api/clock", json={"now": "2026-11-03T09:00:00"})
    brief = fresh.get("/api/brief?project=Pocket").json()
    assert brief["agenda"] and brief["open_conflicts"] and brief["headline"]
    sent = fresh.post("/api/reminders/run").json()["sent"]
    assert sent and all(s["channel"] == "log" for s in sent)
    assert fresh.post("/api/reminders/run").json()["sent"] == []  # once per task

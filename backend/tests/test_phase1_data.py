"""Phase 1: data layer + demo controls."""

import json


def test_reset_seeds_meeting1(fresh):
    decisions = fresh.get("/api/decisions", params={"project": "Pocket"}).json()
    assert {d["topic_key"]: d["statement"] for d in decisions} == {
        "platform_scope": "v1 is iOS only; Android moves to v2",
        "launch_date": "Public launch is 20 Nov 2026",
        "payments_provider": "Payments via Razorpay, not Stripe",
    }
    assert all(d["status"] == "active" and d["meeting_id"] == "mtg_m1" and d["date"] == "2026-10-24" for d in decisions)

    tasks = fresh.get("/api/tasks", params={"project": "Pocket"}).json()
    assert [(t["owner"], t["due_date"]) for t in tasks] == [
        ("Ananya", "2026-11-03"), ("Priya", "2026-11-06"), ("Rahul", "2026-11-10"),
    ]
    assert all(t["status"] == "todo" and t["tracker_url"] is None and not t["reminder_sent"] for t in tasks)


def test_reset_is_idempotent_and_wipes_changes(fresh):
    fresh.patch("/api/tasks/tsk_m1_onboarding", json={"status": "done"})
    fresh.post("/api/clock", json={"now": "2026-11-20T10:00:00"})
    fresh.post("/api/demo/reset")
    assert fresh.get("/api/clock").json() == {"now": "2026-10-31T09:00:00"}
    assert len(fresh.get("/api/tasks").json()) == 3
    assert all(t["status"] == "todo" for t in fresh.get("/api/tasks").json())


def test_seed_quotes_are_exact_spans_of_transcript(seed_dir):
    transcript = (seed_dir / "meeting1.txt").read_text()
    data = json.loads((seed_dir / "meeting1.json").read_text())
    for item in data["decisions"] + data["tasks"]:
        assert item["source_quote"] in transcript, item["source_quote"]


def test_meetings_and_projects(fresh):
    assert fresh.get("/api/projects").json() == [{"name": "Pocket", "meeting_count": 1, "last_meeting": "2026-10-24"}]
    meetings = fresh.get("/api/meetings", params={"project": "Pocket"}).json()
    assert meetings == [{"id": "mtg_m1", "project": "Pocket", "title": "Pocket v1 planning sync",
                         "date": "2026-10-24", "speaker": "Priya", "source_type": "transcript"}]
    assert fresh.get("/api/meetings", params={"project": "Nope"}).json() == []


def test_clock_is_frozen_and_settable(fresh):
    assert fresh.get("/api/clock").json() == {"now": "2026-10-31T09:00:00"}
    assert fresh.post("/api/clock", json={"now": "2026-11-03T10:00:00"}).json() == {"now": "2026-11-03T10:00:00"}
    assert fresh.get("/api/clock").json() == {"now": "2026-11-03T10:00:00"}
    assert fresh.get("/api/health").json()["clock"] == "2026-11-03T10:00:00"
    # date-only input is accepted as midnight
    assert fresh.post("/api/clock", json={"now": "2026-11-04"}).json() == {"now": "2026-11-04T00:00:00"}
    assert fresh.post("/api/clock", json={"now": "next tuesday"}).status_code == 422


def test_people_overdue_follows_demo_clock(fresh):
    people = {p["name"]: p for p in fresh.get("/api/people").json()}
    assert set(people) == {"Ananya", "Priya", "Rahul"}
    assert all(p["overdue"] == 0 and p["open_tasks"] == 1 for p in people.values())

    fresh.post("/api/clock", json={"now": "2026-11-04T09:00:00"})  # onboarding was due 3 Nov
    people = {p["name"]: p for p in fresh.get("/api/people").json()}
    assert people["Ananya"]["overdue"] == 1 and people["Rahul"]["overdue"] == 0


def test_patch_task(fresh):
    r = fresh.patch("/api/tasks/tsk_m1_testflight", json={"status": "done"})
    assert r.status_code == 200 and r.json()["status"] == "done"
    assert {p["name"]: p["open_tasks"] for p in fresh.get("/api/people").json()}["Rahul"] == 0
    assert fresh.patch("/api/tasks/tsk_nope", json={"status": "done"}).status_code == 404
    assert fresh.patch("/api/tasks/tsk_m1_testflight", json={"status": "pending"}).status_code == 422


def test_task_filters(fresh):
    assert [t["id"] for t in fresh.get("/api/tasks", params={"owner": "Rahul"}).json()] == ["tsk_m1_testflight"]
    assert fresh.get("/api/tasks", params={"project": "Nope"}).json() == []


def test_decision_graph_before_any_supersede(fresh):
    g = fresh.get("/api/decisions/graph", params={"project": "Pocket"}).json()
    assert len(g["nodes"]) == 3 and g["edges"] == []
    assert all(n["meeting_title"] == "Pocket v1 planning sync" and n["status"] == "active" for n in g["nodes"])


def test_include_superseded_flag(fresh):
    # No superseded decisions exist yet; both views agree. (Supersede lineage is covered in Phase 6.)
    a = fresh.get("/api/decisions", params={"project": "Pocket"}).json()
    b = fresh.get("/api/decisions", params={"project": "Pocket", "include_superseded": "true"}).json()
    assert a == b


def test_responses_match_contract_types(fresh):
    from app import schemas

    for d in fresh.get("/api/decisions").json():
        schemas.Decision.model_validate(d)
    for t in fresh.get("/api/tasks").json():
        schemas.Task.model_validate(t)
    for m in fresh.get("/api/meetings").json():
        schemas.Meeting.model_validate(m)


def test_ids_are_prefixed():
    import pytest

    from app.ids import new_id

    i = new_id("dec")
    assert i.startswith("dec_") and len(i) == 12
    with pytest.raises(ValueError):
        new_id("decision")

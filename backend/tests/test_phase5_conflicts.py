"""Phase 5: memory retrieval + conflict detection (LLM post-processing and deterministic checks)."""

import json

import pytest

from app.agents import conflict_detector as cd
from app.agents import memory_retriever as mr
from app.models import Task
from app.services import embeddings

MEETING = {"id": "mtg_x", "project": "Pocket", "title": "Debrief", "date": "2026-10-31",
           "speaker": "Priya", "source_type": "voice"}


def dec(id_, topic, statement, made_by="Priya"):
    return {"id": id_, "topic_key": topic, "statement": statement, "made_by": made_by, "meeting_id": "mtg_x",
            "date": "2026-10-31", "status": "pending", "superseded_by": None, "rationale": None, "source_quote": ""}


def task(id_, owner, due, title="Thing"):
    return {"id": id_, "title": title, "owner": owner, "due_date": due, "raw_due_phrase": "", "status": "pending",
            "source_quote": "", "meeting_id": "mtg_x", "tracker_url": None, "reminder_sent": False}


# ---------------------------------------------------------------- retrieval

def test_same_topic_always_retrieved_plus_similar(fresh):
    related = mr.find_related("Pocket", [dec("dec_n1", "platform_scope", "Android is included in v1")])
    hits = related["dec_n1"]
    assert hits[0]["decision"]["id"] == "dec_m1_platform" and hits[0]["why"] == "same_topic"
    assert all(h["decision"]["status"] == "active" for h in hits)


def test_unrelated_new_topic_finds_nothing_similar(fresh):
    related = mr.find_related("Pocket", [dec("dec_n1", "office_snacks", "We will order more oat milk")])
    assert related["dec_n1"] == []


def test_retrieval_degrades_to_topic_key_without_embeddings(fresh, monkeypatch):
    monkeypatch.setattr(embeddings, "vectors_for", lambda s, items: {})
    monkeypatch.setattr(embeddings, "embed", lambda texts: None)
    related = mr.find_related("Pocket", [dec("dec_n1", "launch_date", "Launch is 28 Nov"),
                                         dec("dec_n2", "brand_new", "Something else")])
    assert [h["decision"]["id"] for h in related["dec_n1"]] == ["dec_m1_launch"]
    assert related["dec_n2"] == []


def test_embeddings_are_cached_in_sqlite(fresh):
    from sqlmodel import Session

    from app.db import get_engine
    from app.models import Embedding

    mr.find_related("Pocket", [dec("dec_n1", "launch_date", "Launch is 28 Nov")])
    with Session(get_engine()) as s:
        assert s.get(Embedding, "dec_m1_launch") is not None


def test_other_projects_are_not_memory(fresh):
    assert mr.find_related("Acme", [dec("dec_n1", "launch_date", "Launch is 28 Nov")]) == {"dec_n1": []}


# ---------------------------------------------------------------- LLM post-processing

def _setup(fresh_client):
    new = [dec("dec_n1", "platform_scope", "Android in v1", "Rahul"), dec("dec_n2", "launch_date", "Launch 28 Nov")]
    related = mr.find_related("Pocket", new)
    open_tasks = cd._open_tasks("Pocket")
    msgs, n, p, t, past = cd.build_messages(new, related, open_tasks, MEETING)
    return new, related, open_tasks, msgs, n, p, t, past


def test_prompt_uses_labels_not_ids(fresh):
    new, related, open_tasks, msgs, n, p, t, past = _setup(fresh)
    text = msgs[1][1]
    assert "N1 vs P1" in text and "T1 Ananya" in text
    assert "dec_n1" not in text and "tsk_m1_onboarding" not in text  # generated IDs never reach the prompt


def test_judgements_map_back_and_bad_ones_are_dropped(fresh):
    new, related, open_tasks, msgs, n, p, t, past = _setup(fresh)
    p_platform = next(lbl for pid, lbl in p.items() if pid == "dec_m1_platform")
    p_launch = next(lbl for pid, lbl in p.items() if pid == "dec_m1_launch")
    t_onboarding = next(lbl for tid, lbl in t.items() if tid == "tsk_m1_onboarding")
    out = cd.ConflictOut(judgements=[
        cd.Judgement(new_ref="N1", past_ref=p_platform, verdict="reversal", severity="high", explanation="e",
                     suggested_resolution="r", affected_task_refs=[t_onboarding, "T99"]),
        cd.Judgement(new_ref="N1", past_ref=p_platform, verdict="reversal", severity="high", explanation="dup",
                     suggested_resolution="r", affected_task_refs=[]),
        cd.Judgement(new_ref="N2", past_ref=p_launch, verdict="none", severity="low", explanation="x",
                     suggested_resolution="", affected_task_refs=[]),
        cd.Judgement(new_ref="N9", past_ref="P9", verdict="reversal", severity="high", explanation="ghost",
                     suggested_resolution="", affected_task_refs=[]),
    ])
    conflicts = cd.semantic_conflicts(out, new_decisions=new, related=related, open_tasks=open_tasks,
                                      n_labels=n, p_labels=p, t_labels=t, past=past)
    assert len(conflicts) == 1
    c = conflicts[0]
    assert c["id"].startswith("cfl_") and c["new_item_id"] == "dec_n1" and c["old_decision"]["id"] == "dec_m1_platform"
    assert [x["id"] for x in c["affected_tasks"]] == ["tsk_m1_onboarding"]


# ---------------------------------------------------------------- deterministic checks

def _open(*tasks):
    return [Task(project="Pocket", meeting_id="mtg_m1", status="todo", **t) for t in tasks]


def test_task_due_after_new_launch_date_collides():
    new_decisions = [dec("dec_n2", "launch_date", "Launch date is November 28th, 2026")]
    conflicts = cd.deterministic_conflicts([task("tsk_a", "Rahul", "2026-12-02", "Press kit")], new_decisions, [], MEETING)
    assert [(c["type"], c["severity"], c["new_item_id"]) for c in conflicts] == [("deadline_collision", "medium", "tsk_a")]
    assert "after the launch on 2026-11-28" in conflicts[0]["explanation"]


def test_existing_task_after_launch_collides_with_launch_from_memory(fresh):
    existing = _open({"id": "tsk_old", "title": "Late thing", "owner": "Priya", "due_date": "2026-11-25"})
    conflicts = cd.deterministic_conflicts([], [], existing, MEETING)  # memory launch = 20 Nov
    assert [c["new_item_id"] for c in conflicts] == ["tsk_old"]
    assert conflicts[0]["old_decision"]["id"] == "dec_m1_launch"


def test_new_task_due_before_meeting_is_late_on_arrival(fresh):
    conflicts = cd.deterministic_conflicts([task("tsk_a", "Ananya", "2026-10-29")], [], [], MEETING)
    assert conflicts[0]["type"] == "deadline_collision" and conflicts[0]["old_decision"] is None
    assert "late on arrival" in conflicts[0]["explanation"]


def test_overload_counts_new_and_existing_tasks(fresh):
    existing = _open({"id": "tsk_e1", "title": "A", "owner": "Rahul", "due_date": "2026-11-10"},
                     {"id": "tsk_e2", "title": "B", "owner": "Rahul", "due_date": "2026-11-10"})
    conflicts = cd.deterministic_conflicts([task("tsk_n", "Rahul", "2026-11-10")], [], existing, MEETING)
    over = [c for c in conflicts if c["type"] == "overload"]
    assert len(over) == 1 and over[0]["severity"] == "low" and over[0]["new_item_id"] == "tsk_n"
    assert len(over[0]["affected_tasks"]) == 3 and "Rahul has 3 tasks due on 2026-11-10" in over[0]["explanation"]


def test_existing_overload_alone_is_not_this_debriefs_conflict(fresh):
    existing = _open(*({"id": f"tsk_e{i}", "title": "X", "owner": "Rahul", "due_date": "2026-11-10"} for i in range(3)))
    assert [c for c in cd.deterministic_conflicts([], [], existing, MEETING) if c["type"] == "overload"] == []


def test_trace_message():
    assert cd.describe({"conflicts": [{"severity": "high"}, {"severity": "high"}, {"severity": "medium"}]}) == \
        "Found 3 conflicts (2 high, 1 medium)"
    assert cd.describe({"conflicts": []}) == "No conflicts with past decisions"


# ---------------------------------------------------------------- end to end on recordings

def _review(client, name, title):
    from app.config import BACKEND_DIR

    client.post("/api/demo/reset")
    body = {"project": "Pocket", "title": title, "date": "2026-10-31", "speaker": "Priya", "source_type": "voice",
            "text": (BACKEND_DIR / "seed" / f"{name}.txt").read_text()}
    tid = client.post("/api/ingest", json=body).json()["thread_id"]
    with client.stream("GET", f"/api/runs/{tid}/stream?until=review") as s:
        for line in s.iter_lines():
            if line.startswith("data:"):
                e = json.loads(line[5:])
                assert e["type"] != "error", e["message"]
                if e["type"] == "review_ready":
                    return e["payload"]


def test_agreeing_debrief_has_zero_conflicts(client):
    review = _review(client, "debrief_agree", "Standup update")
    assert review["conflicts"] == []
    assert {d["topic_key"] for d in review["decisions"]} == {"platform_scope", "launch_date", "payments_provider"}


@pytest.mark.parametrize("topic,severity", [("platform_scope", "high"), ("payments_provider", "high"),
                                            ("launch_date", "medium")])
def test_debrief2_severities_follow_the_rules(client, topic, severity):
    review = _review(client, "debrief2", "Investor sync debrief")
    c = next(c for c in review["conflicts"] if c["old_decision"] and c["old_decision"]["topic_key"] == topic)
    assert c["type"] == "reversal" and c["severity"] == severity
    assert c["explanation"] and c["suggested_resolution"]


def test_android_reversal_flags_ananyas_onboarding(client):
    review = _review(client, "debrief2", "Investor sync debrief")
    c = next(c for c in review["conflicts"] if c["old_decision"]["topic_key"] == "platform_scope")
    assert "tsk_m1_onboarding" in [t["id"] for t in c["affected_tasks"]]

"""The guided example on the home page: one spoken update, one clear conflict. Runs on its saved recordings."""

import json

import pytest

MEETING = {"project": "Pocket", "title": "Launch date update", "date": "2026-10-31",
           "speaker": "Priya", "source_type": "voice"}


@pytest.fixture(scope="module")
def review(client, seed_dir):
    assert client.post("/api/demo/reset").status_code == 200
    r = client.post("/api/ingest", json={**MEETING, "text": (seed_dir / "simple.txt").read_text()})
    assert r.status_code == 200, r.text
    with client.stream("GET", f"/api/runs/{r.json()['thread_id']}/stream?until=review") as s:
        for line in s.iter_lines():
            if line.startswith("data:"):
                event = json.loads(line[5:].strip())
                if event["type"] == "error":
                    pytest.fail(event["message"])
                if event["type"] == "review_ready":
                    return event["payload"]
    pytest.fail("no review_ready")


def test_one_decision_one_task_one_conflict(review):
    assert [d["statement"] for d in review["decisions"]] == ["Public launch is moved to 28 November 2026"]
    assert [(t["owner"], t["due_date"]) for t in review["tasks"]] == [("Rahul", "2026-11-02")]
    assert len(review["conflicts"]) == 1
    conflict = review["conflicts"][0]
    assert conflict["old_decision"]["statement"] == "Public launch is 20 Nov 2026"
    assert conflict["new_item_id"] == review["decisions"][0]["id"]
    assert [t["title"] for t in conflict["affected_tasks"]] == ["Write landing page copy"]


def test_only_the_landing_page_moves(review):
    assert [(r["task"]["title"], r["proposal"]["due_date"]) for r in review["ripples"]] == [
        ("Write landing page copy", "2026-11-14")]
    assert [h["person"] for h in review["heads_up"]] == ["Priya"]


def test_dates_in_the_clean_text_are_right(review):
    assert "2026-11-20" in review["clean_text"] and "2026-11-28" in review["clean_text"]
    assert "2026-11-25" not in review["clean_text"]

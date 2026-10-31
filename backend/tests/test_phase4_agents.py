"""Phase 4: deterministic post-processing of the normalizer and extractor (no LLM involved)."""

from app.agents import extractor, normalizer
from app.agents.extractor import DecisionOut, ExtractorOut, TaskOut
from app.agents.normalizer import CorrectionOut, NormalizerOut

MEETING = {"id": "mtg_x", "project": "Pocket", "title": "Debrief", "date": "2026-10-31",
           "speaker": "Priya", "source_type": "voice"}
RAW = ("so um Rahul said Android is back in for v1. Ananya will redo onboarding by, uh, next Wednesday. "
       "and I'll send the investor update on Monday. someone should look at analytics.")


def test_fillers_merge_into_one_summary_line_first():
    out = NormalizerOut(clean_text="Clean.", corrections=[
        CorrectionOut(original="um, uh", resolved="", kind="filler"),
        CorrectionOut(original="next Wednesday", resolved="Wednesday 2026-11-04", kind="date_resolution"),
        CorrectionOut(original="so, uh, like", resolved="", kind="filler"),
    ])
    res = normalizer.postprocess(out, RAW, "2026-10-31")
    fillers = [c for c in res["corrections"] if c["kind"] == "filler"]
    assert fillers == [{"original": "um, uh, so, like", "resolved": "", "kind": "filler"}]
    assert res["corrections"][0]["kind"] == "filler"


def test_wrong_llm_date_is_overridden():
    out = NormalizerOut(clean_text="x", corrections=[
        CorrectionOut(original="next Wednesday", resolved="Wednesday 2026-11-11", kind="date_resolution"),
        CorrectionOut(original="Monday", resolved="Monday", kind="date_resolution"),
    ])
    res = normalizer.postprocess(out, RAW, "2026-10-31")
    assert [c["resolved"] for c in res["corrections"]] == ["Wednesday 2026-11-04", "Monday 2026-11-02"]


def test_self_correction_gets_iso_date_appended():
    out = NormalizerOut(clean_text="x", corrections=[
        CorrectionOut(original="December 1st, no wait, November 28th", resolved="November 28th", kind="self_correction")])
    assert normalizer.postprocess(out, RAW, "2026-10-31")["corrections"][0]["resolved"] == "November 28th (2026-11-28)"


def test_empty_clean_text_falls_back_to_raw():
    assert normalizer.postprocess(NormalizerOut(clean_text="  ", corrections=[]), RAW, "2026-10-31")["clean_text"] == RAW


def test_transcripts_get_the_light_prompt():
    voice = normalizer.build_messages(RAW, "2026-10-31", "Priya", "voice")[0][1]
    transcript = normalizer.build_messages("Priya: hi", "2026-10-31", "Priya", "transcript")[0][1]
    assert "Keep EVERY speaker turn" in transcript and "Keep EVERY speaker turn" not in voice


def _extract(**kw):
    out = ExtractorOut(
        decisions=[DecisionOut(topic_key="Platform Scope", statement=" Android is in v1 ", made_by="rahul",
                               rationale="", source_quote="Rahul said Android is back in for v1")],
        tasks=[
            TaskOut(title="Redo onboarding", owner="Ananya", due_date="2026-11-11",
                    raw_due_phrase="by, uh, next Wednesday", source_quote="Ananya will redo onboarding", depends_on_topic=None),
            TaskOut(title="Send investor update", owner="I", due_date=None, raw_due_phrase="on Monday",
                    source_quote="Priya sends the investor update Monday", depends_on_topic=None),
            TaskOut(title="Look at analytics", owner=None, due_date=None, raw_due_phrase="",
                    source_quote="someone should look at analytics.", depends_on_topic=None),
        ], **kw)
    return extractor.postprocess(out, raw_text=RAW, meeting=MEETING, people=["Ananya", "Priya", "Rahul"])


def test_decisions_get_ids_pending_status_and_normalized_fields():
    d = _extract()["decisions"][0]
    assert d["id"].startswith("dec_") and d["status"] == "pending" and d["superseded_by"] is None
    assert d["topic_key"] == "platform_scope" and d["statement"] == "Android is in v1"
    assert d["made_by"] == "Rahul" and d["rationale"] is None
    assert d["meeting_id"] == "mtg_x" and d["date"] == "2026-10-31"


def test_due_dates_are_checked_and_I_means_the_speaker():
    tasks = _extract()["tasks"]
    assert tasks[0]["due_date"] == "2026-11-04"           # LLM said 11-11; resolver wins
    assert tasks[0]["raw_due_phrase"] == "by, uh, next Wednesday"
    assert tasks[1]["owner"] == "Priya" and tasks[1]["due_date"] == "2026-11-02"
    assert all(t["status"] == "pending" and t["id"].startswith("tsk_") for t in tasks)


def test_quotes_are_real_words_from_the_raw_text():
    res = _extract()
    assert res["tasks"][1]["source_quote"] == "and I'll send the investor update on Monday."  # paraphrase snapped
    for item in res["decisions"] + res["tasks"]:
        assert item["source_quote"] in RAW


def test_missing_owner_and_date_become_questions():
    res = _extract()
    analytics = res["tasks"][2]
    assert analytics["owner"] == "" and analytics["due_date"] is None
    qs = [(q["item_id"], q["field"]) for q in res["questions"]]
    assert qs == [(analytics["id"], "owner"), (analytics["id"], "due_date")]
    assert res["questions"][0]["prompt"] == "Who owns “Look at analytics”?"


def test_extractor_prompt_carries_memory_and_both_texts():
    msgs = extractor.build_messages("clean", "2026-10-31", "Priya", ["Priya", "Rahul"],
                                    [("platform_scope", "v1 is iOS only")], raw_text="raw words")
    assert "platform_scope: v1 is iOS only" in msgs[0][1] and "KNOWN PEOPLE: Priya, Rahul" in msgs[0][1]
    assert "CLEANED TEXT:\nclean" in msgs[1][1] and "ORIGINAL WORDS:\nraw words" in msgs[1][1]


def test_memory_context_is_stable_and_project_scoped(fresh):
    people, existing = extractor.memory_context("Pocket", "Priya")
    assert people == ["Ananya", "Priya", "Rahul"]
    assert [k for k, _ in existing] == ["launch_date", "payments_provider", "platform_scope"]
    assert extractor.memory_context("Other", "Zoe") == (["Zoe"], [])


def test_trace_messages():
    assert extractor.describe({"decisions": [1, 2, 3], "tasks": [1], "questions": [1, 2]}) == \
        "Found 3 decisions and 1 task; 2 questions for you"
    assert normalizer.describe({"corrections": [
        {"kind": "filler", "original": "um, uh"}, {"kind": "digression", "original": "x"}]}) == \
        "Cut 1 digression, removed 2 fillers"


def test_unrecorded_input_without_groq_fails_with_a_clear_retryable_error(fresh):
    import json
    tid = fresh.post("/api/ingest", json={**{k: MEETING[k] for k in ("project", "title", "date", "speaker", "source_type")},
                                           "text": "a brand new debrief nobody recorded"}).json()["thread_id"]
    with fresh.stream("GET", f"/api/runs/{tid}/stream?until=review") as s:
        events = [json.loads(line[5:]) for line in s.iter_lines() if line.startswith("data:")]
    err = events[-1]
    assert err["type"] == "error" and err["agent"] == "normalizer"
    assert "no replay recording" in err["message"] and err["payload"]["retryable"] is True

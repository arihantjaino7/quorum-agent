from app.services.quotes import sentences, snap

RAW = ("okay so um quick debrief. so basically Rahul said the investors really want Android at launch, "
       "so Android is back in for v1. Ananya is going to redo the onboarding for Android, she said she can have "
       "it by, uh, next Wednesday. and I'll send the investor update on Monday.")


def test_verbatim_quote_returns_exact_span():
    q, changed = snap("Ananya is going to redo the onboarding for Android", RAW)
    assert q == "Ananya is going to redo the onboarding for Android" and changed is False


def test_case_and_spacing_differences_snap_to_source_span():
    q, changed = snap("ANANYA is going  to redo\nthe onboarding", RAW)
    assert q == "Ananya is going to redo the onboarding" and changed is True


def test_paraphrase_snaps_to_closest_sentence():
    q, changed = snap("Priya will send the investor update Monday", RAW)
    assert q == "and I'll send the investor update on Monday." and changed is True


def test_transcript_speaker_labels_are_not_quoted():
    assert sentences("Priya: Decision: v1 is iOS only.\nRahul: Agreed.") == ["Decision: v1 is iOS only.", "Agreed."]

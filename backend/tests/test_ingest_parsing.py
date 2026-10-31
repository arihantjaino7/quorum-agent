from pathlib import Path

import pytest

from app.services.ingest_parsing import (
    ParsedTranscript, UnsupportedFormat, parse_file, parse_srt, parse_text, parse_vtt,
)


def test_plain_speaker_lines_keep_first_appearance_order():
    assert parse_text("Priya: Hello.\nRahul: Hi.\nPriya: Welcome.") == ParsedTranscript(
        "Priya: Hello.\nRahul: Hi.\nPriya: Welcome.", ["Priya", "Rahul"]
    )


def test_uppercase_names_and_roles():
    parsed = parse_text("PRIYA (PM): Start.\nRahul Jain (Eng lead): Ready.")
    assert parsed.text == "PRIYA: Start.\nRahul Jain: Ready."
    assert parsed.speakers == ["PRIYA", "Rahul Jain"]


def test_unlabelled_lines_continue_the_previous_turn():
    assert parse_text("Priya: This is\na single turn.\n\nStill Priya.\nRahul: Done.").text == (
        "Priya: This is a single turn. Still Priya.\nRahul: Done."
    )


def test_leading_unattributed_text_has_no_invented_speaker():
    parsed = parse_text("Opening remarks.\nA second line.\nPriya: Start.")
    assert parsed.text == "Opening remarks. A second line.\nPriya: Start."
    assert parsed.speakers == ["Priya"]


@pytest.mark.parametrize("stamp", ["[00:01:02]", "00:01", "00:01:02", "[00:01:02.500]"])
def test_text_timestamps_are_stripped(stamp):
    assert parse_text(f"{stamp} Priya: Hello.").text == "Priya: Hello."


def test_prose_and_invalid_names_do_not_create_speakers():
    parsed = parse_text("Note: Keep this.\nPriya: Yes.\nSummary: Still prose.\nSpeaker 2: Not a name.\nrahul: lowercase.")
    assert parsed.speakers == ["Priya"]
    assert parsed.text == "Note: Keep this.\nPriya: Yes. Summary: Still prose. Speaker 2: Not a name. rahul: lowercase."


def test_name_length_and_word_limits():
    parsed = parse_text("A B C D: prose\nABCDEFGHIJKLMNOPQRSTUVWXYZABCDE: prose\nMary Jane: Okay.")
    assert parsed.speakers == ["Mary Jane"]


def test_unicode_and_hyphenated_person_names():
    parsed = parse_text("Élodie: Salut.\nMary-Jane O’Neil: Hello.")
    assert parsed.speakers == ["Élodie", "Mary-Jane O’Neil"]


def test_vtt_voice_tags_merge_consecutive_cues():
    parsed = parse_vtt("""WEBVTT

first-cue
00:00.000 --> 00:02.000 align:start
<v Priya>Hello <c.emphasis>team</c>.</v>

second-cue
00:02.000 --> 00:04.000
<v Priya><i>Let’s</i> begin.</v>

00:04.000 --> 00:06.000
<v Rahul>Ready.</v>
""")
    assert parsed == ParsedTranscript("Priya: Hello team. Let’s begin.\nRahul: Ready.", ["Priya", "Rahul"])


def test_vtt_skips_metadata_and_inline_timestamp_tags():
    parsed = parse_vtt("""WEBVTT A meeting
Kind: captions

NOTE A private annotation
Do not include this.

STYLE
::cue { color: white; }

REGION
id: region1

cue-1
00:00:01.000 --> 00:00:03.000
Priya: <00:00:01.500><b>Hello</b> &amp; welcome.
""")
    assert parsed == ParsedTranscript("Priya: Hello & welcome.", ["Priya"])


def test_multiple_voice_tags_in_one_cue():
    parsed = parse_vtt("WEBVTT\n\n00:00.000 --> 00:02.000\n<v Priya>Hi.</v><v Rahul>Hello.</v>")
    assert parsed.text == "Priya: Hi.\nRahul: Hello."


def test_srt_strips_indices_timings_and_html_and_merges():
    parsed = parse_srt("""1
00:00:00,000 --> 00:00:02,000
Priya: <b>Hello</b> team.

2
00:00:02,000 --> 00:00:04,000
Priya: Begin.

3
00:00:04,000 --> 00:00:06,000
Rahul: Yes.
And one more thing.
""")
    assert parsed == ParsedTranscript("Priya: Hello team. Begin.\nRahul: Yes. And one more thing.", ["Priya", "Rahul"])


def test_subtitle_cue_without_a_speaker_remains_unattributed():
    parsed = parse_srt("1\n00:00:00,000 --> 00:00:01,000\nPriya: Hi.\n\n2\n00:00:01,000 --> 00:00:02,000\nUnattributed words.")
    assert parsed.text == "Priya: Hi.\nUnattributed words."


@pytest.mark.parametrize("parser", [parse_text, parse_vtt, parse_srt])
def test_empty_input(parser):
    assert parser(" \r\n\t\r\n") == ParsedTranscript("", [])


@pytest.mark.parametrize("extension", [".txt", ".MD", ".VTT", ".SRT"])
def test_file_dispatch_bom_and_crlf(extension):
    raw = "Priya:   Hello\t team.\r\n"
    if extension.lower() in {".vtt", ".srt"}:
        raw = "00:00:00,000 --> 00:00:02,000\r\n" + raw
        raw = ("WEBVTT\r\n\r\n" if extension.lower() == ".vtt" else "1\r\n") + raw
    assert parse_file(f"meeting{extension}", b"\xef\xbb\xbf" + raw.encode()).text == "Priya: Hello team."


def test_unsupported_extension_lists_all_supported_formats():
    with pytest.raises(UnsupportedFormat) as error:
        parse_file("meeting.mp3", b"\xff")
    for extension in (".txt", ".md", ".vtt", ".srt"):
        assert extension in str(error.value)


@pytest.mark.parametrize("extension", ["vtt", "srt"])
def test_samples_match_the_original_meeting(extension):
    seed = Path(__file__).resolve().parent.parent / "seed"
    original = parse_text((seed / "meeting1.txt").read_text(encoding="utf-8"))
    sample = seed / "samples" / f"meeting1.{extension}"
    parsed = parse_file(sample.name, sample.read_bytes())
    assert parsed.speakers == ["Priya", "Rahul", "Ananya"]
    assert parsed == original

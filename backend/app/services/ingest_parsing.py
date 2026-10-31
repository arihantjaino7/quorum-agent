"""Normalize text and subtitle files into speaker-attributed transcript turns."""

from dataclasses import dataclass
from html import unescape
from pathlib import Path
import re


class UnsupportedFormat(ValueError):
    """The uploaded filename does not identify a supported transcript format."""


@dataclass
class ParsedTranscript:
    text: str
    speakers: list[str]


_TIMESTAMP = re.compile(
    r"^\s*(?:\[\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d+)?\]"
    r"|\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d+)?)(?:\s+|$)"
)
_TIMING_LINE = re.compile(
    r"^\s*(?:\d+:)?\d{1,2}:\d{2}[.,]\d+\s*-->"
)
_PREFIX = re.compile(r"^([^:]+):\s*(.*)$")
_ROLE = re.compile(r"\s*\([^()]*\)\s*$")
_TAGS = re.compile(r"<[^>]*>")
_VOICE = re.compile(r"(<v(?:\.[^\s>]*)?\s+[^>]+>|</v\s*>)", re.IGNORECASE)
_VOICE_OPEN = re.compile(r"<v(?:\.[^\s>]*)?\s+([^>]+)>", re.IGNORECASE)
_PROSE_LABELS = {
    "note", "notes", "summary", "agenda", "action", "actions", "action items",
    "decision", "decisions", "topic", "todo", "warning", "important",
}


def _collapse(text: str) -> str:
    return " ".join(text.split())


def _speaker_name(value: str) -> str | None:
    name = _collapse(_ROLE.sub("", value))
    words = name.split()
    if not name or len(name) > 30 or not 1 <= len(words) <= 3:
        return None
    if name.casefold() in _PROSE_LABELS:
        return None
    if not all(
        word[0].isupper()
        and all(char.isalpha() or char in "-'’" for char in word)
        for word in words
    ):
        return None
    return name


def _attributed(line: str) -> tuple[str | None, str]:
    match = _PREFIX.match(line)
    if match:
        speaker = _speaker_name(match[1])
        if speaker:
            return speaker, _collapse(match[2])
    return None, line


class _Turns:
    def __init__(self) -> None:
        self.lines: list[tuple[str | None, str]] = []
        self.speakers: list[str] = []

    def add(self, speaker: str | None, text: str, *, merge: bool = True) -> None:
        text = _collapse(text)
        if not text:
            return
        if speaker and speaker not in self.speakers:
            self.speakers.append(speaker)
        if merge and self.lines and self.lines[-1][0] == speaker:
            previous_speaker, previous_text = self.lines[-1]
            self.lines[-1] = previous_speaker, f"{previous_text} {text}"
        else:
            self.lines.append((speaker, text))

    def parsed(self) -> ParsedTranscript:
        return ParsedTranscript(
            text="\n".join(f"{speaker}: {text}" if speaker else text for speaker, text in self.lines),
            speakers=self.speakers,
        )


def parse_text(raw: str) -> ParsedTranscript:
    turns = _Turns()
    for raw_line in raw.lstrip("\ufeff").splitlines():
        line = _collapse(_TIMESTAMP.sub("", raw_line))
        if not line:
            continue
        speaker, text = _attributed(line)
        if speaker:
            turns.add(speaker, text, merge=False)
        else:
            previous = turns.lines[-1][0] if turns.lines else None
            turns.add(previous, text)
    return turns.parsed()


def _cue_text(block: str) -> str | None:
    lines = block.splitlines()
    if not lines:
        return None
    # Metadata blocks and cue identifiers are not spoken text.
    if re.match(r"^(?:NOTE|STYLE|REGION)(?:\s|$)", lines[0].strip()):
        return None
    for index, line in enumerate(lines):
        if _TIMING_LINE.match(line):
            return "\n".join(lines[index + 1:])
    return None


def _subtitles(content: str, *, voices: bool) -> ParsedTranscript:
    turns = _Turns()
    content = content.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    for block in re.split(r"\n[ \t]*\n", content):
        cue = _cue_text(block.strip())
        if cue is None:
            continue
        speaker: str | None = None
        voice: str | None = None
        for chunk in _VOICE.split(cue) if voices else [cue]:
            tag = _VOICE_OPEN.fullmatch(chunk) if voices else None
            if tag:
                voice = _speaker_name(unescape(tag[1]))
                speaker = voice
                continue
            if voices and re.fullmatch(r"</v\s*>", chunk, re.IGNORECASE):
                voice = speaker = None
                continue
            for raw_line in chunk.splitlines():
                line = _collapse(unescape(_TAGS.sub("", raw_line)))
                if not line:
                    continue
                prefix, text = _attributed(line)
                if prefix:
                    speaker = voice or prefix
                turns.add(speaker, text)
    return turns.parsed()


def parse_vtt(content: str) -> ParsedTranscript:
    return _subtitles(content, voices=True)


def parse_srt(content: str) -> ParsedTranscript:
    return _subtitles(content, voices=False)


def parse_file(filename: str, data: bytes) -> ParsedTranscript:
    parsers = {".txt": parse_text, ".md": parse_text, ".vtt": parse_vtt, ".srt": parse_srt}
    extension = Path(filename).suffix.lower()
    if extension not in parsers:
        raise UnsupportedFormat(
            f"Unsupported transcript format {extension or '(no extension)'}. "
            "Supported types: .txt, .md, .vtt, .srt."
        )
    return parsers[extension](data.decode("utf-8-sig"))

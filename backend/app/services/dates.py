"""Deterministic date resolver: spoken deadline phrase + meeting date → ISO date.

Used to check and override the LLM's date arithmetic, which is the most likely silent failure.
Rules (identical to the prompts):
- "today" / "tomorrow" / "day after tomorrow"
- "next <weekday>"  → the first such weekday strictly after the meeting date
- "this <weekday>" / bare "<weekday>" → the next such weekday strictly after the meeting date
- "the 20th" / "20th"  → the next 20th on or after the meeting date
- "November 28th" / "Nov 28" / "28 Nov" / "28th of November" → that date; next year if already past
- "next week" → Monday after the meeting week; "end of (the) week" → Friday of the meeting week (or next if past)
- Self-corrections: "December 1st, no wait, November 28th" → the phrase after the last correction marker
Returns None when it can't parse the phrase; the caller then keeps the LLM's answer.
"""

import calendar
import re
from datetime import date, timedelta

WEEKDAYS = {name.lower(): i for i, name in enumerate(calendar.day_name)}
WEEKDAYS.update({name.lower(): i for i, name in enumerate(calendar.day_abbr)})
WEEKDAYS.update({"tues": 1, "weds": 2, "thur": 3, "thurs": 3})
MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
MONTHS.update({name.lower(): i for i, name in enumerate(calendar.month_abbr) if name})
MONTHS["sept"] = 9

_FILLERS = re.compile(r"\b(uh+|um+|er+|erm|like|basically|so|yeah|ok(ay)?)\b", re.I)
_CORRECTION = re.compile(r"\b(?:no wait|no,? wait|actually|i mean|sorry|make that|scratch that|correction)\b", re.I)
_ORD = r"(\d{1,2})(?:st|nd|rd|th)?"
_MONTH = r"(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\.?"
_DAY = r"(" + "|".join(sorted(WEEKDAYS, key=len, reverse=True)) + r")"


def _clean(phrase: str) -> str:
    text = phrase.lower()
    parts = _CORRECTION.split(text)
    if len(parts) > 1:
        text = parts[-1]  # keep what follows the last self-correction
    text = _FILLERS.sub(" ", text)
    return re.sub(r"[^\w\s]", " ", text)


def _month_day(month: int, day: int, base: date) -> date | None:
    try:
        d = date(base.year, month, day)
    except ValueError:
        return None
    if d < base:
        try:
            d = date(base.year + 1, month, day)
        except ValueError:
            return None
    return d


def _next_weekday(base: date, weekday: int) -> date:
    delta = (weekday - base.weekday()) % 7 or 7
    return base + timedelta(days=delta)


def resolve(phrase: str | None, meeting_date: str | date) -> date | None:
    if not phrase or not phrase.strip():
        return None
    base = date.fromisoformat(meeting_date) if isinstance(meeting_date, str) else meeting_date
    text = " " + " ".join(_clean(phrase).split()) + " "

    if m := re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", phrase):  # already ISO
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    if " day after tomorrow " in text:
        return base + timedelta(days=2)
    if " tomorrow " in text:
        return base + timedelta(days=1)
    if " today " in text or " tonight " in text or " eod " in text:
        return base
    if m := re.search(rf"\b{_MONTH}\s+{_ORD}\b", text):  # November 28th
        return _month_day(MONTHS[m.group(1)], int(m.group(2)), base)
    if m := re.search(rf"\b{_ORD}\s+(?:of\s+)?{_MONTH}\b", text):  # 28th of November / 28 Nov
        return _month_day(MONTHS[m.group(2)], int(m.group(1)), base)
    if m := re.search(rf"\bnext\s+{_DAY}\b", text):
        return _next_weekday(base, WEEKDAYS[m.group(1)])
    if m := re.search(rf"\b(?:this\s+|on\s+|by\s+)?{_DAY}\b", text):
        return _next_weekday(base, WEEKDAYS[m.group(1)])
    if re.search(r"\bend of (?:the )?week\b", text):
        friday = base + timedelta(days=(4 - base.weekday()) % 7)
        return friday if friday >= base else friday + timedelta(days=7)
    if re.search(r"\bnext week\b", text):
        return base + timedelta(days=7 - base.weekday())
    if m := re.search(r"\b(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)\b", text):  # the 20th
        day = int(m.group(1))
        y, mo = base.year, base.month
        for _ in range(13):
            try:
                d = date(y, mo, day)
                if d >= base:
                    return d
            except ValueError:
                pass
            mo += 1
            if mo > 12:
                y, mo = y + 1, 1
    return None

"""Shared prompt helpers (date context). Draft prompts for each agent live in that agent's module."""

from datetime import date, timedelta


def date_context(meeting_date: str, days: int = 35) -> str:
    """Meeting date + a calendar of the following weeks, so relative dates resolve reliably."""
    d0 = date.fromisoformat(meeting_date)
    lines = [f"Meeting date: {d0:%A} {d0.isoformat()}.", "Calendar from the meeting date onward:"]
    for i in range(days):
        d = d0 + timedelta(days=i)
        lines.append(f"  {d:%a} {d.isoformat()}" + ("  (meeting day)" if i == 0 else ""))
    return "\n".join(lines)

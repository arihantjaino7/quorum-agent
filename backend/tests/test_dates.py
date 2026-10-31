"""Deterministic date resolver. Meeting date for most cases: Saturday 2026-10-31."""

import pytest

from app.services.dates import resolve

M = "2026-10-31"  # Saturday


@pytest.mark.parametrize("phrase,expected", [
    ("by, uh, next Wednesday", "2026-11-04"),
    ("next Wednesday", "2026-11-04"),
    ("on Monday", "2026-11-02"),
    ("Monday", "2026-11-02"),
    ("by Friday", "2026-11-06"),
    ("this Thursday", "2026-11-05"),
    ("next Saturday", "2026-11-07"),          # strictly after the meeting day
    ("by the 20th", "2026-11-20"),
    ("the 31st", "2026-10-31"),               # on or after the meeting date
    ("by the 3rd", "2026-11-03"),
    ("December 1st, no wait, November 28th", "2026-11-28"),
    ("November 28th", "2026-11-28"),
    ("Nov 28", "2026-11-28"),
    ("28 Nov", "2026-11-28"),
    ("28th of November", "2026-11-28"),
    ("by November 3rd", "2026-11-03"),
    ("tomorrow", "2026-11-01"),
    ("today", "2026-10-31"),
    ("day after tomorrow", "2026-11-02"),
    ("end of the week", "2026-11-06"),
    ("next week", "2026-11-02"),
    ("2026-11-18", "2026-11-18"),
    ("by the 18th", "2026-11-18"),
])
def test_resolves(phrase, expected):
    assert str(resolve(phrase, M)) == expected


def test_past_month_day_rolls_to_next_year():
    assert str(resolve("January 5th", M)) == "2027-01-05"


def test_month_rollover_for_day_of_month():
    assert str(resolve("the 5th", "2026-10-31")) == "2026-11-05"


@pytest.mark.parametrize("phrase", ["", "soon", "asap", "when we can", None, "February 30th"])
def test_unparseable_returns_none(phrase):
    assert resolve(phrase, M) is None

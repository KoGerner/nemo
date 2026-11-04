"""The one public duration reader: how nemo turns a written duration into minutes.

It lived privately in the referee, and every other caller — `nemo.next_step` and the skin, fifteen
times — reached across that seam for it. Ticket 130's nudge ('<' a minute under, '>' and '≥' a
minute past) changed the reading and, with it, the skin's `same_figure` and `tighter`, and nothing
named that dependency. One public name with its own test file makes the next such change visible
where every caller is (ticket 218).

`minutes`, `upper_edge` (with its `BAND`) and `worst_case` are the public names here. The tables
and the comparator are private: a caller that needs another comparison helper is asking for a rule
this module does not state yet, and the ticket that needs it adds it here rather than reading the
tables out (ticket 240 added the band's two, ADR-0039).

**Nothing here reaches the disk, the clock or the network**, and it imports nothing of this package.
"""

from __future__ import annotations

import re

_DURATION = re.compile(r"^(\d+(?:\.\d+)?)\s*(?:[-–]\s*\d+(?:\.\d+)?)?\s*([a-z]+)$")
_TRAILING_NOTE = re.compile(r"\s*\([^)]*\)\s*$")
_DUR_UNITS = {
    "min": 1, "mins": 1, "minute": 1, "minutes": 1, "m": 1,
    "h": 60, "hr": 60, "hrs": 60, "hour": 60, "hours": 60,
    "d": 1440, "day": 1440, "days": 1440,
    "week": 10080, "weeks": 10080,
}


def minutes(value: object) -> int | None:
    """A duration in minutes, or None when it cannot be compared at all.

    A band ('2-4 hours') is read at its lower bound: the deadline is where the band starts.
    '< 8 h' is just under 8 hours, one minute less, so it fits inside an 8-hour limit (ADR-0030
    decision 1). '>168 h' (and '≥') is just past 168 hours, one minute more, so a 168 h target is
    inside it (14_nemo_check, t130 follow-up). '≈', '~' (about N) and '≤' (at most N) read N itself.
    """
    if not value:
        return None
    raw = str(value).strip()
    text = _TRAILING_NOTE.sub("", raw).lstrip("<>≤≥≈~ ").strip().lower()
    match = _DURATION.match(text)
    if match is None or match.group(2) not in _DUR_UNITS:
        return None
    return _nudged(raw, int(float(match.group(1)) * _DUR_UNITS[match.group(2)]))


def _nudged(raw: str, minutes: int) -> int:
    """`minutes`' comparator: '<' a minute under, '>' and '≥' a minute past, else as read."""
    if minutes and raw.startswith("<"):
        return minutes - 1
    return minutes + 1 if raw.startswith((">", "≥")) else minutes


#: A band, "0–4 h" or "2-6 hours": an MTPD (t74) and a recovery target (ADR-0039) count at its
#: upper edge.
BAND = re.compile(r"^(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)\s*([a-z]+)$")


def upper_edge(value: object) -> str | None:
    """A band's upper edge as a duration ("0–4 h" → "4 h"); None for anything else (t74, ADR-0039).

    It lived in `nemo.handover`; ticket 240 moved it here because the referee, below handover,
    holds a banded recovery target at its upper edge too."""
    text = _TRAILING_NOTE.sub("", str(value).strip()).lower()
    match = BAND.match(text)
    if match is None or match.group(3) not in _DUR_UNITS:
        return None
    return f"{match.group(2)} {match.group(3)}"


def worst_case(value: object) -> int | None:
    """A duration in minutes with a band read at its upper edge: what a target or an MTPD is held
    at when one is compared to the other (t74, ADR-0039). Anything else reads as `minutes` does."""
    return minutes(upper_edge(value) or value)

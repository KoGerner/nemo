"""The next step: which activity nemo offers under a free-chat answer (tickets 108 and 252).

Under a free-chat answer the skin draws at most one tap for an activity. nemo chooses the activity
and the model writes nothing about it (M13). The rule, in the order the check session reads it:

1. **Touched.** An activity is touched when the turn read one of its own files (its interview,
   its run, its documents) or named it (the activity a reading call was about, or one his own
   typed line names by its whole name, ticket 252). A room-wide read, such as the registers, the
   process map, the method or the file list, touches no activity. With several touched, the one
   with the tighter MTPD wins, then the room's order, the process map's, as the caller hands the
   room in.
2. **None**, when nothing is touched (ticket 252: the owner called the most-urgent fallback,
   "Open access-management?" under almost every answer, "obviously bullshit"), or when the room
   holds no activity.

**Nothing here reaches the disk, the clock or the network.** It never opens anything either. The
tap is only an offer, and the manager decides (rulings B, C and D).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from nemo import duration

#: The minutes an unreadable figure sorts at: after every figure that can be read.
_UNKNOWN = float("inf")


@dataclass(frozen=True)
class Activity:
    """One activity the room holds, in the room's spelling, with the figures on its sheet."""

    name: str
    #: Its own files, relative to the room. A path ending in "/" holds every file under it.
    files: frozenset[str]
    mtpd: str | None
    rto: str | None
    #: The referee's rule: its recovery target is not strictly inside its MTPD.
    gap: bool


@dataclass(frozen=True)
class Turn:
    """What one free-chat turn read (room-relative paths) and which activities it named."""

    read: tuple[str, ...] = ()
    named: tuple[str, ...] = ()


def _owns(activity: Activity, path: str) -> bool:
    return any(path == f or (f.endswith("/") and path.startswith(f)) for f in activity.files)


def touched(turn: Turn, room: Sequence[Activity]) -> list[Activity]:
    """The activities this turn touched, each once, in the room's order."""
    return [a for a in room
            if a.name in turn.named or any(_owns(a, path) for path in turn.read)]


def _minutes(figure: str | None) -> float:
    minutes = duration.minutes(figure)
    return _UNKNOWN if minutes is None else minutes


def next_step(turn: Turn, room: Sequence[Activity]) -> str | None:
    """The activity to offer under this turn's answer, or None when the turn touched none."""
    hit = touched(turn, room)
    if hit:
        return min(enumerate(hit), key=lambda ia: (_minutes(ia[1].mtpd), ia[0]))[1].name
    return None

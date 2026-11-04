"""The turn file (ADR-0020, ticket 109): one line per turn, one file per room, one writer.

Every caller hands its turn here: a scripted walk, a chat batch and the live phone app. The writer
adds what every turn carries, whoever wrote it: a fresh `turn_id`, when it ended (`at`, epoch
seconds, which are UTC), the room, the wording version in play (the tree's commit) and the model
calls the turn made, each as `call` built it. The line is appended whole under one lock, so fifty
rooms written from fifty threads never interleave, and a walk that dies mid-write leaves at most
one broken line, which `read` skips.

**Where.** Under a dot-path in the room, `.turns/`. The chat's room listing hides dot-paths, so the
model never reads nemo's own record of the conversation as the company's files; it is not under
`output/`, where the signed documents live; and the yardstick's room never has one, because only
nemo's rooms are written to.

**Drawn again, never replayed.** When he reopens the link, the skin draws the room's last turns
before its greeting (ticket 118, `past`). That reads the file and writes nothing: no line is added
and none is rewritten, because the export sends each line to Langfuse once, keyed by its turn id.

**Never a gate.** It is a record: nothing in a walk reads it to decide anything. Nothing here makes
a model call or a network call; the export that reads it runs after the walk, outside this package.

The calls wait in a `Calls`, by room, from the moment they return until their turn is written: a
background draft adds its call from its own thread, and the turn that waited on it takes it. The
room travels with every call explicitly; there is no "current turn" anywhere.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, NamedTuple

#: The dot-path in the room, and the file in it.
DIR = ".turns"
NAME = "turns.jsonl"
#: How a call ended. A reply that declines is ANSWERED; only a transport that gave up is FAILED.
ANSWERED = "answered"
FAILED = "failed"
#: How many of the room's last turns are drawn again when he reopens the link (the planner's).
CAP = 50

_WRITING = threading.Lock()
#: A line as written: non-ASCII kept as the manager typed it, and anything JSON cannot hold (a
#: path, a time) as its text. `ensure_ascii=None` would read the same as False, so the choice is
#: made once here rather than as a call argument a mutant could flip without anyone noticing.
_LINE = json.JSONEncoder(ensure_ascii=False, default=str)


def path(room: Path) -> Path:
    """The room's turn file."""
    return room / DIR / NAME


def call(*, lane: str, asked: str, answered: str | None, messages: Any, tools: Any, reply: Any,
         usage: Mapping[str, Any], seconds: float, start: float, purpose: str | None, thread: str,
         attempts: Sequence[Any], error: str | None) -> dict[str, Any]:
    """One model call as the turn file holds it: the messages and tool definitions as sent, the raw
    reply before anything post-processed it (None when the transport gave up), the model asked for
    and the model that answered, the tokens and the billed cost as reported (None when not)."""
    return {"purpose": purpose, "thread": thread, "start": start, "seconds": seconds, "lane": lane,
            "model_asked": asked, "model_answered": answered, "messages": messages, "tools": tools,
            "reply": reply, "usage": dict(usage), "tokens": usage.get("total_tokens"),
            "cost": usage.get("cost"), "outcome": FAILED if error else ANSWERED, "error": error,
            "attempts": list(attempts)}


class Calls:
    """The calls made for each room and not yet written with a turn. Safe across threads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_room: dict[str, list[dict[str, Any]]] = {}

    def add(self, room: Path, entry: dict[str, Any]) -> None:
        with self._lock:
            self._by_room.setdefault(str(room), []).append(entry)

    def take(self, room: Path) -> list[dict[str, Any]]:
        """Every call made for `room` since the last take, oldest first; they are then gone."""
        with self._lock:
            return self._by_room.pop(str(room), [])


def write(room: Path, record: Mapping[str, Any], *, wording: str,
          calls: Sequence[Mapping[str, Any]], index: Path | None = None,
          clock: Callable[[], float] = time.time,
          new_id: Callable[[], str] = lambda: uuid.uuid4().hex) -> dict[str, Any]:
    """Append one turn to the room's turn file and return it as written.

    `record` is the caller's turn; its own `at` is kept when it has one. `index` is a batch file a
    scripted walk keeps beside its scenario and commits: it gets the same line without the calls,
    which stay in the room's file under the same `turn_id`.
    """
    turn = {"at": round(clock(), 1), **record, "turn_id": new_id(), "room": room.name,
            "wording": wording, "calls": list(calls)}
    lines = {path(room): turn}
    if index:
        lines[index] = {k: v for k, v in turn.items() if k != "calls"}
    with _WRITING:
        for target, line in lines.items():
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("ab") as f:
                f.write((_LINE.encode(line) + "\n").encode())
    return turn


def read(file: Path) -> list[dict[str, Any]]:
    """Every whole turn in a turn file. A line that does not parse is skipped, never fatal.

    Split the bytes first and decode inside the try, as `past` does: the writer keeps non-ASCII,
    so a write cut can land between the bytes of one character, and decoding the file whole would
    lose every turn in it rather than the torn line (ticket 210)."""
    turns = []
    for line in file.read_bytes().splitlines():
        try:
            turns.append(json.loads(line.decode()))
        except ValueError:
            continue
    return turns


class Past(NamedTuple):
    """One turn he took part in, as it is drawn again: his words, nemo's reply (None when the lane
    failed and there was none), the turn's cards, and how he took it ("typed", "tapped"; None on a
    line that does not say), since a tap is drawn in the words his phone showed. Ticket 533 (511):
    the stage the answer was at (`answer_stage`, None on a line written before ticket 478), so it
    is drawn again with its label, and the turn's id, which names what it showed."""
    said: str
    reply: str | None
    cards: list[str]
    how: str | None
    stage: int | None = None
    turn_id: str | None = None


def past(room: Path, cap: int = CAP) -> list[Past]:
    """The room's last `cap` turns with words of his, oldest first. The opener is nemo's, not his,
    and is left out; so is a line that cannot be read. No turn file means nothing to draw.

    Read one line at a time and only six fields kept, since one line can hold hundreds of KB of
    calls: the file is never loaded whole."""
    kept: deque[Past] = deque(maxlen=cap)
    try:
        f = path(room).open("rb")
    except FileNotFoundError:
        return []
    with f:
        kept.extend(p for p in map(_his, f) if p is not None)
    return list(kept)


def _his(line: bytes) -> Past | None:
    """One line as `past` keeps it; None when it is not his (the opener) or cannot be read."""
    try:
        turn = json.loads(line)
    except ValueError:
        return None
    if isinstance(turn, dict) and turn.get("said") and turn.get("how") != "opener":
        return Past(turn["said"], turn.get("reply"), turn.get("cards") or [], turn.get("how"),
                    turn.get("answer_stage"), turn.get("turn_id"))
    return None


def his_turns(room: Path, wanted: set[str] | None = None) -> dict[str, dict[str, str]]:
    """His words on each turn of his, by the turn's id, with the day (UTC) the turn ended.

    Ticket 132 (ADR-0030): a chat confirmation is read from here and never from a model call's
    arguments. His words are what he typed, or for a tap the words the tap showed him (`shown`,
    which the caller writes on a tapped turn; a tap drawn in its own words has none, and its
    `said` is those words). `wanted` limits it to those ids; a line naming none of them is not
    parsed, since one line can hold hundreds of KB of calls."""
    try:
        f = path(room).open("rb")
    except FileNotFoundError:
        return {}
    with f:
        return dict(t for t in (_his_turn(line, wanted) for line in f) if t is not None)


def _his_turn(line: bytes, wanted: set[str] | None) -> tuple[str, dict[str, str]] | None:
    """One line as `his_turns` keeps it; None when it is not his, not wanted or cannot be read."""
    if not _names_one(line, wanted):
        return None
    turn = _his_line(line)
    if turn is None or not _is_wanted(turn, wanted):
        return None
    return str(turn.get("turn_id")), _words_and_day(turn)


def _names_one(line: bytes, wanted: set[str] | None) -> bool:
    """Whether the raw line names a wanted id at all, so that no other line is parsed."""
    return wanted is None or any(w.encode() in line for w in wanted)


def _his_line(line: bytes) -> dict[str, Any] | None:
    """The line's turn when it is one of his: readable, a turn, with words, and not the opener."""
    try:
        turn = json.loads(line)
    except ValueError:
        return None
    if isinstance(turn, dict) and turn.get("said") and turn.get("how") != "opener":
        return turn
    return None


def _is_wanted(turn: dict[str, Any], wanted: set[str] | None) -> bool:
    return wanted is None or turn.get("turn_id") in wanted


def _words_and_day(turn: dict[str, Any]) -> dict[str, str]:
    """His words (what a tap showed him, else what he said) and the day (UTC) the turn ended."""
    return {"words": str(turn.get("shown") or turn["said"]),
            "on": time.strftime("%Y-%m-%d", time.gmtime(float(turn.get("at") or "0")))}

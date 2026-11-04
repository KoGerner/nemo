"""What nemo last showed in a room, kept in the room (ticket 533, ADR-0056 rework S2).

The room's focus, its last chart, its drafts and its invitation were each the session's memory
alone, and his phone's reconnect, a reopened link and a restart all start a fresh session on the
same room: after A1 and A2 on production, A3 drew the picker. So each is kept here, in the room
folder, on the one copy that holds the room (ADR-0052), beside the turn file.

**One line per put.** `put` appends a new version of a kind, never rewrites one: `last` is the
newest of a kind (that matches), `get` any version by its id, `on_turn` what a turn showed. The
line is appended whole under one lock, and a write cut short leaves at most one torn line, which
`read` skips, as the turn file's `read` does.

**Where.** Under a dot-path in the room, `.shown/`, so the room listing never serves it to the
model as one of the company's files (`core.room_files`), and outside `output/`.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

#: the dot-path in the room, and the file in it
DIR = ".shown"
NAME = "shown.jsonl"
#: the kinds kept: a chart (its activities, classes, years), the drafts (each by its id, placed
#: or not), the invitation (its slot, the calendar event's id, placed or not), the focus activity
CHART, DRAFTS, INVITATION, FOCUS = "chart", "drafts", "invitation", "focus"
KINDS = (CHART, DRAFTS, INVITATION, FOCUS)
#: a chart's years as the impact chart draws them: last year's record and this year's interview
YEARS = ["last", "this"]

_WRITING = threading.Lock()


def path(room: Path) -> Path:
    """The room's store."""
    return room / DIR / NAME


def read(room: Path) -> list[dict[str, Any]]:
    """Every whole line, oldest first; a torn one is skipped, a room with none has none."""
    try:
        lines = path(room).read_bytes().splitlines()
    except FileNotFoundError:
        return []
    kept = []
    for line in lines:
        try:
            entry = json.loads(line.decode())
        except ValueError:
            continue
        if isinstance(entry, dict):
            kept.append(entry)
    return kept


def put(room: Path, kind: str, value: Mapping[str, Any], *, turn: str = "") -> dict[str, Any]:
    """A new version of `kind`, appended, and returned as written: its id names its kind and
    version, `turn_id` the turn that showed it ("" outside a turn)."""
    if kind not in KINDS:
        raise ValueError(f"not a kind the room keeps: {kind!r}")
    with _WRITING:
        version = 1 + sum(e.get("kind") == kind for e in read(room))
        entry = {"kind": kind, "id": f"{kind}-{version}", "version": version, "turn_id": turn,
                 **value}
        path(room).parent.mkdir(parents=True, exist_ok=True)
        with path(room).open("ab") as f:
            f.write((json.dumps(entry, ensure_ascii=False) + "\n").encode())
    return entry


def last(room: Path, kind: str, **match: Any) -> dict[str, Any] | None:
    """The newest version of `kind` whose fields equal `match`; None where there is none."""
    return next((e for e in reversed(read(room)) if e.get("kind") == kind
                 and all(e.get(k) == v for k, v in match.items())), None)


def get(room: Path, id_: str) -> dict[str, Any] | None:
    """The version with this id, or None."""
    return next((e for e in read(room) if e.get("id") == id_), None)


def on_turn(room: Path, turn: str) -> list[dict[str, Any]]:
    """What the turn with this id showed, in the order it was put."""
    return [e for e in read(room) if turn and e.get("turn_id") == turn]


# ── the drafts: which ones (a digest of their words), each by its id, placed or not ───────────
def digest(what: str, drawn: Any) -> str:
    """Which drafts: what they are for and a digest of their words, so a changed draft is new."""
    return f"{what}:{hashlib.sha256(json.dumps(drawn, default=str).encode()).hexdigest()[:12]}"


def keep_drafts(room: Path, key: str, activity: str | None, names: list[str],
                placed: bool) -> dict[str, Any]:
    """A new version of the drafts `key` names, each by its id (its .eml name), placed or not:
    one tap places all of them or none."""
    return put(room, DRAFTS, {"key": key, "activity": activity,
                              "drafts": [{"id": n, "placed": placed} for n in names]})


def all_placed(room: Path, key: str) -> bool:
    """The last version of the drafts `key` names holds drafts, and every one was placed."""
    kept = last(room, DRAFTS, key=key)
    return bool(kept and kept["drafts"] and all(d["placed"] for d in kept["drafts"]))

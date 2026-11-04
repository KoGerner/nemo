"""The safety core: a path jail, and the two writes that go through it.

Ported from v1's `graph_files._jail` and `bia_run_store`'s compare-and-set — the two properties
that never caused a stall. The write-lane jaws, the save-token slot and the refusal sites around
them are deliberately left behind (ADR-0007); this module refuses two things and nothing else.

The refusal count is the part of that provenance worth carrying next to the code. ADR-0007's
"130 refusal sites" is the count in the *rewrite's* `bia_service.py`; v1's own inventory is 96,
and 216 of the tree's 312 sites were written on 2026-09-01 and 09-02 as a parallel second gate
system. Two days of reflex under deadline pressure, not a year of decay — so it is a live risk
for whoever adds to this module, not a historical curiosity. Add a property, never a jaw.

A record is a JSON object in a room folder. The store owns its `revision` key: a record that is
not there yet is at revision 0, and every accepted write advances the revision by one. A writer
says which revision it read, and loses if the record has moved on.

A room also holds evidence, which is files rather than records — a transcript the manager gave in
the room is one. `write_file` is how those land, and it is here rather than in the caller so that
every path reaching the disk inside a room is jailed by the module that owns the jail.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path

from nemo.record import Record


class PathRefused(Exception):
    """The path resolves outside the room folder."""


#: How much of a saved document may be lost in one write before a human has to decide: half of it.
#: One number, in one place, for every document that goes through this door — a threshold per view
#: is two thresholds a year from now. It is deliberately far from the numbers it exists to catch:
#: v1's gutted capture kept 20% of its bytes and its gutted analysis 15%, while an honest re-render
#: of a record that moved is worth a few percent either way.
SHRINK_FACTOR = 2

#: The mode every file a room holds is left at. A staged file is the writing process's own and
#: arrives 0600; the record, the four views and the graph page are read out of the room by
#: whatever serves them, under another uid, so the mode is restated here rather than inherited
#: from the temp file. It is what an ordinary `write_bytes` under this box's umask always gave.
READABLE_BY_THE_SERVER = 0o644

SHRUNK = ("{document} holds {saved} bytes and what was offered for it is {offered} bytes, which is "
          "less than half of what is there. Nothing has been overwritten: whether the record lost "
          "something it should not have is a human's decision, not this write's.")


class Shrunk(Exception):
    """A document was offered a fraction of its saved bytes. Both counts are in the message.

    Not a heading comparison, on purpose. v1's gate compared the set of `##` headings and a
    stage-2 capture went 10,514 -> 2,099 bytes with every heading intact, so the only thing that
    catches the defect is the thing the defect is made of: the bytes.
    """

    def __init__(self, relative_path: str, saved: int, offered: int) -> None:
        super().__init__(SHRUNK.format(document=relative_path, saved=saved, offered=offered))
        self.saved = saved
        self.offered = offered


#: One lock per room folder, and the dictionary that hands them out. `os.replace` is atomic, but
#: the revision compare in front of it is not part of it: two writers that both read revision N
#: both pass the compare and both replace, and the first one's change is gone with nobody told.
#: One manager has one room, and one process serves the phone — the app is a single `chainlit run`
#: and turns run in its thread pool (`cl.make_async`) — so his double-tap and his second tab are
#: two threads on one room, and a lock in this process is the whole of what that needs. It is not
#: a file lock: two processes on one room is not a shape this product has, and a lock file would be
#: a jaw to unstick at 3am rather than a property (ADR-0007).
#:
#: Reentrant because a writer that holds it writes through `write_record`, which takes it again on
#: the same thread: stage 4's press holds the room from before it reads the run's revision until
#: after it has saved it (ticket 211), and its land and its save are both `write_record`. A plain
#: `threading.Lock` deadlocks there, and a deadlock is a phone that never answers.
_LOCKS: dict[Path, threading.RLock] = {}

#: Held only while a room's lock is handed out, never while a write runs, so a slow write on one
#: room cannot make a writer on another wait.
_HANDING_OUT = threading.Lock()


def room_lock(room_folder: Path) -> threading.RLock:
    """The one lock for this room folder, the same object for every writer that asks for it.

    Keyed on the resolved path, so a room reached through a symlink and the same room reached
    directly are one room rather than two. The dictionary is never pruned: a room is a manager's,
    the phone serves a handful at a time, and a lock is a few dozen bytes.

    It is public because the read-compare-write this guards is not always `write_record`'s: the
    skin appends one line to a room's `_said.json` by reading it, adding to it and writing it
    back, which is the same race in another file (ticket 208, finding B8).
    """
    key = room_folder.resolve()
    with _HANDING_OUT:
        return _LOCKS.setdefault(key, threading.RLock())


class StaleWrite(Exception):
    """The record is no longer at the revision the writer read."""

    def __init__(self, current_revision: int) -> None:
        super().__init__(f"the record is at revision {current_revision}")
        self.current_revision = current_revision


def jailed_path(room_folder: Path, relative_path: str) -> Path:
    """The absolute path of `relative_path` inside `room_folder`, or `PathRefused`.

    Resolved on both sides, so `..`, an absolute path and a symlink out of the room are all the
    same refusal. The room folder itself is not a path anything may write to.
    """
    room_folder = room_folder.resolve()
    target = (room_folder / relative_path).resolve()
    if room_folder not in target.parents:
        raise PathRefused(f"{relative_path!r} resolves outside the room")
    return target


def read_record(room_folder: Path, relative_path: str) -> Record | None:
    """The record as saved, `revision` included, or None if it was never written."""
    return _record_at(jailed_path(room_folder, relative_path))


def write_record(
    room_folder: Path, relative_path: str, record: Record, expected_revision: int
) -> Record:
    """Save `record` iff the room still holds `expected_revision`; return what was saved.

    Reading the revision, comparing it and replacing the file happen under the room's own lock,
    because the compare is what makes the write conditional and `os.replace` does not carry it:
    without the lock two of his tabs both read revision N, both pass, and the first change is
    gone. `room_lock` says why one lock per room in one process is the whole of it.
    """
    target = jailed_path(room_folder, relative_path)
    with room_lock(room_folder):
        current_revision = _revision_of(_record_at(target))
        if current_revision != expected_revision:
            raise StaleWrite(current_revision)
        saved = {**record, "revision": expected_revision + 1}
        _written(target, json.dumps(saved).encode())
        return saved


def write_file(room_folder: Path, relative_path: str, content: str) -> None:
    """Save `content` as a file in the room — evidence rather than a record, so no revision.

    Nothing here is conditional: the bytes are the manager's own words and the room is the only
    place they exist. A record that names this file is what a revision guards, and that save is
    `write_record`'s.
    """
    _written(jailed_path(room_folder, relative_path), content.encode())


def write_document(room_folder: Path, relative_path: str, text: str) -> None:
    """Save a document a human reads, unless that would lose more than half of the saved one.

    The guard is here rather than in whatever renders the document, because it is the write that
    has both numbers in front of it and because a second write path is how the guard comes to be
    on one document somebody remembered. A document that is not there yet has nothing to shrink
    from and is written; one that grows, or barely moves, is written without argument.
    """
    target = jailed_path(room_folder, relative_path)
    payload = text.encode()
    saved = target.stat().st_size if target.is_file() else 0
    if saved > SHRINK_FACTOR * len(payload):
        raise Shrunk(relative_path, saved, len(payload))
    _written(target, payload)


def _written(target: Path, payload: bytes) -> None:
    """Bytes onto an already-jailed path, making the folder a room's first write needs.

    One spelling for both writes: a room path that reached the disk some other way would be a
    path the jail above had no say in.

    The bytes land in a staged file beside the target, are flushed to the disk, and take the
    target's name in one `rename`, so a reader sees the whole old record or the whole new one and
    never half of either (ADR-0010). Plain `write_bytes` truncates first, so a stop between the
    truncation and the last byte — a `SIGTERM` deploy, an OOM kill — left an unparseable run file
    where the resume checkpoint should be. The staged file is removed when the write does not
    finish, so a crash leaves no litter in the room for the sweep or a digest to trip over.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, staged = tempfile.mkstemp(dir=target.parent)
    try:
        os.chmod(staged, READABLE_BY_THE_SERVER)
        with os.fdopen(descriptor, "wb") as opened:
            opened.write(payload)
            opened.flush()
            os.fsync(opened.fileno())
        os.replace(staged, target)
    except BaseException:
        os.unlink(staged)
        raise


def _record_at(target: Path) -> Record | None:
    """The record at an already-jailed path, so a write jails the path once rather than twice."""
    if not target.is_file():
        return None
    loaded: Record = json.loads(target.read_bytes())
    return loaded


def _revision_of(record: Record | None) -> int:
    """A record that was never written is at revision 0. Pins the revision JSON hands back."""
    return 0 if record is None else int(record["revision"])

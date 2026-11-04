"""The room door: what a scanned code makes you, and what that identity may touch.

The code in the QR is a credential, not an address (ADR-0003): the demo skin presents it as an
authenticated identity, one identity per room. Isolation has no partial credit — with no auth
callback registered Chainlit's ``get_current_user`` returns ``None`` and every ``if current_user:``
guard becomes a no-op at the same moment, so the property comes from distinct identifiers and from
nothing else. Measured in ``tests/isolation/``; verdict table atop
``docs/research/chainlit-multitenancy.md``.

What a room code *is* — the shape one has to have before anything creates a folder for it — and
the ``Refused`` every door raises are one layer down, in ``nemo.room_code``. Ticket 50 gave the
room code a second reader in ``nemo.walk``, which mints rooms, and these two are siblings that may
not import each other; the shared thing sits below them both.

Two of these decisions cannot be made anywhere but here.

``checked_session_id``
    Chainlit uses the client-supplied ``sessionId`` as a directory name, creates it and later
    ``rmtree``s it. The value rides inside the Socket.IO CONNECT ``auth`` payload, in an opaque
    engine.io frame after upgrade, where nginx has no URL, header or query string to match on. The
    systemd sandbox contains the damage; only this check closes the defect, and the unit in
    ``deploy/`` ships alongside rather than instead of it.

``sweep``
    A killed process leaves its session directory behind, and with Chainlit's default
    ``session_timeout`` of 3600 s an ordinary restart does too — uvicorn will not wait an hour to
    shut down. ADR-0012 proposes the interval and the age.
"""

from __future__ import annotations

import shutil
import sys
import time
import uuid
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlsplit

from nemo.room_code import NO_FOLDER, Refused

#: A session directory untouched for this long belongs to nobody. ADR-0012: Chainlit's own
#: ``session_timeout`` is 3600 s, and an hour of slack on top keeps a paused room's uploads.
SWEEP_AGE_SECONDS = 7200

#: How often the timer runs the sweep. ADR-0012.
SWEEP_INTERVAL_SECONDS = 900

#: The last segment of the room-link prefix nginx serves, which is ``/demo/r/``. A scan that loses
#: the room code leaves the prefix itself — ``/demo/r/`` and ``/demo/r`` both end here — so a link
#: whose last segment is this one carries no room code at all.
PREFIX_SEGMENT = "r"


def identity_from_link(link: str) -> str:
    """The room code a scanned link carries, which is the identity the skin holds for it.

    nginx forwards ``$request_uri``, so what arrives carries the query string a scanned link was
    shared with. The room code decides storage, so `?x=1` left inside it would be a wrong-room
    write; ``urlsplit`` drops the query and the fragment and leaves the path.

    A link that ends at the prefix carries no room code, and that is judged here rather than at the
    door because a malformed credential needs no disk to recognise. ``/demo/r/`` and ``/demo/r``
    are what a damaged or half-printed QR scans as, and both leave ``PREFIX_SEGMENT`` as the last
    segment — a real credential for a room nobody named, until this line.

    **Nothing is percent-decoded, and that is a decision rather than an inheritance.** ``urlsplit``
    leaves ``%2F`` as three characters, so whatever comes out is one segment and ``rooms / room``
    is one child of the rooms folder; no room is named that, so ``checked_room_folder`` refuses it.
    Decoding would produce a string that then has to be re-validated for separators; not decoding
    has nothing to validate. ``test_an_encoded_separator_never_reaches_the_filesystem`` pins it.
    """
    # `rpartition` rather than `rsplit("/", 1)`: the two are the same last segment, but the
    # maxsplit argument is a number no test can pin, because `[-1]` does not depend on it.
    room = urlsplit(link).path.rstrip("/").rpartition("/")[-1]
    if not room or room == PREFIX_SEGMENT:
        raise Refused(f"the link {link!r} carries no room code")
    return room


def checked_room_folder(rooms: Path, room: str) -> Path:
    """The folder this room code names, or a refusal in its own words if it has none.

    The second of the two refusals, and deliberately not worded like ``identity_from_link``'s: a
    well-formed code for a room nobody minted is a different event from a damaged scan, and an
    operator reading the log has to be able to tell them apart without guessing. This one depends
    on the disk, so a mount that is slow or briefly absent refuses valid rooms — the accepted cost
    of catching a code the link alone cannot judge, and the reason the two sentences must differ.

    ``.`` and ``..`` are the two one-segment codes that name something other than a room; both
    have a folder, neither is one.

    ``is_dir`` swallows some errno values and re-raises the rest, and a code longer than the
    filesystem's name limit is one it re-raises: ``ENAMETOOLONG`` escaped as a bare ``OSError``
    where this layer promises a refusal in its own words. A name the filesystem will not even look
    up is a name no room has, which is this refusal and not a third outcome — the property at
    ``test_door.py`` says there is no third outcome, and it was right while this was wrong.
    """
    if room in (".", "..") or not _is_a_folder(rooms / room):
        raise Refused(NO_FOLDER.format(room=room))
    return rooms / room


def _is_a_folder(path: Path) -> bool:
    """``path.is_dir()``, with every disk answer read as "not a folder" rather than raised."""
    try:
        return path.is_dir()
    except OSError:
        return False


def authorise(actor_room: str | None, owner_room: str) -> None:
    """Only the room that owns a thing may read it or fire it. No identity is no entry."""
    if actor_room != owner_room:
        raise Refused(f"{actor_room!r} may not touch {owner_room!r}")


def checked_session_id(value: object) -> str:
    """The client's ``sessionId``, unchanged, or a refusal if it is not a UUID."""
    text = str(value)
    try:
        uuid.UUID(text)
    except ValueError as exc:
        raise Refused(f"session identifier {text!r} is not a UUID") from exc
    return text


def admit(actor_room: str, auth: Mapping[str, object], occupants: Mapping[str, str]) -> str:
    """The CONNECT decision: a checked session identifier, owned by the room presenting it.

    ``occupants`` maps a live session identifier to the room holding it. An identifier nobody
    holds is this room's to open; one another room holds is a hijack, and refusing it leaves the
    occupant where they were.
    """
    session_id = checked_session_id(auth.get("sessionId"))
    authorise(actor_room, occupants.get(session_id, actor_room))
    return session_id


def _names_a_session(name: str) -> bool:
    try:
        checked_session_id(name)
    except Refused:
        return False
    return True


def _is_an_orphan(child: Path, cutoff: float) -> bool:
    """A real directory (not a symlink) named after a session, untouched since ``cutoff``."""
    return (_names_a_session(child.name) and not child.is_symlink() and child.is_dir()
            and child.stat().st_mtime < cutoff)


def sweep(sessions_dir: Path, max_age_seconds: float = SWEEP_AGE_SECONDS) -> list[str]:
    """Remove session directories nothing has touched for ``max_age_seconds``; name what went.

    A session directory is one Chainlit named after a session: a real directory (never a symlink,
    which would lead out of ``sessions_dir``) whose name is a UUID, the only ``sessionId`` the door
    lets through (ticket 175, on 160's rule). A room's folder or anything else stays.

    A directory Chainlit has not made yet holds no orphan, so the first manager into a fresh room
    meets a no-op rather than a ``FileNotFoundError``.
    """
    if not sessions_dir.is_dir():
        return []
    cutoff = time.time() - max_age_seconds
    swept: list[str] = []
    for child in sorted(sessions_dir.iterdir()):
        if _is_an_orphan(child, cutoff):
            shutil.rmtree(child)
            swept.append(child.name)
    return swept


if __name__ == "__main__":  # pragma: no cover - the timer's entry point, see deploy/
    print("\n".join(sweep(Path(sys.argv[1]))))

"""The evidence a room already holds: its interviews, their own bytes, and their fingerprints.

Transcripts are the evidence, not a side effect. The referee proves nothing was invented by
finding each quote verbatim in a readable file, so the question was only ever whose disk — and for
a demo room the answer is ours, readable by the operator (ADR-0002). What that makes this module
is the room's evidence read as it stands: which interviews are on file, what each of them says in
its own characters, and the digest that says whether it still says it.

It sits below the walk because it is not about a walk. `nemo.walk` binds one of these to a BIA and
puts it on a card; a later stage quotes it and the referee checks the quote; ticket 13 will add a
third home, the interview held in the room there and then. All three read the room the same way,
and a second reader would be a second answer to "what does this file say".

Nothing here writes. A preview is the file's own first characters and never a summary of them, and
a fingerprint is taken over the same bytes `sha256sum` would take it over, so an operator can
check a binding without the product's help.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

# The field name is `nemo.record`'s: `nemo.evidence` reads the same word off a register entry, and
# a word two layers need is spelled once, below them both, rather than borrowed across.
from nemo.record import DEPARTMENT

#: Where the interviews a company already had are filed in a room.
INTERVIEWS = "07_Interviews"

#: The room's second home for interviews: the ones it held itself, earlier. An interview conducted
#: in the room is evidence exactly as one the company already had is (ADR-0002), so both folders
#: are read at Stage 2 and neither wins.
OWNER_INTERVIEWS = "output/owner-interviews"

#: Both homes, in the order a card offers them.
HOMES = (INTERVIEWS, OWNER_INTERVIEWS)

#: How much of an interview is shown beside it: its own first characters, cut at a fixed length
#: and not touched otherwise. Long enough to reach testimony past the front matter, short enough
#: to read on a phone. A preview is never summarised — a yes has to be a yes to bytes.
PREVIEW = 400

_FRONT_MATTER_DEPARTMENT = re.compile(rf"^{DEPARTMENT}:[ \t]*(.+?)[ \t]*$", re.MULTILINE)


@dataclass(frozen=True)
class Interview:
    """One interview the room holds: what a manager calls it, where it is, and what it said.

    ``preview`` is the file's own characters and never a summary of them, because the whole claim
    of a preview is that a yes is a yes to something a human has read. ``fingerprint`` is the
    digest of the same file's bytes, as ``sha256sum`` prints it, so the operator can check the
    binding without the product's help.
    """

    name: str
    path: str
    preview: str
    fingerprint: str


def held(room_folder: Path, process: str) -> tuple[Interview, ...]:
    """Every interview the room holds for this process, from both of its homes, each once."""
    return tuple(_read(room_folder, path) for path in sorted(
        path for home in HOMES for path in paths_about(room_folder, home, process)))


def paths_about(room_folder: Path, home: str, process: str) -> list[str]:
    """The interviews in one home whose front matter names this process, as room-relative paths."""
    return [f"{home}/{found.name}" for found in (room_folder / home).glob("*.md")
            if process in _named_in(found)]


def departments(room_folder: Path) -> set[str]:
    """Every department the company's own transcripts name, each once."""
    return {name for found in (room_folder / INTERVIEWS).glob("*.md")
            for name in _named_in(found)}


def unreadable(room_folder: Path) -> list[str]:
    """The captures in either home that name no department, as room-relative paths.

    The one question a reader can answer about a file nobody has bound yet: is it evidence for
    anybody? A capture whose front matter names no department is offered for no process, so no
    stage can bind it and no walk that needs it reaches stage 5. Ticket 50's admission check asks
    this of a seed before a room is minted from it — better to refuse a scan than to seat a
    delegate in front of a BIA that stops at stage 2 — and what comes back is paths, because the
    operator who has to put it right needs something to open.
    """
    return sorted(f"{home}/{found.name}" for home in HOMES
                  for found in (room_folder / home).glob("*.md")
                  if not _named_in(found))


def about_to_be_filed(path: str, content: str) -> Interview:
    """An interview that is not on disk yet: its own bytes, and the fingerprint of exactly them.

    Ticket 13's live path shows the manager the whole of what it is about to write, under the name
    it will be filed as, so that a yes is a yes to named bytes before there are any. The preview is
    **not** cut at ``PREVIEW``: that length is for offering a file somebody else wrote, and this is
    the interview they have just this minute given.
    """
    return Interview(name=_name(Path(path)), path=path, preview=content,
                     fingerprint=digest_of(content))


def previewed_whole(item: Interview) -> bool:
    """Whether the preview is the whole of the bytes the fingerprint promises, and not a cut.

    True of an interview ``about_to_be_filed`` — the one nemo held in the room, previewed whole so
    that a yes is a yes to named bytes before there are any — and false of a longer file somebody
    else wrote, whose preview stops at ``PREVIEW``. Read off the two fields the interview already
    carries rather than kept as a flag, because the fields are the claim: a preview that digests
    to the fingerprint beside it *is* the evidence and can be written down, and one that does not
    is an opening that no writer may rebuild a transcript from.

    ``nemo.walk`` asks this before it files an interview that is not on disk yet.
    """
    return digest_of(item.preview) == item.fingerprint


def digest(path: Path) -> str:
    """The file's own bytes, digested as ``sha256sum`` prints it. "" when the file has gone."""
    return _sha256(path.read_bytes()) if path.is_file() else ""


def digest_of(content: str) -> str:
    """The same digest over bytes that are not on disk yet — what a preview promises."""
    return _sha256(content.encode())


def _sha256(payload: bytes) -> str:
    """One digest for the package, so a preview and the file it becomes cannot be digested twice."""
    return hashlib.sha256(payload).hexdigest()


def text(path: Path) -> str:
    """Read an interview as UTF-8, and never at the locale's discretion.

    `Path.read_text()` with no encoding falls back to `locale.getencoding()` — UTF-8 on this box
    and not necessarily on another, so a transcript with an umlaut in it would decode differently
    depending on where the skin runs. `bytes.decode()` has no such fallback: its default is UTF-8
    unconditionally, fixed in CPython rather than read from the environment. Spelling it this way
    rather than passing `encoding="utf-8"` also leaves mutmut nothing on this line to mutate, so
    the property is held by the code's shape instead of by a pragma hiding the mutant that tests
    it. `test_a_transcript_is_utf_8_wherever_the_skin_runs` pins it under a non-UTF-8 locale.
    """
    return path.read_bytes().decode()


def _read(room_folder: Path, path: str) -> Interview:
    target = room_folder / path
    return Interview(name=_name(target), path=path, preview=text(target)[:PREVIEW],
                     fingerprint=digest(target))


def _name(path: Path) -> str:
    """What a manager calls this interview: its own file name, said in words.

    Never its path and never its folder: ``docs/voice.md`` §3.1 keeps a path off a card everywhere
    but the ``Source:`` line, and this name is a button. Not the transcript's title either, which
    is the obvious alternative and the wrong one — two interviews about one department are both
    titled after the department, so a title makes two buttons read as one thing offered twice.
    The name the company filed it under is what tells them apart, and is what the manager sees in
    the folder.
    """
    return path.stem.replace("_", " ").replace("-", " ")


def _named_in(path: Path) -> list[str]:
    """The departments a capture names, or none when its bytes are not UTF-8 (ticket 237).

    A file the company saved as Windows-1252 is ordinary in their own store. It names nobody, so
    `unreadable` hands its path to the operator and no stage offers it; no encoding is guessed.
    """
    try:
        return _departments_in(text(path))
    except UnicodeDecodeError:
        return []


def _departments_in(content: str) -> list[str]:
    return _FRONT_MATTER_DEPARTMENT.findall(content)

"""Served facts: what the room's files say, worked out by nemo and handed to the chat finished.

Ticket 106, and M2 in `docs/research/v1-failure-modes.md`: the model states facts about the room
that it should have been served. Two models in round 2 answered "I can't find a supplier called
Kornmark" about a customer the risk register names at 27 % of revenue. The fix is to serve the
fact, never to add a prompt rule. Three kinds of fact are served, each read off the room's files
on every call:

1. **A company by name** (`company`): the suppliers the dependency register names and the
   customers the company profile lists (`companies`), and what every file says about the one
   asked for. A name matches when its case, its legal form, its first word, its abbreviation or
   one letter differ, never by meaning. A name no list carries is looked for as typed, so "no
   file names it" is said only when no file does.
2. **The interviews** (`interviews`): who, when and about what, from each interview file's front
   matter and the date its file name carries. The count is the number of files.
3. **The figure the record carries** (`carried`): the record's MTPD, RTO and RPO first, and beside
   each the figure an interview stated, labelled with whose interview it was.

Nothing here writes, and nothing reads the model's words.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path
from typing import Any

from nemo.interview import HOMES, OWNER_INTERVIEWS, _name, text
from nemo.text import norm

#: The files the companies are listed in, and the register whose rows carry an id.
PROFILE = "01_Organisation/company-profile.md"
REGISTER = "03_Dependencies/dependency-register.json"
RISKS = "06_Risk-and-Incidents/risk-register.md"

#: nemo's answer for a name that no file of the room carries.
NOT_NAMED = "no file names it"

#: The figures the record carries, in the order a record states them.
LABELS = ("MTPD", "RTO", "RPO")

#: A legal form after a company's name, and everything after it ("GmbH & Co. KG").
_LEGAL_FORM = re.compile(r"(?:^|\s+)(?:GmbH|AG|SE|KG|OHG|UG|e\.V\.|w\.V\.|Ltd\.?|LLC|Inc\.?|plc)"
                         r"(?=[\s,]|$).*")
#: An aside in brackets after a name: "(discounter)", "(primary)", or an abbreviation, "(NTV)".
_ASIDE = re.compile(r"\s*\(([^)]*)\)")
_ABBREVIATION = re.compile(r"[A-Z]{2,}")
#: The date an interview's file name starts with, `yy_mm_dd_`.
_DATED = re.compile(r"(\d\d)_(0[1-9]|1[0-2])_(\d\d)_")
_MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---", re.DOTALL)
_FIELD = re.compile(r"^(\w+):[ \t]*(.*?)[ \t]*$", re.MULTILINE)
#: A transcript line's speaker, "**Louven:** ", and where one sentence of prose ends.
_SPEAKER = re.compile(r"\*\*[^*]+:\*\* ")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
#: The line under a table's header: nothing but dashes, colons and spaces in its cells.
_SEPARATOR = re.compile(r"[-: ]*")


@dataclass(frozen=True)
class Company:
    """A customer or supplier a room's file lists, as that file spells it, aside taken off.

    ``kind`` is "supplier" for the dependency register's, and the profile table's own heading for
    a customer ("Customer / channel"). ``keys`` are the names it is matched by: its name and its
    first word, legal form off and case folded, and an abbreviation its aside gives.
    """

    name: str
    kind: str
    share: str
    source: str
    keys: tuple[str, ...]


@dataclass(frozen=True)
class Mention:
    """One place a file names a company, in the file's own words.

    ``quote`` is a table row whole, and a line of prose cut to the sentences that name it, its
    speaker kept ("**Louven:** Kornmark is twenty-seven percent of our revenue, …"), so every
    mention fits what the chat reads. ``row`` is the risk register's row id or the dependency
    register's asset id, "" elsewhere.
    """

    path: str
    quote: str
    row: str


@dataclass(frozen=True)
class Found:
    """What nemo serves for a name as typed: the companies it resolved to, how, and every mention.

    ``said`` is `NOT_NAMED` exactly when no file names it, and "" otherwise.
    """

    asked: str
    companies: tuple[Company, ...]
    how: str
    mentions: tuple[Mention, ...]
    said: str


@dataclass(frozen=True)
class Held:
    """One interview on file: its path, who was interviewed, about what, and when ("" if unsaid)."""

    path: str
    who: str
    about: str
    when: str


@dataclass(frozen=True)
class OnFile:
    """The room's interviews as one reading (`read`): each one held, and each file's words by its
    path."""

    held: tuple[Held, ...]
    words: Mapping[str, str]


@dataclass(frozen=True)
class Stated:
    """A figure a prepared draft took from an interview: its label, its value, the interview's
    path, and the interviewee's words it rests on. The value is the drafting model's reading;
    only the quote, found word for word in the file (`in_their_words`), is the interviewee's."""

    label: str
    value: str
    path: str
    quote: str


# ── 1. a company by name ────────────────────────────────────────────────────────────────────
def companies(room: Path) -> tuple[Company, ...]:
    """The dependency register's suppliers that carry a legal form, then the profile's customers."""
    suppliers = [_company(raw, "supplier", "", REGISTER) for raw in dict.fromkeys(_suppliers(room))]
    customers = [_company(cells[0], header[0], cells[1], PROFILE)
                 for header, cells in _rows(_lines(room / PROFILE))
                 if "customer" in header[0].casefold()]
    return (*suppliers, *customers)


def _suppliers(room: Path) -> list[str]:
    """Each name in the register's `supplier` fields, split at " / ", that carries a legal form."""
    fields = [str(entry.get("supplier")) for entry in _entries(room).values()]
    return [part for field in fields for part in field.split(" / ") if _LEGAL_FORM.search(part)]


def company(room: Path, asked: str) -> Found:
    """Every company the name resolves to, and what each file of the room says about it."""
    key = _key(asked)
    hits, how = _resolved(key, companies(room))
    words = [k for c in hits for k in c.keys] or [key] * bool(key)
    mentions = _mentions(room, words)
    return Found(asked, tuple(hits), how, mentions, "" if mentions else NOT_NAMED)


def _resolved(key: str, listed: tuple[Company, ...]) -> tuple[list[Company], str]:
    """The listed companies the key names, and how: by name first, else one letter off."""
    same = [c for c in listed if key in c.keys]
    near = _near(key, listed)
    return (same, "by name") if same else (near, "one letter off" if near else "")


def _near(key: str, listed: tuple[Company, ...]) -> list[Company]:
    return [c for c in listed if any(_one_edit(key, k) for k in c.keys)]


def _company(raw: str, kind: str, share: str, source: str) -> Company:
    name = _ASIDE.sub("", raw).strip()
    short = _key(name)
    abbreviations = [aside.casefold() for aside in _ASIDE.findall(raw)
                     if _ABBREVIATION.fullmatch(aside)]
    return Company(name, kind, share, source, tuple(dict.fromkeys(
        [short, short.split()[0], *abbreviations])))


def _key(name: str) -> str:
    return _LEGAL_FORM.sub("", _ASIDE.sub("", name)).strip().casefold()


def _one_edit(a: str, b: str) -> bool:
    """Whether b is a with exactly one letter changed, added or taken away."""
    return a != b and any(a[:i] + a[i + 1:] in (b, b[:i] + b[i + 1:]) or b[:i] + b[i + 1:] == a
                          for i in range(max(len(a), len(b))))


def _mentions(room: Path, words: list[str]) -> tuple[Mention, ...]:
    """The risk register's lines, the dependency register's fields, the interviews, the rest."""
    rest = [p for p in _readable(room) if p not in (RISKS, REGISTER)]
    return (*_said_in(room, [RISKS], words), *_registered(room, words),
            *_said_in(room, rest, words))


def _registered(room: Path, words: list[str]) -> list[Mention]:
    """Every field of a dependency-register entry that names one of the words, with its asset id."""
    return [Mention(REGISTER, _quote(said, words), key) for key, entry in _entries(room).items()
            for said in _strings(entry) if _names(said, words)]


def _readable(room: Path) -> list[str]:
    """The room's own Markdown and JSON files, interviews first; nothing nemo wrote or published."""
    paths = [p.relative_to(room).as_posix() for p in room.rglob("*")
             if p.suffix in (".md", ".json")]
    own = [p for p in paths
           if p.startswith(OWNER_INTERVIEWS) or not p.startswith(("output/", "public/"))]
    return sorted(own, key=lambda p: (not p.startswith(HOMES), p))


def _said_in(room: Path, paths: list[str], words: list[str]) -> list[Mention]:
    return [Mention(path, _quote(line, words), _row(path, line))
            for path in paths for line in _lines(room / path) if _names(line, words)]


def _quote(line: str, words: list[str]) -> str:
    """A table row whole; prose cut to its sentences that name one of the words, speaker kept.
    A line that names it only as its speaker stays whole."""
    speaker = _SPEAKER.match(line)
    head = speaker.group(0) if speaker else ""
    said = [s for s in _SENTENCE.split(line[len(head):]) if _names(s, words)]
    return head + " … ".join(said) if said and not line.startswith("|") else line


def _row(path: str, line: str) -> str:
    """A risk-register row's id, its first cell: "" for any other line."""
    return _cells(line)[0].replace("*", "") if path == RISKS and _cells(line) else ""


def _names(line: str, words: list[str]) -> bool:
    return any(re.search(rf"(?<!\w){re.escape(w)}(?!\w)", line, re.IGNORECASE) for w in words)


def _strings(value: Any) -> list[str]:
    """Every string a register entry holds, however deep."""
    if isinstance(value, str):
        return [value]
    items = value.values() if isinstance(value, dict) else value if isinstance(value, list) else []
    return [s for item in items for s in _strings(item)]


def _entries(room: Path) -> dict[str, dict[str, Any]]:
    """The dependency register's entries by their asset id; none when it is not on file."""
    path = room / REGISTER
    found = json.loads(text(path)) if path.is_file() else {}
    return {key: entry for key, entry in found.items() if isinstance(entry, dict)}


def _lines(path: Path) -> list[str]:
    return text(path).splitlines() if path.is_file() else []


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")] if line.startswith("|") else []


def _rows(lines: list[str]) -> list[tuple[list[str], list[str]]]:
    """(its header, the row) for every row of every Markdown table in the lines."""
    tables = [list(rows) for found, rows in groupby(map(_cells, lines), key=bool) if found]
    return [(rows[0], row) for rows in tables for row in rows[1:]
            if not _SEPARATOR.fullmatch("".join(row))]


# ── 2. the interviews ───────────────────────────────────────────────────────────────────────
def interviews(room: Path) -> tuple[Held, ...]:
    """Every interview file in both homes, in the order a card offers them."""
    return read(room).held


def read(room: Path) -> OnFile:
    """The room's interviews, each file read once (ticket 309): one build serves every activity's
    figures from this, rather than listing the interviews again for each one."""
    said = {f"{home}/{found.name}": text(found)
            for home in HOMES for found in sorted((room / home).glob("*.md"))}
    return OnFile(tuple(_held(where, words) for where, words in said.items()), said)


def _held(where: str, words: str) -> Held:
    matter = _FRONT_MATTER.match(words)
    fields = dict(_FIELD.findall(matter.group(1))) if matter else {}
    dated = _DATED.match(Path(where).name)
    when = f"{int(dated[3])} {_MONTHS[int(dated[2]) - 1]} 20{dated[1]}" if dated else ""
    # t337: who was interviewed; `owner:` is the process owner, read only when no one else is named
    who = fields.get("interviewee") or fields.get("owner", "")
    return Held(where, who, fields.get("department", ""), when)


# ── 3. the figure the record carries ────────────────────────────────────────────────────────
def carried(room: Path, record: Mapping[str, str | None], state: str,
            stated: Iterable[Stated], on_file: OnFile | None = None) -> dict[str, tuple[str, ...]]:
    """Per figure: the record's first ("record: 4 h (signed)"), then each interview's, served with
    its own words and only when its file holds them verbatim (`in_their_words`). A build that
    serves several activities reads the room once (`read`) and hands each call that reading."""
    found = on_file or read(room)
    held = {h.path: h for h in found.held}
    said = _verified(found, stated)
    lines = {label: _figure(record.get(label), state, _theirs(held, said, label))
             for label in LABELS}
    return {label: figure for label, figure in lines.items() if figure}


def _verified(on_file: OnFile, stated: Iterable[Stated]) -> list[Stated]:
    return [s for s in stated if _verbatim(on_file, s)]


def in_their_words(room: Path, stated: Stated) -> bool:
    """Whether the stated item's quote is non-empty and stands word for word in the interview
    file at its path: one of the room's interview files, never any other. Compared as the
    referee compares a quote (`nemo.text.norm`): typography folded, never wording."""
    return _verbatim(read(room), stated)


def _verbatim(on_file: OnFile, stated: Stated) -> bool:
    quote, words = norm(stated.quote), on_file.words
    return bool(quote) and stated.path in words and quote in norm(words[stated.path])


def _theirs(held: Mapping[str, Held], said: list[Stated], label: str) -> list[str]:
    """Each interview's figure for the label, named by whose interview it was, in their words."""
    return [f"{_whose(held[s.path], s.path)}: {s.value}, in their words: “{s.quote}”"
            for s in said if s.label == label]


def _figure(mine: str | None, state: str, theirs: list[str]) -> tuple[str, ...]:
    """The record's figure first, when it carries one, then each interview's, each once."""
    return tuple(dict.fromkeys(([f"record: {mine} ({state})"] if mine else []) + theirs))


def _whose(held: Held, path: str) -> str:
    if held.who:
        return f"{held.who.split()[-1]}'s interview" + (f" ({held.when})" if held.when else "")
    return _name(Path(path))

"""The approved transcript read as standardised evidence: what it states, and what it does not.

Stage 3 is the server doing the work and showing the human its own working, so this module's whole
discipline is what it refuses to say. An RTO is asserted only where a label and a figure stand
together — v1 read "RTO: we never settled one" as a target and put it on a card. A dependency the
register does not model gets **no id**, because an id that looks right and is not is worse than a
gap: the graph believes it. A category the interview never reached is proposed as unknown, and the
reason it was not reached is the transcript's own or the words *not stated* — never one of three
options picked at the card, which would be a reason invented where none was given (owner's ruling,
2026-09-12, `docs/stage-model.md` Stage 3).

Nothing here reaches the disk, the clock or the network: it is handed a transcript's characters,
the register the room holds and the method's own lenses, and it hands back a draft. `nemo.walk`
writes the prose around it and owns the press; this owns what may be claimed.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from nemo.record import DEPARTMENT, Record
from nemo.text import norm  # the project's one normalizer: tolerate typography, never reword

#: The four things stage 3 standardises out of an interview, in the order a card reads them.
LABELS = ("MTPD", "RTO", "RPO", "MBCO")

#: The three the owner states and the card marks as his own words. An RTO is read off the evidence
#: rather than stated, so it is not put in anybody's mouth.
OWNER_STATED = ("MTPD", "RPO", "MBCO")

#: The two said as a time, and so asserted only where a duration stands beside the label.
DURATIONS = ("MTPD", "RTO")

#: What a transcript calls the dependencies it names, what it calls a scored impact category, and
#: what its header calls the two things stage 3 reads out of it: which impact categories were
#: covered, and why the rest were not.
DEPENDS = "Depends on"
IMPACT = "Impact"
COVERED = "covered"
NOT_ELICITED = "not elicited"

#: What a cell nobody scored says. The referee's own word for it, read back out of the record it
#: judges: a category left honestly blank, never a zero and never a gap in the grid.
MISSING = "MISSING"

#: The reason recorded where the header gives none. Those words, and nothing standing in for them.
NOT_STATED = "not stated"

#: The worst case proposed for a category the interview never reached.
UNKNOWN = "unknown"

UNMODELLED = ("{heard} — you named it in the interview and your dependency register does not "
              "model it. There is no id for it to resolve to and I have not made one up, so it "
              "stays an open item you would be accepting at sign-off.")
DISPUTED = ("{heard} — the interview puts it with {said}, and your dependency register puts it "
            "with {held}. Both cannot be right, and what the rest of this rests on changes with "
            "the answer.")

_FRONT_MATTER = re.compile(r"\A---\n.*?\n---", re.DOTALL)
_SECTION = re.compile(r"^##[ \t]+(.+)$", re.MULTILINE)
_SCORED = re.compile(rf"\A{IMPACT} (?P<lens>[^:]+): (?P<cells>.+?)\.?\Z")
_CELL = re.compile(r"\A(?P<horizon>.+?)[ \t]+(?P<score>[1-5])\Z")
_SAID = re.compile(r"(?P<speaker>[^:]+): (?P<said>.+)")
#: A figure, with the comparator it was stated with (t139, F1): ">168 h" is past the last horizon
#: and "168 h" is the horizon itself, so dropping the ">" put a figure on the card nobody said.
_DURATION = re.compile(
    r"(?:[<>≤≥]\s*)?\d+(?:[.,]\d+)?\s*(?:h|hrs?|hours?|m|mins?|minutes?|d|days?|weeks?)\b")
_NAMED_OWNER = re.compile(r"(?P<heard>.+?)\s*\((?P<owner>[^)]+)\)\Z")


@dataclass(frozen=True)
class Statement:
    """One thing the transcript states: the figure, and the sentence it was stated in."""

    label: str
    value: str
    speaker: str
    quote: str
    owner_stated: bool


@dataclass(frozen=True)
class Dependency:
    """One dependency the interview names: the words it was heard in, and what it resolves to.

    ``asset_id`` is empty where the register models nothing under that exact name. Empty is the
    honest answer and a finding follows from it; a nearest match would be an invented id wearing
    a better disguise.
    """

    heard: str
    owner: str
    asset_id: str
    held_by: str


@dataclass(frozen=True)
class Score:
    """One impact category scored across the horizons, and the sentence it was scored in.

    The quote is the whole line, because that is what the referee hunts verbatim in the room's own
    file and what stage 4 puts beside the score. A row the interview never gave is not here at all.
    """

    lens: str
    row: dict[str, int]
    speaker: str
    quote: str


@dataclass(frozen=True)
class Activity:
    """One thing the BIA is about: what the interview said under it, and the grid it scored.

    A transcript that names none is about one activity — the department its front matter names —
    which is the ordinary walk. Five headings are five activities and one stage 4 card
    (owner's ruling, 2026-09-12).
    """

    name: str
    statements: tuple[Statement, ...]
    dependencies: tuple[Dependency, ...]
    scores: tuple[Score, ...]
    lenses: tuple[str, ...]

    @property
    def impact_grid(self) -> Record:
        """Every category the method names, scored where the interview scored it and MISSING where
        it did not — over the horizons the interview itself used, never a horizon nobody named."""
        rows = {score.lens: score.row for score in self.scores}
        absent = dict.fromkeys((h for score in self.scores for h in score.row), MISSING)
        return {lens: dict(rows.get(lens, absent)) for lens in self.lenses}

    @property
    def proposed(self) -> Record:
        """This activity as the run state carries it, which is all stage 4 is ever given."""
        return {"name": self.name, "impact_grid": self.impact_grid,
                "evidence": [asdict(item) for item in self.statements],
                "scores": [asdict(item) for item in self.scores],
                "dependencies": [asdict(item) for item in self.dependencies]}


@dataclass(frozen=True)
class Draft:
    """The server's own draft of the standardised evidence, before a human has seen it."""

    activities: tuple[Activity, ...]
    unknown: tuple[str, ...]
    not_elicited: str

    @property
    def statements(self) -> tuple[Statement, ...]:
        """Everything the interview states, whichever activity it was said under."""
        return tuple(item for activity in self.activities for item in activity.statements)

    @property
    def dependencies(self) -> tuple[Dependency, ...]:
        """Every dependency the interview names, whichever activity it was named under."""
        return tuple(item for activity in self.activities for item in activity.dependencies)

    @property
    def open_items(self) -> tuple[str, ...]:
        """What the evidence leaves to be decided, across the whole interview."""
        return _open_items(self.dependencies)

    @property
    def proposal(self) -> Record:
        """What goes to the run state at the press: every string the card is entitled to say."""
        return {
            "evidence": [asdict(item) for item in self.statements],
            "dependencies": [asdict(item) for item in self.dependencies],
            "open_items": list(self.open_items),
            "worst_case": {lens: UNKNOWN for lens in self.unknown},
            "not_elicited": self.not_elicited,
            "activities": [activity.proposed for activity in self.activities],
        }


def standardise(transcript: str, register: Mapping[str, Any], lenses: Sequence[str]) -> Draft:
    """The draft this transcript supports, and nothing beyond it."""
    header, body = _split(transcript)
    return Draft(
        activities=tuple(_activity(name, text, register, lenses)
                         for name, text in _sections(header, body)),
        unknown=_unreached(header, lenses),
        not_elicited=_field(header, NOT_ELICITED) or NOT_STATED,
    )


def _sections(header: str, body: str) -> list[tuple[str, str]]:
    """The activities the transcript is divided into, each with the testimony said under it.

    A transcript that draws no headings is one activity under the name its front matter gives the
    department — the name the manager pressed at stage 1, so the card and the button agree.
    """
    parts = _SECTION.split(body)
    if len(parts) == 1:
        return [(_field(header, DEPARTMENT), body)]
    return [(parts[index], parts[index + 1]) for index in range(1, len(parts), 2)]


def _activity(name: str, text: str, register: Mapping[str, Any], lenses: Sequence[str]) -> Activity:
    testimony = _testimony(text)
    return Activity(name=name, statements=_statements(testimony),
                    dependencies=_dependencies(testimony, register),
                    scores=_scores(testimony), lenses=tuple(lenses))


# ── what a line scores ───────────────────────────────────────────────────────


def _scores(testimony: Sequence[str]) -> tuple[Score, ...]:
    """Every impact row the testimony scores. A line that scores nothing is not one."""
    return tuple(found for found in map(_score, testimony) if found)


def _score(line: str) -> Score | None:
    """What this line scores, or None where it scores nothing the method has a name for."""
    speaker, said = _speaker(line)
    found = _SCORED.match(said)
    if found is None:
        return None
    return Score(lens=found.group("lens"), row=_row(found.group("cells")),
                 speaker=speaker, quote=line)


def _row(cells: str) -> dict[str, int]:
    """The horizons this line scored, each with the figure beside it. A cell that says no figure
    says nothing: the horizon is left out and the referee refuses the gap, rather than filled in."""
    read = [_CELL.match(cell.strip()) for cell in cells.split(",")]
    return {found.group("horizon"): int(found.group("score")) for found in read if found}


# ── what a line states ───────────────────────────────────────────────────────


def _testimony(body: str) -> list[str]:
    """The lines somebody spoke, the blank ones between them dropped and the margins with them."""
    return [line.strip() for line in body.splitlines() if line.strip()]


def _statements(testimony: Sequence[str]) -> tuple[Statement, ...]:
    """Every figure the testimony states. A line that states nothing the method names is not one."""
    return tuple(found for found in map(_statement, testimony) if found)


def _split(transcript: str) -> tuple[str, str]:
    """The front matter and the testimony under it. A transcript without one has no header.

    Two slices of the one string at one offset, fences and all, rather than a pair of values: a
    transcript with no front matter then takes the same path as one with it, and there is no
    literal empty header standing in for the absent one. That literal was the whole difficulty —
    nothing downstream can tell an empty header from any other string that carries no ``key:``
    line, so no test could ever have killed a mutation of it (`gate.sh`, the exemption ceiling).
    """
    found = _FRONT_MATTER.match(transcript)
    end = found.end() if found else 0
    return transcript[:end], transcript[end:]


def _field(header: str, key: str) -> str:
    """What the header says under one key, in its own words. Absent from the file, absent here."""
    found = re.search(rf"^{key}:[ \t]*(.*)$", header, re.MULTILINE)
    return found.group(1).strip() if found else ""


def _speaker(line: str) -> tuple[str, str]:
    """Who said it and what they said. A line nobody spoke is all said and nobody's."""
    found = _SAID.match(line)
    return (found.group("speaker"), found.group("said")) if found else ("", line)


def _statement(line: str) -> Statement | None:
    """What this line states, or None where it states nothing the method has a name for."""
    speaker, said = _speaker(line)
    for label in LABELS:
        value = _value(label, _after(label, said))
        if value:
            return Statement(label, value, speaker, line, label in OWNER_STATED)
    return None


def _after(label: str, said: str) -> str:
    """What stands beside the label on this line. Nothing beside it is the empty string."""
    found = re.search(rf"\b{label}:[ \t]*(.*)", said)
    return found.group(1) if found else ""


def _value(label: str, beside: str) -> str:
    """The value the label carries: a duration where the method says a time, the words otherwise.

    A label with no figure beside it where a figure is what it means carries no value at all, so
    nothing is asserted for it and nothing on the card reads as though a target had been stated.
    """
    if label in DURATIONS:
        found = _DURATION.search(beside)
        return found.group() if found else ""
    return beside.strip().rstrip(".")


# ── the dependencies, and what the register models ───────────────────────────


def _dependencies(testimony: Sequence[str], register: Mapping[str, Any]) -> tuple[Dependency, ...]:
    """Every dependency the testimony names, each read against the register once."""
    assets = _assets(register)
    return tuple(_resolved(heard, owner, assets)
                 for line in testimony for heard, owner in _named_in(line))


def _assets(register: Mapping[str, Any]) -> dict[str, tuple[str, str]]:
    """What the register models, by name: its own id for it, and who it holds it under."""
    return {norm(entry["name"]): (asset_id, str(entry.get(DEPARTMENT, "")))
            for asset_id, entry in register.items()
            if isinstance(entry, dict) and entry.get("name")}


def _named_in(line: str) -> list[tuple[str, str]]:
    """Every dependency this line names, each with the owner the interview gave it, or none."""
    _, said = _speaker(line)
    named = _after(DEPENDS, said).rstrip(".")
    return [_owner(heard.strip()) for heard in named.split(",") if heard.strip()]


def _owner(heard: str) -> tuple[str, str]:
    """The dependency and the department the interview put it with, where it named one."""
    found = _NAMED_OWNER.match(heard)
    return (found.group("heard"), found.group("owner")) if found else (heard, "")


def _resolved(heard: str, owner: str, assets: Mapping[str, tuple[str, str]]) -> Dependency:
    """One dependency against the register: its exact id, or no id at all."""
    asset_id, held_by = assets.get(norm(heard), ("", ""))
    return Dependency(heard=heard, owner=owner, asset_id=asset_id, held_by=held_by)


def _open_items(dependencies: Sequence[Dependency]) -> tuple[str, ...]:
    """What the evidence leaves to be decided, the contradictions first: a card leads with those."""
    return (*(DISPUTED.format(heard=item.heard, said=item.owner, held=item.held_by)
              for item in dependencies if _disputed(item)),
            *(UNMODELLED.format(heard=item.heard)
              for item in dependencies if not item.asset_id))


def _disputed(item: Dependency) -> bool:
    """Whether the interview and the register disagree about who owns a modelled dependency."""
    return bool(item.asset_id and item.owner) and norm(item.owner) != norm(item.held_by)


# ── what the interview never reached ─────────────────────────────────────────


def _unreached(header: str, lenses: Sequence[str]) -> tuple[str, ...]:
    """The method's impact categories the header does not list as covered, in the method's order."""
    covered = {norm(name) for name in _field(header, COVERED).split(",")}
    return tuple(lens for lens in lenses if norm(lens) not in covered)

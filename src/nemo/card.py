"""The second verification layer: a stage card may only say figures the record holds.

The referee checks the record against the method. Nothing checked the card against the record,
and that is the drift ADR-0006 names — "if the card says 'about a working day' and the record says
`MTPD: 8h`, those have drifted" — without naming a mechanism for it. This is the mechanism, and
`docs/voice.md` §4.4 has already written the test in one line: **the figure on the card must be a
string the record holds.** One test, both directions. "About a working day" softens a figure;
"8 h 15 m" invents one; "45 cutters" where the record says "approximately 45 cutters" drops the
record's own qualifier. None of the three is a string the record holds.

**Two things on a card are exempt, and only two.** A *verbatim interview preview*, because a
verbatim quotation is not the card talking — an owner who said "a day or so" must not make his own
transcript unrenderable — and that one is kept out by `Card.screen` in `nemo.walk`, which never
puts a preview in the prose this check reads. And *a name the room supplies*: a room called
`Werk 1`, `Halle 45` or `Key Accounts` is not asserting a quantity when it says which building the
manager works in, so **a name is never a figure and never a vague word, whatever it contains — it
is exempt for its whole span** (the owner's ruling, 2026-09-14, widening the ruling of 2026-09-13
from a digit to a name). Both checks skip what sits **inside an occurrence of one of the room's own
names on this card**, scoped to that span and no wider. The names are never added to what the
record holds:
`The MBCO for Halle 45 is 45 cutters` is still refused for the count, `Key Accounts is the scope
and the key risk is staff` for the bare `key`, and a `Werk 7` the room does not hold is refused for
being nobody's name.

It is a mechanism and not a review. `render` is the door every card goes through on its way to a
human, the check is the first thing it does, and there is no argument that turns it off. A card
that cannot be traced raises `CardGeneratorBug`: a defect in whatever wrote the card, reported to
a developer. It is never a **finding** — a finding is something the human resolves, and no human
can resolve a card that disagrees with the record behind it.

What this does not catch, stated plainly so nobody assumes otherwise: it compares a card to a
record, so a record that is wrong about the world passes here. A live record on this box holds
seven "activities" that are resources and dependencies — a cutting room, CIP cleaning, wastewater
— each correctly derived as "no MTPD within horizons", and a card saying so agrees with it
perfectly. The defence against *that* is ticket 16, where activities come from the register and an
unmodelled dependency is a finding rather than an invented id.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from nemo.text import norm  # the project's one normalizer: tolerate typography, never reword

# The units a figure may carry. A figure keeps its unit, so "12 h" is not traced to "12 °C".
_UNITS = r"%|°c|h|hrs?|hours?|m|mins?|minutes?|d|days?|weeks?"

# `roughly 8 h`, `about 8 h`: a word that softens the figure standing next to it. §4.3 is explicit
# that the ban is on the word *adjacent to a quantity* — "a question about scope" is ordinary
# English — so these are read only in that position, and in either direction: a hedge the record
# does not carry is vagueness, and dropping a hedge the record does carry is invented precision.
_HEDGES = (
    "about", "roughly", "around", "somewhere around", "approximately", "circa", "almost",
    "nearly", "up to", "at least", "no more than", "over", "under", "some",
)

# §4.3's four tables, less the entries that carry a figure of their own: those are the hedge
# above. What is left says a figure, a severity, an evidence strength or an agreement in words,
# and a word in words is a string the record either holds or does not.
_VAGUE = (
    "a working day", "a day or so", "a day", "overnight", "end of week", "a few hours",
    "a few days", "several days", "several hours", "some time", "shortly", "soon", "quickly",
    "promptly", "minimal", "as low as possible", "to a minimum", "absolute minimum",
    "a reasonable level", "reasonable",
    "fairly critical", "quite critical", "business critical", "mission critical",
    "very important", "highly important", "key", "vital", "significant", "substantial",
    "material impact", "high risk", "likely to fail", "probably",
    "it seems", "it appears", "presumably", "evidently", "indicated", "suggested", "implied",
    "based on my understanding", "as far as i can tell", "broadly", "generally", "largely",
    "i think", "i believe", "in my view", "or whoever",
    "approved", "signed off", "the business agreed", "everyone is comfortable", "no objections",
    "we'll assume", "looks good", "is solid",
)


def _alternation(phrases: Sequence[str]) -> str:
    """The phrases as one regex branch, longest first so `a day or so` beats `a day`."""
    return "|".join(re.escape(p) for p in sorted(phrases, key=len, reverse=True))


# §2 keeps the card's structure exactly as it is, and the walk's own position in the header is
# structure rather than a figure the record holds: the five stages are the method's, not the room's.
_STRUCTURE = re.compile(r"stage \d+ of 5")
_UNIT_GAP = re.compile(rf"(?<=\d)\s+(?=(?:{_UNITS})\b)")
_FIGURE = re.compile(rf"(?<![\w/])\d+(?:[.,]\d+)?(?:{_UNITS})?(?![\w/])")
_HEDGE_TAIL = re.compile(rf"(?:^|\W)({_alternation(_HEDGES)})\s*$")
_VAGUE_RE = re.compile(rf"\b(?:{_alternation(_VAGUE)})\b")


class CardGeneratorBug(Exception):
    """A card said something the record does not hold. A bug, never a finding."""

    def __init__(self, stage: int, strings: Sequence[str], record: Mapping[str, Any]) -> None:
        super().__init__(
            f"bug in the card generator at stage {stage}: the card says "
            f"{', '.join(repr(text) for text in strings)}, which the record does not hold "
            f"(checked against the record at {_record_name(record)})")
        self.stage = stage
        self.strings = list(strings)


def _record_name(record: Mapping[str, Any]) -> str:
    """Which record was checked, so a developer can fix the card without re-walking."""
    ids = [item.get("id") or item.get("name") for item in record.get("activities") or []
           if isinstance(item, dict)]
    return f"revision {record.get('revision', 0)}, activities {ids}"


def _held_text(value: object) -> str:
    """Every string the record holds, as one line. The separator keeps two fields from merging."""
    if isinstance(value, Mapping):
        # Keys too: a grid's horizon labels are figures the record holds, and they are its keys.
        return _held_text([*value.keys(), *value.values()])
    if isinstance(value, list):
        return " | ".join(_held_text(item) for item in value)
    return str(value)


def _searchable(text: str) -> str:
    """Normalized for comparison, with the gap inside a figure closed so `8h` reads as `8 h`."""
    return _UNIT_GAP.sub("", norm(text))


def _hedge_before(text: str, end: int) -> str:
    """The hedge standing immediately before `end`, or "" when the figure stands on its own."""
    found = _HEDGE_TAIL.search(text[:end])
    return found.group(1) if found else ""


def _untraceable_words(phrases: Sequence[re.Match[str]], held: str) -> list[str]:
    """Every phrase saying a figure in words rather than as one, unless the record says it too.

    `phrases` is what §4.3's tables matched, one to several words each — `key`, `material impact`,
    `a working day` — which is why it is not named for the "words" in this function's own name:
    that word is the *figure said in words* the phrase stands in for.
    """
    return [found.group() for found in phrases if found.group() not in held]


def _name_spans(text: str, names: Sequence[str]) -> list[tuple[int, int]]:
    """Where each name the room supplies stands on the card, in the text the check reads.

    A span, never the name itself: what is exempt is the stretch of card the name occupies, so a
    figure standing next to one — or between two of them — is an ordinary untraceable figure.
    """
    return [found.span()
            for name in (_searchable(name) for name in names) if name
            for found in re.finditer(re.escape(name), text)]


def _inside_a_name(found: re.Match[str], name_spans: Sequence[tuple[int, int]]) -> bool:
    """Whether this figure or word stands inside one of the room's own names, not beside one."""
    return any(start <= found.start() and found.end() <= end for start, end in name_spans)


def _outside_the_names(pattern: re.Pattern[str], text: str,
                       name_spans: Sequence[tuple[int, int]]) -> list[re.Match[str]]:
    """Every match of `pattern` the room's own names do not cover, which is every one to check.

    The one place the exemption is applied, for both checks below: a name is exempt for its whole
    span, a figure and a vague word alike. A match the span only overlaps — `business critical`
    beginning inside `Group Business` and ending outside it — is not covered and is checked.
    """
    return [found for found in pattern.finditer(text)
            if not _inside_a_name(found, name_spans)]


def _held_with_the_same_hedge(held: str, figure: str, hedge: str) -> bool:
    """Whether the record holds this figure anywhere, carrying the hedge the card gave it."""
    return any(_hedge_before(held, at.start()) == hedge
               for at in re.finditer(re.escape(figure), held))


def _untraceable_figures(figures: Sequence[re.Match[str]], text: str, held: str) -> list[str]:
    """Every figure on the card the record does not hold, hedge included, in card order.

    `text` is the card the matches were found in, and is read for one thing only: the hedge
    standing immediately before each figure, which is part of what the record must hold.
    """
    untraced = []
    for figure in figures:
        hedge = _hedge_before(text, figure.start())
        if not _held_with_the_same_hedge(held, figure.group(), hedge):
            untraced.append(f"{hedge} {figure.group()}".strip())
    return untraced


def untraceable(card: str, record: Mapping[str, Any], names: Sequence[str] = ()) -> list[str]:
    """Every string on `card` the record does not hold. Empty means the card is verifiable.

    Both directions of §4.4, read against the same two lines: vagueness, where the card says in
    words what the record says as a figure, and invented precision, where the card says a figure
    the record does not hold — including one whose hedge the card dropped or added.

    `names` is what the room calls its departments, and the exemption the module docstring states:
    a name is never a figure and never a vague word, whatever it contains, where it stands
    **inside an occurrence of one of those names on this card** — its whole span and no wider.
    The names are never added to what the record holds: that wider form would let one `Halle 45`
    in a room license every bare `45`, and one `Key Accounts` every bare `key`, on every card of
    the walk.
    """
    text = _STRUCTURE.sub("", _searchable(card))
    held = _searchable(_held_text(record))
    name_spans = _name_spans(text, names)
    return (_untraceable_words(_outside_the_names(_VAGUE_RE, text, name_spans), held)
            + _untraceable_figures(_outside_the_names(_FIGURE, text, name_spans), text, held))


def render(stage: int, card: str, record: Mapping[str, Any], names: Sequence[str] = ()) -> str:
    """The card, iff the record holds every figure on it. The only door a card reaches a human by.

    The check is first, so a refused card is never rendered: there is nothing for the manager to
    read, no warning attached to a card they cannot judge, and nothing to carry to the sign-off.
    """
    untraced = untraceable(card, record, names)
    if untraced:
        raise CardGeneratorBug(stage, untraced, record)
    return card


def render_walk(cards: Sequence[str], record: Mapping[str, Any]) -> list[str]:
    """Every stage's card, each checked against the record before any of them is returned."""
    return [render(stage, card, record) for stage, card in enumerate(cards, 1)]

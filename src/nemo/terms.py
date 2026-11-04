"""Abbreviations and method terms, each followed by its plain name the first time a text uses it.

Ticket 107, on round 2's junior-manager standard: *"please don't use so many abbreviations. In the
beginning, you always have to explain what, for example, NTV is"* (r2-02). Naming the codes in the
tool results the model reads was not enough — after ticket 96 the model still wrote MTPD and MAP
bare in its own prose (r2-12) — so this runs over the text the manager is shown, the model's answer
included, before a front end draws it. It is a rendering of tables, never a check on what the model
wrote (M13).

Two tables, and only one of them is here. **Method terms are nemo's** (`METHOD_TERMS`): the words of
business continuity itself, in the plain words the guidance uses, the abbreviation kept so the
guidance still matches; the standard's own words among them are marked `STANDARD_TERMS` and are
named once in a conversation rather than once in each turn (ticket 215). **A room's own
abbreviations are the room's**: "NTV is the company that collects slaughter waste" is a fact about
one company, so it lives in that room's glossary file (`GLOSSARY`, read by `glossary`) and never in
this package.

The naming never touches someone's words, a code span or a link: a quote stays byte for byte. It
never lands inside a bold span, a heading or another bracket either (ticket 444). A signed
document never comes through here at all (ruling A): it keeps its codes.

Pure: text in, text out. The caller reads the room's files and hands their text over.
"""

from __future__ import annotations

import functools
import re
from collections.abc import Iterable, Mapping

#: The room's glossary: one bullet per term, `- **NTV**: the logistics company that collects
#: slaughter waste`. Room content, never code.
GLOSSARY = "01_Organisation/glossary.md"

#: nemo's own table: method terms only, each in the plain words a manager new to BCM reads. No
#: meaning carries an abbreviation (it would need a bracket of its own) or a figure (the chat's
#: figure check would take it for one).
METHOD_TERMS: Mapping[str, str] = {
    "BIA": "business impact analysis: what a stop does to the organisation over time",
    "BCM": "business continuity management",
    "BC": "business continuity",
    "MTPD": "how long the activity can be down before the damage is intolerable",
    "RTO": "how soon the activity must be back at its agreed minimum level",
    "RPO": "how far back the information it uses may be restored",
    "MBCO": "the least the activity must still deliver while it is disrupted",
    "SPOF": "single point of failure: one thing whose loss stops the activity",
    "N+1": "one spare beyond what is needed",
    "PIR": "post-incident review",
    "intolerability threshold": "the score at which a stop is no longer tolerable",
    "safety buffer": "the margin kept between how soon it must be back and how long it can be down",
    "MTPD anchor": "the first point in time at which a stop becomes intolerable",
    "grid-derived": "worked out from the impact scores over time",
    "canonical MTPD": "the one limit that counts: the tightest of all that apply",
}

#: t215, on the owner's words TYPED 2026-09-28T20:43:33Z ("basic terms such as BCM, RPO, etc must
#: not always be explained in ()"): the standard's own words. They are named **once per
#: conversation**, the first time they reach him or the model, and are said bare after that. Every
#: other entry of the table above keeps 107's naming, at its first use in each turn: SPOF, N+1 and
#: PIR are less basic (ticket 64's beginners), and the rest are nemo's own coined terms. The caller
#: keeps the conversation's set and hands it to `name_first_uses` as `already`.
STANDARD_TERMS: frozenset[str] = frozenset({"BCM", "BC", "BIA", "MTPD", "RTO", "RPO", "MBCO"})

#: Someone's words (in quote marks, or a blockquote line: nemo draws an interviewee's words as
#: "> " lines on a card), a code span, a fenced block, a link or an address: never renamed inside.
#: t418 r2 (35_nemo_check's ruling 2026-10-11): an item name in quote marks, single ones too, is a
#: quote, so it carries no gloss inside or after it.
_KEPT = re.compile(r"(```.*?```|`[^`\n]*`|\[[^\]\n]*\]\([^)\n]*\)|<https?://[^>\s]*>|https?://\S+"
                   r"|“[^”]*”|‘[^’\n]*’|\"[^\"\n]*\"|^>[^\n]*)", re.S | re.M)
#: What may not stand directly before or after a term for it to be one: a letter or digit, and
#: the joints of a code (R-SUP-03), a path (x/SUP), a file name (a.SUP) or a sum (SUP+).
_BEFORE, _AFTER = r"(?<![\w/.+-])", r"(?![\w+-])"


def _pattern(table: Mapping[str, str]) -> re.Pattern[str]:
    """One alternation, longest term first; a lower-case term matches in any case."""
    return _pattern_of(tuple(table))


def _built(terms: tuple[str, ...]) -> re.Pattern[str]:
    said = [f"(?i:{re.escape(t)})" if t.islower() else re.escape(t)
            for t in sorted(terms, key=len, reverse=True)]
    return re.compile(_BEFORE + "(" + "|".join(said) + ")" + _AFTER)


#: t438, on 431's profile: a tool result's every string asked for the same pattern again (32% of
#: CPU on room_state turns), so each is built once per table, and the name pattern once per names.
#: Wrapped here, not decorated: mutmut leaves a decorated function's body unmutated.
_pattern_of = functools.lru_cache(maxsize=64)(_built)


#: t444 (his A, 2026-10-12T15:49:43Z: "After the bold, never nested"): what a gloss never goes
#: inside: a heading line, a bold span and a bracket (one with no bracket inside it). The empty
#: match at the end makes the text's tail a plain run like any other.
#: t444 r2 (37_nemo_check's FORM FINAL 2026-10-13 00:21:44): a bold span with the owner bracket
#: after it is one span, so its gloss goes in that bracket, gloss first, owner after.
_SHELTER = re.compile(r"(^#[^\n]*|\*\*[^*\n]+?\*\*(?: \(owner: [^()\n]*\))?|\([^()\n]*\)|\Z)",
                      re.M)
_OWNER = re.compile(r" \((owner: [^()\n]*)\)$")
_BRACKET = re.compile(r"\([^()\n]*\)")
#: a bold span that is a heading: the line's start, then the line's end or " · " and a source
_HEADED = re.compile(r"(?: · [^\n]*)?(?:\n|$)")


def _said_after(said: str, after: str, new: list[str], table: Mapping[str, str],
                used: set[str]) -> str:
    """t377 M, t444: `said` with the first uses `new` it holds named after it in one bracket,
    each counting as used. Not where a bracket follows: a gloss there would stand back to back
    with it, so they wait for a bare use (one the text writes for them, "(CSB: …)", names them:
    `_bracketed`)."""
    if not new or re.match(r"\s*\(", after):
        return said
    return f"{said} ({'; '.join(_glossed(new, table, used))})"


def _glossed(new: list[str], table: Mapping[str, str], used: set[str]) -> list[str]:
    """`new` as `TERM: meaning` each, the parts of one bracket, each counting as used."""
    used.update(new)
    return [f"{t}: {table[t]}" for t in new]


def _names_pattern(names: Iterable[str], pattern: re.Pattern[str]) -> re.Pattern[str] | None:
    """t377 M: one alternation of the item names that hold a term, each before any it extends."""
    return _names_pattern_of(frozenset(names), pattern)


def _names_built(names: frozenset[str], pattern: re.Pattern[str]) -> re.Pattern[str] | None:
    # reverse order puts every name before any name it extends (a prefix sorts first), so the
    # alternation takes the whole name
    held = sorted({n for n in names if pattern.search(n)}, reverse=True)
    return re.compile(r"(?<!\w)(" + "|".join(map(re.escape, held)) + r")(?!\w)") if held else None


_names_pattern_of = functools.lru_cache(maxsize=256)(_names_built)


def _first_in(name: str, table: Mapping[str, str], pattern: re.Pattern[str],
              used: set[str]) -> list[str]:
    """t377 M: the terms `name` holds that are not used yet, in their order, each once."""
    lookup = {t.casefold(): t for t in table}
    held = dict.fromkeys(lookup[u.casefold()] for u in pattern.findall(name))
    return [t for t in held if t not in used]


def _name_said(name: str, after: str, table: Mapping[str, str], pattern: re.Pattern[str],
               used: set[str]) -> str:
    """t377 M: an item name whole, the first uses inside it named after it in one bracket."""
    return _said_after(name, after, _first_in(name, table, pattern, used), table, used)


def _bracketed(said: str, table: Mapping[str, str], pattern: re.Pattern[str],
               used: set[str]) -> None:
    """t444: a bracket is never glossed inside. The text's own naming counts as used: a term that
    is the whole bracket, "(ABP)", or opens a part of it with a colon, "(CSB: …; ERP: …)"."""
    lookup = {t.casefold(): t for t in table}
    used.update(lookup[m.group(1).casefold()] for m in pattern.finditer(said)
                if said[:m.start()].endswith(("(", "; ")) and said[m.end()] in (":", ")"))


def name_first_uses(text: str, table: Mapping[str, str], already: frozenset[str] = frozenset(),
                    names: Iterable[str] = ()) -> tuple[str, frozenset[str]]:
    """`text` with each term of `table` followed by its plain name the first time it is used,
    and the terms used so far. `already` holds those used earlier in the same turn, which stay
    bare. A use inside someone's words, a code span or a link is left as it is and is not a first
    use; a use the text brackets itself counts as named.

    t377 M: `names` are item names a term may stand inside ("CSB ERP Marschkamp"). A name is
    never broken: the first uses inside it are named after the whole name, once each, in one
    bracket, "CSB ERP Marschkamp (CSB: …; ERP: …)".

    t444 (his A, 2026-10-12T15:49:43Z: "After the bold, never nested"): a bold span's gloss goes
    after it the same way, "**CSB ERP Marschkamp** (CSB: …; ERP: …)"; a heading carries none, and
    a term inside another bracket is not glossed there: each waits for its first bare use, as one
    that a bracket follows does, so no two brackets stand back to back.

    t444 r2 (37_nemo_check's FORM FINAL 2026-10-13 00:21:44): a bold name's owner bracket takes
    its gloss, gloss first, "**CSB ERP Marschkamp** (CSB: …; ERP: …; owner: Head of IT
    Operations)", so a first use there always has somewhere to land."""
    if not table:
        return text, already
    pattern = _pattern(table)
    whole = _names_pattern(names, pattern)
    said = _Pass(table, pattern, whole, set(already))
    out = "".join(piece if n % 2 else said.one(piece) for n, piece in enumerate(_KEPT.split(text)))
    return out, frozenset(said.used)


class _Pass:
    """One text's naming: the table, its patterns and the terms used so far."""

    def __init__(self, table: Mapping[str, str], pattern: re.Pattern[str],
                 whole: re.Pattern[str] | None, used: set[str]) -> None:
        self.table, self.pattern, self.whole, self.used = table, pattern, whole, used
        self.lookup = {t.casefold(): t for t in table}

    def one(self, piece: str) -> str:
        """A piece outside someone's words: its plain runs named, its sheltered spans kept."""
        out, at = [], 0
        for m in _SHELTER.finditer(piece):
            out += [self.plain(piece[at:m.start()], piece[m.start():]), self.sheltered(piece, m)]
            at = m.end()
        return "".join(out)

    def plain(self, part: str, after: str) -> str:
        """A plain run, `after` the text that follows it: names whole, terms where they stand."""
        out, at = [], 0
        for m in self.whole.finditer(part) if self.whole else ():
            out += [self.terms_in(part[at:m.start()], part[m.start():] + after),
                    _name_said(m.group(), part[m.end():] + after, self.table, self.pattern,
                               self.used)]
            at = m.end()
        return "".join([*out, self.terms_in(part[at:], after)])

    def terms_in(self, part: str, after: str) -> str:
        def rep(m: re.Match[str]) -> str:
            term = self.lookup[m.group(1).casefold()]
            if term in self.used:
                return m.group(1)
            rest = part[m.end():] + after
            if re.match(r" ?\(", rest):  # the text names it itself: "NTV (the renderer)"
                self.used.add(term)
                return m.group(1)
            if part[:m.start()].endswith("(") or re.match(r"\s*\(", rest):
                return m.group(1)  # t444: inside a bracket, or back to back with one
            self.used.add(term)
            return f"{m.group(1)} ({self.table[term]})"
        return self.pattern.sub(rep, part)

    def sheltered(self, piece: str, m: re.Match[str]) -> str:
        """t444: a bracket or a heading as it is; a bold span whole, its gloss after it."""
        said, after = m.group(), piece[m.end():]
        if said.startswith("("):
            _bracketed(said, self.table, self.pattern, self.used)
            return said
        owner = _OWNER.search(said)
        if owner:  # t444 r2: "**X** (X's terms: …; owner: …)", one bracket, never back to back
            bold = said[:owner.start()]
            new = self.new_in(bold)
            _bracketed(owner.group(), self.table, self.pattern, self.used)
            return f"{bold} ({'; '.join([*_glossed(new, self.table, self.used), owner[1]])})"
        if (piece[:m.start()].endswith("\n") or not m.start()) and _HEADED.match(after):
            return said  # a heading ("## …", or a bold line): its terms wait for a plain use
        return _said_after(said, after, self.new_in(said), self.table, self.used)

    def new_in(self, bold: str) -> list[str]:
        """A bold span's first uses outside its own brackets, which name theirs."""
        for inner in _BRACKET.findall(bold):
            _bracketed(inner, self.table, self.pattern, self.used)
        return _first_in(_BRACKET.sub("", bold), self.table, self.pattern, self.used)


_ENTRY = re.compile(r"^[-*]\s+\*\*(?P<term>[^*]+)\*\*:\s*(?P<meaning>.+?)\s*$", re.M)


def glossary(text: str) -> dict[str, str]:
    """A room's glossary file, term -> plain name, from its `- **TERM**: meaning` bullets."""
    return {m.group("term"): m.group("meaning") for m in _ENTRY.finditer(text)}


# ── the completeness check ───────────────────────────────────────────────────────────────────────
#: Two capitals or more, digits allowed after the first (PP4, ERP, FY2025), and the one sum the
#: method writes (N+1). A code (HACCP-01) is ticket 96's and not an abbreviation here.
_ABBREVIATION = re.compile(_BEFORE + r"([A-Z][A-Z0-9]*[A-Z][A-Z0-9]*|[A-Z]\+\d)" + _AFTER)
_ROMAN = re.compile(r"[IVX]+")
#: English words a file writes in capitals, and a date's placeholders: none of them stands for
#: anything. Any word of six letters or more in capitals is taken for a word shouted, too.
_WORDS = frozenset({"NO", "NOT", "YET", "PER", "AND", "OR", "TEST", "FILE", "GAP",
                    "DD", "MM", "YYYY"})


def _abbreviation(token: str) -> bool:
    return not (_ROMAN.fullmatch(token) or token in _WORDS or (len(token) > 5 and token.isalpha()))


def abbreviations(text: str) -> set[str]:
    """Every abbreviation `text` uses."""
    return {t for t in _ABBREVIATION.findall(text) if _abbreviation(t)}


def undefined(texts: Iterable[str], table: Mapping[str, str]) -> list[str]:
    """The abbreviations `texts` use that `table` does not name, sorted: a room's files against its
    glossary and nemo's method terms. Empty is the bar for a room a manager walks."""
    return sorted({t for text in texts for t in abbreviations(text)} - set(table))

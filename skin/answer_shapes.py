"""Ticket 603 (ADR-0061 decision 3, map N1): the answer shapes, and the rules every answer keeps.

His approved page, `docs/answer-shapes.md`, as data: sixteen kinds of question, each a shape of
slots and order (the first line, the parts that follow in order, what to name where the files do
not say), never a sentence. The model picks the shape by calling its tool; a question no shape fits
gets the free answer (`FREE`, rule 6), checked the same way. Thirteen kinds are text shapes built
here (`TEXT`); the e-mail drafts, the invitation and the chart are `led_turn`'s own tools, their
rows kept here so the page is one table in code too.

- **A shape holds slots and order only** (`held`): no name, figure or date of the room.
- **The rules on every answer** (`judge`): the first line's rule of its kind and no preamble (1, 5),
  at most six reasons (2), "Not stated" last (3), who decides beside a proposal (4), two figures
  that disagree each with who said it (7), next steps that follow from the answer and say what
  they do, never the BCM manager accepting an owner's figure himself (8), an e-mail step only where
  the answer leaves something with owners (9), the same count in every part, in its taps and in
  an earlier answer on the same activity (11), no explanation inside a table (12). Rule 10, a
  graph only when he asks for one, is `drawn_unasked`; the drafts kind's checks are the letter's.
- **The drafts kind** (591, 594): a numbered letter keeps its numbers (`unnumbered`), a date the
  room holds stands as cited (`held_dates`), and a body with a part for each of several owners
  gives each owner only his part (`section`).

The checks read the text, the room's files and his lines; none is a model, and `checks.py` keeps
the facts' stack (607 owns its refusals).
"""

from __future__ import annotations

import functools
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import checks

from nemo import walk

import PROTOTYPE_core as core
import PROTOTYPE_draft as drafting
import PROTOTYPE_words as words

#: rule 6: the free answer, for a question no shape fits
FREE = "answer"
#: the page's other three rows, built in `led_turn` (its `LETTER`, `INVITATION`, `CHART`)
DRAFTS, INVITE, CHART = "letter", "invitation", "impact_over_time"
#: the drafts kind's first line, code's (the page's words), and its count's noun; 629: "ready for
#: Drafts" until his tap has placed them, "in Drafts" only once it has (his "Say ready for Drafts")
DRAFTS_FIRST = "Drafts for {n} {people}, ready for Drafts, not sent"
DRAFTS_PLACED = "Drafts for {n} {people}, in Drafts, not sent"
#: 753: the letter shown again and already placed: nothing changed, and where the drafts still are.
#: DRAFTS_PLACED stays his tap's words, a first tap having just written a draft
DRAFTS_UNCHANGED = "Drafts for {n} {people}, unchanged, in Drafts, not sent"
#: rule 3: the last line of an answer, code's heading over what the files do not say
NOT_STATED = "Not stated: {items}"
#: rule 2: reasons at most
REASONS = 6

_COUNT = r"(?:\d+|" + "|".join(checks.SPELLED) + r")"
#: 738: the lead a true count keeps ("Yes, 3 mismatches…"), in digits as `_listed` reads a count
_MISMATCHES = re.compile(r"\W*yes\W+([1-9]\d*)\s+mismatches\b", re.I)


@dataclass(frozen=True)
class Shape:
    """One row of the page: the tool's name, the kind of question, the first line, the parts in
    order, what to name where the files do not say, and the first line's rule as code reads it
    (`opens`, a pattern; "" where code writes the first line itself)."""

    name: str
    kind: str
    first: str
    then: tuple[str, ...]
    missing: str
    opens: str = ""
    #: the dependency kind: code draws the graph's link over the parts (757)
    link: bool = False


SHAPES: tuple[Shape, ...] = (
    Shape("what_changed", "What changed since last year",
          "what matters most, with its effect", (
              "each change, one line", "what did not change", "other interviews this year"),
          "which figures are still open (RTO, MTPD)",
          r"\d|\b(?:MTPD|RTO|RPO|level|impact|days?|hours?)\b|" + _COUNT),
    Shape("mismatch", "What does not match last year or the grid",
          "'Yes, N mismatches' or 'No'", (
              "each mismatch: its class, this year against last year",
              "the knock-on (MTPD, RTO no longer below it)"),
          "cells last year did not rate ('not a change')",
          rf"^(?:Yes,\s+{_COUNT}\s+mismatch(?:es)?\b|No\b)"),
    Shape("how_long_down", "How long can it be down",
          "the time now against last year, as at most one before/after pair, in days where "
          "plainer", (
              "why (which classes hit high when)", "the money per day, if stated",
              "who decides"),
          "the owner's own figure if he left it open, quoted",
          rf"^\W*(?:about\s+|around\s+|up\s+to\s+|at\s+most\s+)?{_COUNT}(?:[.,]\d+)?\s*"
          r"(?:days?|hours?|h|weeks?)\b"),
    Shape("quotes", "The quote behind each gap", "one line naming how many gaps", (
        "per gap: the gap in plain words, the speaker's function, the quote",),
        "a gap with no quote", rf"\b{_COUNT}\s+(?:\w+\s+)?gaps?\b|\bno\s+(?:\w+\s+)?gaps?\b"),
    Shape("who_decides", "Who decides on the open gaps", "'N people decide, one each: ...'", (
        "per person: what they own, the quote or record behind it",),
        "the deadline, who signs off",
        rf"^\W*{_COUNT}\s+(?:people|persons?|functions?|owners?)\s+decides?\b"),
    Shape("dependencies", "Dependencies, this year against last year or of one process",
          "how many, and how many have no workaround", (
              "changed or new this year", "the list, each with its workaround or 'not stated'",
              "the graph's link (nemo draws it)"),
          "owners not stated", rf"{_COUNT}\b.*\bworkarounds?\b", link=True),
    Shape("spof", "Single points of failure, missing workarounds",
          "'Yes, N have no workaround' or 'No'", (
              "each one with its owner and why it matters", "then those that do have one"),
          "rows with no workaround stated",
          rf"^(?:Yes,\s+{_COUNT}\b(?:\s+\w+){{0,3}}\s+(?:have|has)\s+no\s+workarounds?\b|No\b)"),
    Shape("due", "Which BIAs are due", "the due list, with the date as of today", (
        "per process: last BIA, due date, overdue or not, re-interview status",),
        "how many others are current",
        r"\b\d{1,2}\s+(?:" + "|".join(checks._MONTHS) + r")\w*\b|\b\d{4}-\d\d-\d\d\b"),
    Shape("next_bia", "Which BIA next, and why", "the process and the planned date", (
        "why (overdue since, what it feeds)", "why not the others"),
        "the process owner to invite",
        r"\b\d{1,2}\s+(?:" + "|".join(checks._MONTHS) + r")\w*\b|\b\d{4}-\d\d-\d\d\b"),
    Shape("who_comes", "Who to invite, who was there", "the people to invite, by function", (
        "who was there last time", "who to add, and why"), "a deputy not named",
        r"\b(?:Head|Manager|Officer|CEO|Director|Lead)\b"),
    Shape("focus", "What we asked last year, the focus now", "the focus points, numbered", (
        "last year's grid as a table", "RTO and MTPD from the record"),
        "suppliers or dependencies with no workaround", r"(?:^|\s)\(?1[.)]\s"),
    Shape("what_to_check", "What should I still check", "'Before <date>, check these yourself:'",
          ("each item: what, why the files cannot settle it, whom to ask",),
          "a date clash between plan and request", r"^Before\b.+\bcheck these yourself\b"),
    Shape("briefing", "A briefing to print", "the title and why now", (
        "last year's grid", "the dependencies table", "the open points"),
        "approval not recorded", r"^\W*\S+(?:\s+\S+){0,15}\s*$"),
    Shape(DRAFTS, "Letter drafts",
          "'Drafts for N people, ready for Drafts, not sent' (nemo writes it)", (
              "each draft: to whom (function), subject, the body shown",),
          "anyone with no address in the files"),
    Shape(INVITE, "Invitation, or move it", "the date and time as now planned (nemo writes it)", (
        "who is invited", "the tap to confirm or move", "'nothing is sent'"),
        "a clash with the programme plan"),
    Shape(CHART, "A chart, drawn or changed", "the chart (nemo draws it)", (
        "one caption line on what it shows", "the money line, if stated"),
        "classes with no rating"),
)
BY_NAME = {s.name: s for s in SHAPES}
#: the shapes this module builds as tools: the text kinds
TEXT = tuple(s.name for s in SHAPES if s.opens)


# ── a shape holds slots and order only ──────────────────────────────────────────────────────────
def _said(shape: Shape) -> str:
    return "\n".join([shape.kind, shape.first, *shape.then, shape.missing])


def held(shape: Shape, folder: Path) -> list[str]:
    """What of the room a shape holds (none may stand): a figure, a date, a person's name or
    first name, a function the organisation file names, an activity's name."""
    said = _said(shape)
    found = [*re.findall(r"\d+", said), *(m[0] for m in checks.DATE.finditer(said))]
    people = words.people(folder)
    names = {*people, *(p.split()[0] for p in people), *words.functions(folder),
             *(core.map_name(folder, a) for a in walk.processes(folder))}
    return found + sorted(n for n in names if re.search(rf"\b{re.escape(n)}\b", said, re.I))


# ── the tools ───────────────────────────────────────────────────────────────────────────────────
_S: dict[str, Any] = {"type": "string"}
_L: dict[str, Any] = {"type": "array", "items": _S}
STEPS_SAID = ("next_steps: two or three next steps that follow from this answer, each saying what "
              "it does (Ask, Write, Show, Compare...); a step that writes to an owner ends with "
              f"'{core.MAIL_MARK.strip()}' and is offered only where the answer leaves something "
              "with owners; never one that lets him accept an owner's figure himself.")
_ARGS = {"answer": _S, "details": _L, "not_stated": _L, "next_steps": _L}


def _tool(name: str, says: str) -> dict[str, Any]:
    return {"type": "function", "function": {"name": name, "description": says, "parameters": {
        "type": "object", "properties": _ARGS, "required": ["answer"]}}}


def tools() -> list[dict[str, Any]]:
    """One tool per text shape, its description the page's row (slots and order only), then the
    free answer (rule 6)."""
    return [*(_tool(s.name, f"{s.kind}. answer: the first line, {s.first}. details: then, in "
                    f"order, one line each: {'; '.join(s.then)}. not_stated: {s.missing}, where "
                    f"the files do not say. {STEPS_SAID}")
              for s in SHAPES if s.name in TEXT),
            _tool(FREE, "The free answer, for a question no other shape fits: answer: the first "
                  "line answers the question; details: the reasons, one line each, most "
                  "important first, at most six; not_stated: what the files do not say. "
                  + STEPS_SAID)]


# ── what he sees ────────────────────────────────────────────────────────────────────────────────
#: 713: the bullets a line already opens on ("**Bold**" is no bullet)
_BULLETED = re.compile(r"^(?:[-*](?:\s+|$)|•\s*)+")


def _line(x: Any) -> str:
    said = _BULLETED.sub("", str(x).strip())  # 713: one bullet, none with nothing left
    return said if not said or said.startswith("|") else f"- {said}"


def render(name: str, a: dict[str, Any], link: str = "") -> str:
    """A shape as he reads it: the graph's link first where the kind draws one (757), the first
    line, then its parts one per line in the order the model gave (a table's rows as they are), and
    what the files do not say as the last line (rule 3)."""
    unsaid = [str(x).strip() for x in checks.as_list(a.get("not_stated")) if str(x).strip()]
    parts = "\n".join(checks.rowless("\n".join(
        x for x in map(_line, checks.as_list(a.get("details"))) if x).split("\n")))
    return "\n\n".join(filter(None, [
        link if BY_NAME.get(name, SHAPES[0]).link and name in TEXT else "",
        str(a.get("answer") or "").strip(), parts,
        NOT_STATED.format(items="; ".join(unsaid)) if unsaid else ""]))


#: 754: a bar with its spaces; one opening a line, its list marks kept; a table's separator
_BAR = re.compile(r"(?:[ \t]*\|)+[ \t]*")
_OPENING_BAR = re.compile(r"^(\s*(?:(?:[-*+]|\d+\.)\s+)*)\|[ \t]*")
_BARE_SEPARATOR = re.compile(r"\s*:?-+:?\s*(?:\|\s*:?-+:?\s*)+\|?\s*")
_BARRED_SEPARATOR = re.compile(r"\s*\|[\s:|-]*-[\s:|-]*")
_BULLET = re.compile(r"^\s*[-*+] ")
#: 754: a stop and what may close it, what may open the next, and the words that make a sentence,
#: so a name or a bare cell ("Müller & Co. | Beta Ltd.") is none
_STOPPED = re.compile(r"[.!?\u2026][\"'\u201c\u201d\u2019\u00ab\u00bb)*_]*$")
_OPENING_MARKS = " \"'\u201c\u201e\u2018\u00ab\u00bb([*_"
_SENTENCE_WORDS = 3


def _prose_bars(line: str) -> list[str]:
    """754: a prose line, cut where a bar stands between two sentences; a bar elsewhere stays, and
    one inside bold, a link or code, which a cut would leave open."""
    def between(m: re.Match[str]) -> str:
        said = _bare(line[:m.start()])
        left = _BULLET.sub("", said.rpartition("|")[2]).strip()
        right = _bare(line[m.end():]).partition("|")[0]
        opens = right.lstrip(_OPENING_MARKS)[:1]
        return "\n" if _STOPPED.search(left) and (opens.isupper() or opens.isdigit()) \
            and min(len(left.split()), len(right.split())) >= _SENTENCE_WORDS \
            and not (said.count("**") % 2 or said.count("`") % 2
                     or said.count("[") > said.count("]")) else m[0]
    return _BAR.sub(between, line).split("\n")


def _block_bars(block: str) -> str:
    lines = block.split("\n")
    # ponytail: prose set tight above a table with no outer bars keeps its bar, as that table's row
    if "```" in block or any(_BARE_SEPARATOR.fullmatch(x) for x in lines):
        return block
    one_column = any(_BARRED_SEPARATOR.fullmatch(x) for x in lines)  # "| Item" under "|---"
    out: list[str] = []
    for line in lines:
        bare = _bare(line).strip()
        if _OPENING_BAR.match(bare) and (bare.count("|") > 1 or one_column):
            out.append(line)  # a row, open at its end or not
            continue
        opened = _OPENING_BAR.sub(r"\1", line)
        if opened != line and not opened.strip(" -*+"):  # the bar was all it said
            continue
        first, *rest = _prose_bars(opened)
        # a list item joins a plain next line, so what the bar parted stays an item of its own
        if opened != line and out and _BULLET.match(out[-1]) and not _BULLET.match(first):
            first = f"- {first}"
        mark = _BULLET.match(first)
        out += [first, *((mark[0] if mark else "") + r for r in rest)]
    return "\n".join(out)


def without_stray_bars(text: str) -> str:
    """754: text as he reads it: a bar between two sentences of prose is a line break, one opening a
    line goes; a table's row keeps every bar, and a bar inside a sentence stays. No word changes."""
    return "\n\n".join(map(_block_bars, text.split("\n\n")))


# ── the rules on every answer ───────────────────────────────────────────────────────────────────
Place = checks.Place
PREAMBLE = re.compile(r"^\W*(?:sure|certainly|of course|here (?:is|are)|let me|based on|according "
                      r"to|great|thanks|to answer|i (?:have|will|can|checked|looked|found))\b",
                      re.I)
OPENS = "its first line does not give {first}, as the {kind} shape opens"
PREAMBLE_SAID = "its first line is a preamble: the first line answers the question"
TOO_MANY = "more than {n} reasons: the most important {n}, one per line"
PAIRS = "its first line holds more than one before/after pair"
IN_DAYS = "it says {hours} hours where {days} days is plainer"
METHOD = "it says 'the method' without saying what it is"
NO_DECIDER = "it gives a figure as a proposal and does not name who decides"
DISAGREE = "it shows two figures that disagree without who said each"
TABLE = "an explanation inside a table: the table holds figures, the explanation goes under it"
STEP_DOES = "the next step {step!r} does not say what it does"
STEP_FIXED = "the next step {step!r} does not follow from this answer"
STEP_ACCEPT = ("the next step {step!r} lets him accept an owner's figure himself: the figure goes "
               "back to the owner")
STEP_MAIL = "the next step {step!r} writes to owners, and this answer leaves nothing with them"
STEP_FACT = "the next step {step!r} states {facts}, which the answer does not"
SAME_COUNT = "it says {said}, where {where} says {other}: the same count is the same everywhere"

_PAIR = re.compile(r"\bfrom\b[^.;]*?\bto\b|→|\bagainst\b|\bvs\.?\s|\binstead of\b", re.I)
_THE_METHOD = re.compile(r"\bthe method\b(?!\s*\(|\s*[:–—]|['’]s\b|\s+(?:of|for|in)\s|\s+file\b)",
                         re.I)
_PROPOSAL = re.compile(r"\bpropos\w*", re.I)
_PROPOSED = re.compile(rf"\d|\b{_COUNT}\s+(?:days?|hours?|weeks?)\b", re.I)
_DECIDES = re.compile(r"\bdecides?\b|\bsigns? off\b", re.I)
_MEASURE = re.compile(r"\b(MTPD|RTO|RPO)\b", re.I)
_FIGURE = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:days?|hours?|h|weeks?)\b", re.I)
_CHANGE = re.compile(r"\bfrom\b.+\bto\b|\b(?:falls?|rises?|fell|rose|drops?|changed?)\b|→"
                     r"|\blast year\b.*\bthis year\b|\bthis year\b.*\blast year\b", re.I)
_SOURCES = re.compile(r"\b(?:record|register|interview|plan|method|grid|last year|this year|"
                      r"said|says|states?)\b", re.I)
#: rule 8: the verbs a next step opens with, so it says what it does
DOES = ("ask", "write", "draft", "show", "compare", "open", "start", "check", "invite", "move",
        "read", "list", "prepare", "draw", "plan", "name", "find", "put", "see", "add", "quote",
        "explain", "book", "block", "review")
#: rule 8: words a step shares with any answer, which say nothing of this one
_EMPTY_WORDS = frozenset({
    "the", "and", "for", "with", "about", "this", "that", "them", "these", "those", "all", "any",
    "its", "his", "her", "our", "your", "from", "into", "more", "next", "now", "what", "who",
    "which", "how", "why", "each", "one", "process", "processes", "activity", "file", "files",
    "answer", "mail"})
#: rule 8: a step that has him settle a figure himself
_ACCEPT = re.compile(r"\b(?:accept|approve|adopt|confirm|sign(?:\s+it)?\s+off|take over|agree to|"
                     r"set|fix)\b", re.I)
_A_FIGURE = re.compile(r"\d|\b(?:figure|RTO|MTPD|RPO|value|estimate|proposal|target|rating|score|"
                       r"level)s?\b", re.I)
_TO_OWNER = re.compile(r"^\W*(?:ask|write|e-?mail|draft)\b", re.I)
#: rule 9: what an answer leaves with owners
_LEFT_WITH_OWNERS = re.compile(r"\bdecides?\b|\bto confirm\b|\bopen\b|\bgaps?\b|\bnot (?:stated|"
                               r"named|given|recorded)\b|\bpropos\w*|\bunconfirmed\b", re.I)
_MAILS = re.compile(r"(?:[\s.]*\(E-?mail\))+[\s.,;:!?]*$", re.I)
#: 746: one word in brackets, by its shape and never a list of names, no figure; the mark may come
#: unclosed
_ONE_WORD = re.compile(r"\((?:(?i:E-?mail)(?![\w-])\)?|[^\W\d][\w-]*\))")
_CLOSING = re.compile(rf"(?:[\s.]*{_ONE_WORD.pattern})+[\s.,;:!?\"]*$")
#: 746: a bracket ending a sentence, and a new sentence after it: a step that holds several
_SEVERAL_STEPS = re.compile(r"(\([^\W\d][\w-]*\))[ \t]*[.!?;|\n][\s.!?;|]*(?=[A-ZÄÖÜ])")
#: 746: raw quote marks between steps, each opening as a step does (rule 8), capital included: a
#: quoted "open", "check" is a step's own words
_QUOTE_JOINED = re.compile(rf'"\s*,?\s*"(?=(?:{"|".join(d.capitalize() for d in DOES)})\b)')
#: rule 11: a count and what it counts
#: 640 (b): a first line's count disagreeing with the points listed under it
LISTED_OFF = "it says {said}, and {listed} are listed under it"
#: 640 (a): the shape-only misses, as patterns of their reasons (`noted`)
_OPENS_SAID, _IN_DAYS_SAID = (re.compile(re.sub(r"\\\{\w+\\\}", ".+", re.escape(x)), re.S)
                              for x in (OPENS, IN_DAYS))
#: 640 (c): hours said where whole days are plainer, and not already said beside them
_IN_HOURS = re.compile(r"\b(\d+)\s*(?:h|hours?)\b(?!\s*\(\d+\s*days?\))", re.I)


def _n(said: str) -> int:
    return int(said) if said.isdigit() else checks.SPELLED.index(said.lower()) + 1


def _counts(text: str) -> dict[str, int]:
    """Each thing the text counts (its last word, singular), and the count."""
    out: dict[str, int] = {}
    for m in checks.LISTED.finditer(_bare(text)):
        noun = re.sub(r"(?:es|s)$", "", m[2].split()[-1].lower()).replace("dependenci", "dependenc")
        out.setdefault(noun, _n(m[1]))
    return out


def _bare(text: str) -> str:
    return checks.CITE.sub("", checks.each_cite(text))


def _cells(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


def _explains(row: str) -> bool:
    """Rule 12: a table row holding an explanation (a cell of more than five words, or a clause)."""
    if re.fullmatch(r"[\s|:-]+", row):
        return False
    return any(len(c.split()) > 5 or re.search(r"\b(?:because|since|which|so that)\b|\.\s", c)
               for c in _cells(_bare(row)))


def _days(h: str) -> int | None:
    return int(h) // 24 if int(h) >= 48 and int(h) % 24 == 0 else None


def _first(name: str, first: str, details: list[Any], folder: Path,
           activity: str | None = None) -> list[str]:
    """Rules 1 and 5 on the first line, and (640 b) its count against the points under it. A
    shape-only miss (`noted`) leaves room for the next rule; IN_DAYS on a line that stands."""
    bare = _bare(first).strip()
    if PREAMBLE.search(bare):
        return [PREAMBLE_SAID]
    shape = BY_NAME.get(name)
    out = [OPENS.format(first=shape.first, kind=shape.kind.lower())] \
        if shape and shape.opens and not re.search(shape.opens, bare, re.I) else []
    if why := PAIRS if len(_PAIR.findall(bare)) > 1 else _listed(
            shape, bare, details, folder, activity):
        return [*out, why]
    if h := next((int(x) for x in _IN_HOURS.findall(bare) if _days(x)), None):
        out.append(IN_DAYS.format(hours=h, days=h // 24))
    return out


def true_mismatches(bare: str, folder: Path, activity: str | None) -> bool:
    """738: a "Yes, N mismatches" lead whose N is the number of categories code has moved on the
    turn's activity (`core.grid_mismatches`; the knock-on is not one), said of no other activity."""
    m = _MISMATCHES.match(bare)
    grid = core.grid_mismatches(folder, activity) \
        if m and activity and set(core.named_in(folder, bare)) <= {activity} else None
    return m is not None and grid is not None and int(m[1]) == len(grid["moved"])


def _listed(shape: Shape | None, bare: str, details: list[Any],
            folder: Path | None = None, activity: str | None = None) -> str | None:
    """640 (b): the first line's own count (its first, said in digits) is the number of points
    listed under it: their lines (the shape's later parts, one line each, may follow them), or the
    items of a line listing them at semicolons. 664: a total code checks against the table
    (`checks.opens_on_a_total`) is never read against the points; 738: nor is a true mismatch count
    (`true_mismatches`)."""
    points = [_bare(str(d)) for d in details if str(d).strip() and not str(d).lstrip()
              .startswith("|")]
    if not points:
        return None
    later = len(shape.then) - 1 if shape else 0
    held = {len(points) - k for k in range(later + 1)} | {
        len(p.split(";")) for p in points if ";" in p}
    m = checks.LISTED.search(bare)
    if m and folder and (checks.opens_on_a_total(bare, folder)
                         or true_mismatches(bare, folder, activity)):
        return None
    return LISTED_OFF.format(said=f"{m[1]} {m[2]}", listed=len(points)) \
        if m and m[1].isdigit() and int(m[1]) not in held else None


def noted(why: str) -> bool:
    """640 (a): a shape-only miss (`OPENS`, `IN_DAYS`) is a finding, never a cut: the part stands
    and the turn is not failed by it (until `OPENS` is tuned on the saved runs)."""
    return any(p.fullmatch(why) for p in (_OPENS_SAID, _IN_DAYS_SAID))


def in_days(text: str) -> str:
    """640 (c): each whole number of days said in hours, the days code computed beside it
    ("72 hours (3 days)")."""
    return _IN_HOURS.sub(lambda m: f"{m[0]} ({d} days)" if (d := _days(m[1])) else m[0], text)


def _line_rules(text: str, functions: list[str]) -> str | None:
    """Rules 5 ('the method'), 7 and 12 on one part."""
    if text.lstrip().startswith("|"):
        return TABLE if _explains(text) else None
    if _THE_METHOD.search(text):
        return METHOD
    bare = _bare(text)
    marks = list(_MEASURE.finditer(bare))
    figures: dict[str, set[str]] = {}
    for m, end in zip(marks, [x.start() for x in marks[1:]] + [len(bare)], strict=False):
        figures.setdefault(m[1].upper(), set()).update(
            re.sub(r"\s+", " ", f.lower()) for f in _FIGURE.findall(bare[m.end():end]))
    if any(len(f) > 1 for f in figures.values()) and not _CHANGE.search(bare):
        if len(_SOURCES.findall(bare)) + sum(f in bare for f in functions) < 2:
            return DISAGREE
    return None


def _dates(text: str) -> set[tuple[str, str]]:
    """641 (d): the dates a text says, each as (its day and month as the facts' stack reads them,
    its year or "")."""
    return {(f"{m['day']} {m['month']}", m["year"] or "")
            for m in checks.DATE.finditer(checks._iso(text))}


def _room_dates(folder: Path) -> set[tuple[str, str]]:
    """641 (d): the dates the room's files hold: the programme plan's and the interviews'."""
    plan = folder / core.PROGRAMME_PLAN
    return _dates("\n".join([plan.read_text(encoding="utf-8") if plan.is_file() else "",
                             *drafting.interviews(folder).values()]))


def _unheld(step: str, held: set[tuple[str, str]]) -> str:
    """641 (d): the step with each date a file of the room holds taken out, its year with it; a
    date said with no year (or held with none) is held where the day is held in any year. Any
    other figure stays, a year said apart from a held date too."""
    def out(m: re.Match[str]) -> str:
        day, year = f"{m['day']} {m['month']}", m["year"] or ""
        return " " if {(day, year), (day, "")} & held or not year and any(
            d == day for d, _ in held) else m[0]
    return checks.DATE.sub(out, checks._iso(checks._bare(step)))


def _step_rules(step: str, said: str, leaves: bool,
                held: Callable[[], set[tuple[str, str]]] = set) -> str | None:
    """Rules 8 and 9 on one next step; a date it names may be one the room's files hold
    (`held`, 641)."""
    bare = _MAILS.sub("", step).strip()
    first = (re.match(r"[\w-]+", bare) or [""])[0].lower()
    if _ACCEPT.search(bare) and _A_FIGURE.search(bare) and not _TO_OWNER.search(bare):
        return STEP_ACCEPT.format(step=step)
    if first not in DOES:
        return STEP_DOES.format(step=step)
    mails = bool(_MAILS.search(checks._uncited(checks.each_cite(step)))) \
        or core.asks_to_write(bare)
    if mails and not leaves:
        return STEP_MAIL.format(step=step)
    if (off := [f for f in checks.facts(bare) if f not in checks.facts(said)]) and (
            off := [f for f in checks.facts(_unheld(bare, held())) if f not in checks.facts(said)]):
        return STEP_FACT.format(step=step, facts=", ".join(off))
    own = {w for w in re.findall(r"[a-z]{3,}", bare.lower()[len(first):]) if w not in _EMPTY_WORDS}
    seen = set(re.findall(r"[a-z]{3,}", said.lower()))
    if not own & seen:
        return STEP_FIXED.format(step=step)
    return None


def judge(name: str, args: dict[str, Any], folder: Path,
          before: Iterable[str] = (), activity: str | None = None) -> list[tuple[Place, str]]:
    """Every rule on one answer's arguments (a text shape's or the free answer's): the places that
    fail, each with its reason. `before` is what earlier answers on the same activity said
    (rule 11); `activity` is the turn's, whose code count a first line may state (738)."""
    out: list[tuple[Place, str]] = []
    first = str(args.get("answer") or "")
    details = checks.as_list(args.get("details"))
    out += [(("answer",), why) for why in (_first(name, first, details, folder, activity)
                                                   if first.strip() else [])]
    functions = words.functions(folder)
    reasons = 0
    for i, d in enumerate(details):
        text = str(d)
        if why := _line_rules(text, functions):
            out.append((("details", i), why))
        # rule 2 on the free answer's reasons: a shape's parts are its own lists, in its order
        elif name == FREE and not text.lstrip().startswith("|") \
                and (reasons := reasons + 1) > REASONS:
            out.append((("details", i), TOO_MANY.format(n=REASONS)))
    claimed = _bare("\n".join([first, *map(str, details)]))
    if _PROPOSAL.search(claimed) and _PROPOSED.search(claimed) and not _DECIDES.search(claimed):
        out.append((("answer",), NO_DECIDER))
    out += _same(first, before)
    said = render(name, {k: v for k, v in args.items() if k != "next_steps"})
    leaves = bool(_LEFT_WITH_OWNERS.search(said))
    counted = _counts(said)
    held = functools.cache(lambda: _room_dates(folder))  # read once, and only for a step's date
    for i, step in enumerate(checks.as_list(args.get("next_steps"))):
        why = _step_rules(str(step), said, leaves, held) or next(
            (SAME_COUNT.format(said=f"{n} {noun}", where="the answer",
                               other=f"{counted[noun]} {noun}")
             for noun, n in _counts(str(step)).items() if counted.get(noun) not in (None, n)),
            None)
        if why:
            out.append((("next_steps", i), why))
    return out


def _same(first: str, before: Iterable[str]) -> list[tuple[Place, str]]:
    """Rule 11 across answers: a first line counting a thing as an earlier answer's first line on
    the same activity and of the same kind did not (`before`)."""
    seen: dict[str, int] = {}
    for text in before:
        for noun, n in _counts(text).items():
            seen.setdefault(noun, n)
    at: Place = ("answer",)
    return [(at, SAME_COUNT.format(said=f"{n} {noun}", where="an earlier answer",
                                   other=f"{seen[noun]} {noun}"))
            for noun, n in _counts(first).items() if seen.get(noun, n) != n][:1]


def apply(checked: checks.CheckedCall, failed: list[tuple[Place, str]],
          args: dict[str, Any]) -> None:
    """The rules' failures, places in the call's own arguments (`args`, as the stack's are), into
    the checked call: each failed part goes from the checked arguments with its reason as a drop,
    and its place is one a send-back may change. A part the stack changed already is a failed
    place of its own. 640: a shape-only miss (`noted`) is recorded and the part stands; hours
    where days are plainer get their days beside them; where another part failed (so it is sent
    back), the retry may change the noted part too."""
    for at, why in failed:
        key = str(at[0])
        said = checks.as_list(args.get(key))[int(at[1])] if len(at) > 1 else args.get(key)
        checked.drops.append({"text": str(said), "reason": why})
        if noted(why):
            if _IN_DAYS_SAID.fullmatch(why) and len(at) == 1:
                checked.args[key] = in_days(str(checked.args.get(key) or ""))
            continue
        checked.failed += [] if at in checked.failed else [at]
        if len(at) == 1:
            checked.args[key] = ""
        elif said in (kept := checks.as_list(checked.args.get(key))):
            kept.remove(said)
            checked.args[key] = kept
    if checked.failed:
        checked.failed += list(dict.fromkeys(at for at, why in failed if noted(why)
                                             and at not in checked.failed))


def taps(args: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """The next steps that stood, as taps: each resends its words as his line; a step that writes
    to owners is marked " (E-Mail)" (475's C2(a)), once, and the mark ends its label (651); its
    cites are taken out, as 602 takes them out of a body (641 (e)). 746: a one-word bracket closing
    a step goes from its label and line, and a step holding several is one tap each."""
    out: dict[str, tuple[str, dict[str, Any]]] = {}
    for step in checks.as_list(args.get("next_steps")):
        whole = checks._uncited(checks.each_cite(str(step))).strip()
        if _QUOTE_JOINED.search(whole):
            whole = _QUOTE_JOINED.sub("\0", whole).replace('"', "")
        for said in map(str.strip, _SEVERAL_STEPS.sub("\\1\0", whole).split("\0")):
            bare = _CLOSING.sub("", said).strip()
            mails = any(_MAILS.fullmatch(b.rstrip(")") + ")")
                        for b in _ONE_WORD.findall(said[len(bare):])) or core.asks_to_write(bare)
            if re.search(r"\w", bare):  # a step that was a cite alone is no tap; two alike are one
                stem = bare.rstrip(". ")
                if mails or stem not in out:  # the mark stands, whichever of the two carried it
                    out[stem] = (stem + core.MAIL_MARK if mails else bare,
                                 {"kind": "again", "line": bare})
    return list(out.values())


# ── rule 10, a graph only when he asks ──────────────────────────────────────────────────────────
UNASKED = "he asked for no chart, and a graph is drawn only when he asks for one"
UNASKED_BACK = ("nemo checked your {name} call: {why}. Answer with the shape that fits his "
                "question.")


#: 742: a word that changes a chart: named as a limit, it cannot tell "show me the risks for
#: production" from a follow-up, so with a chart in the room only the model's choice stops that one
_CHANGES_CHART = re.compile(
    r"\b(?:add|exclude|without|only|show|lines|last year|this year|now for|\d+)\b", re.I)


def _changes_chart(line: str, classes: Iterable[str]) -> bool:
    """742: his line holds a change word, or a class of the room's method, and names no other
    picture or thing (`core.NOT_THIS_CHART`: "show me the process map", "add a new resource")."""
    return not core.NOT_THIS_CHART.search(line) and (bool(_CHANGES_CHART.search(line)) or any(
        re.search(rf"\b{re.escape(c)}\b", line, re.I) for c in classes))


def drawn_unasked(line: str, last_template: str | None, held: bool,
                  classes: Iterable[str]) -> bool:
    """Rule 10: a chart call where his line asks for no chart, no chart was the last thing shown
    (a follow-up to one changes it) and, with a chart `held` in the room, no word of his changes
    one (742). A line adding a resource never counts: `core.ADD_ASKED` holds every line
    `core.asks_one_add` reads, and "add it to production as a resource", which that one leaves to
    the turn."""
    if core.ADD_ASKED.search(line):
        return True
    return not core.asks_for_chart(line) and last_template != CHART \
        and not (held and _changes_chart(line, classes))


# ── the drafts kind (591, 594) ──────────────────────────────────────────────────────────────────
_MARKER = re.compile(r"^([ \t]*)(\d+)([.)])[ \t]+", re.M)
_HELD_MARK = "⁣"


def unnumbered(body: str) -> str:
    """591: list numbers out of the facts' way: each "1." at a line's start becomes as many
    invisible marks as its number, which the stack reads as no figure (`numbered` puts it back)."""
    return _MARKER.sub(lambda m: f"{m[1]}{_HELD_MARK * int(m[2])} ", body)


def numbered(body: str) -> str:
    """The list numbers back where `unnumbered` took them out."""
    return re.sub(rf"^([ \t]*)({_HELD_MARK}+) ?", lambda m: f"{m[1]}{len(m[2])}. ", body,
                  flags=re.M)


def held_dates(folder: Path, lines: Iterable[str], set_dates: Iterable[str] = ()) -> set[str]:
    """591: the dates the room holds, as the facts' stack reads them: the programme plan's, those
    in his lines, and those the conversation set (an invitation's day): a letter may say them
    with no cite."""
    plan = folder / core.PROGRAMME_PLAN
    said = "\n".join([plan.read_text(encoding="utf-8") if plan.is_file() else "", *lines,
                      *set_dates])
    return {f for m in checks.DATE.finditer(said) for f in checks.facts(m[0])}


def _addressed(body: str, functions: list[str]) -> list[tuple[int, str]]:
    """594: where a body opens a part for one function ("To the Plant Manager:"), in order."""
    heads = "|".join(re.escape(f) for f in sorted(functions, key=len, reverse=True))
    return [(m.start(), next(f for f in functions if f.lower() == m[1].lower()))
            for m in re.finditer(rf"^[ \t*#]*(?:To|For|Dear)\s+(?:the\s+)?({heads})[ \t*]*[:,]?"
                                 r"[ \t*]*(?:\n|$)", body, re.M | re.I)] if heads else []


def section(body: str, function: str, functions: list[str]) -> str:
    """594: one letter to one owner: where the body holds a part for each of several functions,
    the text before the first part and this function's part alone (its heading line dropped);
    else the body whole."""
    at = _addressed(body, functions)
    if not at:
        return body
    ends = [s for s, _ in at[1:]] + [len(body)]
    own = [body[s:e] for (s, f), e in zip(at, ends, strict=True) if f == function]
    return "\n".join(filter(None, [body[:at[0][0]].strip(), *(
        re.sub(r"\A[^\n]*\n?", "", p).strip() for p in own)])).strip()


#: 594 (the drafts kind's must-name): who has no address in the files
NO_ADDRESS = "Not stated: an address for the {functions} in the files; nemo uses its demo mailbox"
_ADDRESS = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def unaddressed(folder: Path, to: list[str]) -> list[str]:
    """The recipients whose function no line of the organisation file gives an address beside."""
    lines = (folder / words.ORGANISATION).read_text(encoding="utf-8").splitlines()
    return [f for f in to if not any(f in x and _ADDRESS.search(x) for x in lines)]


def drafts_first(n: int, placed: bool = False, unchanged: bool = False) -> str:
    line = DRAFTS_UNCHANGED if unchanged else DRAFTS_PLACED if placed else DRAFTS_FIRST
    return line.format(n=n, people="person" if n == 1 else "people")


# ── example 3: a briefing to print is the briefing shape ────────────────────────────────────────
_BRIEFING = re.compile(r"\bbriefing\b", re.I)
_A_LETTER = re.compile(r"\be-?mails?\b|\bletters?\b|\bwrite to\b|\bmail\b|\bdrafts?\b", re.I)
BRIEFING_BACK = ("nemo checked your letter call: his line asks for a briefing to print, which is "
                 "the briefing shape, not a letter. Call briefing.")


def asks_briefing(line: str) -> bool:
    """His line asks for a briefing, and for no e-mail or letter."""
    return bool(_BRIEFING.search(line)) and not _A_LETTER.search(line)

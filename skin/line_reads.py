"""What the led turn and the chart tap read from his typed line and the room, by code with no model
(ticket 599, ADR-0061 decision 11). They lived in `agent_fallback`, ADR-0053's agent loop, which no
turn reached any more; the loop went and what the live path used moved here whole, each line as it
was.

- The standard: a line asking about it keeps today's chat path (`about_the_standard`, 506), so
  `PROTOTYPE_core.Session._led_takes` hands it no led turn.
- The chart a tap asks for (t499): where the chart card holds the facts but not the picture asked
  (`chart_miss`: a picture, or the chart before added to), the card stays and the template draws the
  chart before below it (`card_and_template`), in the classes he picked (`picked`).
- The name his line means (t493): the room's names (`things`), the one his line uses (`meant`), and
  the one question with two taps where it fits two (`meant_question`).
- The register: the row a line names (`resource_row`), what an outage takes down (`down`) and the
  activities it reaches (`reached`).
- The activities his line asks about (`asked`).
"""

from __future__ import annotations

import itertools
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import shown

from nemo import walk

import PROTOTYPE_core as core
import PROTOTYPE_draft as drafting

# ── the standard (ticket 506) ─────────────────────────────────────────────────────────────────────
#: the method's terms a question about the standard asks the meaning of
_TERMS = "|".join(["BIA", "BCM", "BCMS", "MTPD", "MBCO", "RTO", "RPO", "business impact analysis",
                   "business continuity(?: management)?"])
#: ADR-0053 decision 1 (ticket 506): a question about the standard, which today's chat path
#: answers from the guidance (`ask_guidance`) and the agent cannot: it names a standard, or asks
#: what a term of the method means, English and German
ABOUT_THE_STANDARD = re.compile(
    r"\b(?:ISO\s*2231\d|BSI[\s-]*(?:standard\s*)?200-4|BCI|GPG|good practice guidelines?)\b"
    r"|\b(?:by|per|under|in|according to|does|do|what does) the standard\b"
    r"|\bthe standard (?:say|require|ask|expect)s?\b"
    rf"|\b(?:what(?:'s| is| are| does| do)|was (?:ist|sind|bedeutet|bedeuten|heißt)|define|explain"
    rf"|meaning of|erkläre?)\s+(?:an?\s+|the\s+|eine?\s+|die\s+|der\s+|das\s+)?(?:{_TERMS})"
    rf"(?:\s+(?:mean|stand for|bedeuten|heißen))?\s*(?:[?.!,]|$)"
    rf"|\bdifference between (?:an?\s+|the\s+)?(?:{_TERMS}) and (?:an?\s+|the\s+)?(?:{_TERMS})\b",
    re.I)


def about_the_standard(line: str) -> bool:
    """ADR-0053 decision 1 (ticket 506): his line asks about the standard, which today's chat path
    answers from the guidance (`ask_guidance`); the led turn never takes it."""
    return bool(ABOUT_THE_STANDARD.search(line))


# ── the chart a tap asks for (t499, ADR-0053 decision 1) ──────────────────────────────────────────
#: ADR-0053 answer 4: a picture asked for in draw-like words, English and German
DRAW_WORDS = re.compile(r"\b(?:draw|sketch|diagram|picture of|map (?:it )?out|chart me"
                        r"|zeichne\w*|skizzier\w*|diagramm\w*|bild von)\b", re.I)
#: what a card drew as a picture: a chart, or a link to the graph page
PICTURED = re.compile(re.escape(f"{core.LIVE_GRAPH}") + r"|" + re.escape(core.CHART_HEADING))
#: he adds one more to the chart before (v4 k1-3: "Add order picking to the same chart.")
ADD_TO_CHART = re.compile(r"\badd\b[^.?!]*\bto (?:the same|this|that|the) (?:chart|graph)\b", re.I)
#: the activity a chart card is of, by its title (`core.CHART_TITLE`)
_CHARTED = re.compile(r"\*\*(.+?)" + re.escape(core.CHART_HEADING))
#: the chart rules by name, as the turn file keeps the one that fired
PICTURE, WRONG_SUBJECT = "picture", "wrong subject"
#: the path's name in the turn file (spec test seam 1)
CARD_TEMPLATE = "card + template"
#: what a sentence says a figure is of besides its class: this year's or last year's
_YEAR_SAID = re.compile(r"\b(this|last)\s+year", re.I)
#: the template's name in the turn file (ADR-0053 decision 3)
IMPACT_OVER_TIME = "impact_over_time"
#: code's line under the card, naming the chart the template adds (r2: 14_nemo_design's words)
TEMPLATE_BESIDE = "Below it, the chart from before: {names}."


def chart_miss(line: str, card: str, earlier: str = "") -> str | None:
    """The rule by which a chart card misses his line, None where it answers it: a picture asked
    for in draw-like words and none drawn (`PICTURE`); a chart he adds to the chart before
    (`earlier`) drawn without that one (`WRONG_SUBJECT`). A chart card opens on its title, so the
    loop's other rules (no card, can't, a list for a judgement) never fired on one."""
    if DRAW_WORDS.search(line) and not PICTURED.search(card):
        return PICTURE
    if ADD_TO_CHART.search(line) and set(_CHARTED.findall(earlier)) - set(_CHARTED.findall(card)):
        return WRONG_SUBJECT
    return None


def classes(folder: Path) -> dict[str, str]:
    """The method's impact classes, each by its name and its id ("health of persons", "health"),
    lower case, to the class's id."""
    method = json.loads((folder / walk.METHOD).read_text())
    return {str(w).lower(): str(s["id"]) for s in method.get("scenarios") or []
            if isinstance(s, dict) and s.get("id") for w in (s.get("name"), s["id"]) if w}


def _about(text: str, named: dict[str, str]) -> tuple[set[str], set[str]]:
    """The impact classes (their ids) and the years ("this", "last") `text` speaks of."""
    return ({c for w, c in named.items() if re.search(rf"\b{re.escape(w)}\b", text, re.I)},
            {y.lower() for y in _YEAR_SAID.findall(text)})


def picked(folder: Path, lines: list[str]) -> list[str]:
    """r2 (k1-2's "Now only legal and financial."): the impact classes (their ids, in the method's
    order) the latest of `lines` naming any names, [] where none does."""
    named, order = classes(folder), list(dict.fromkeys(classes(folder).values()))
    for line in reversed(lines):
        if said := _about(line, named)[0]:
            return [c for c in order if c in said]
    return []


def impact_over_time(folder: Path, activities: list[str], method: dict[str, Any],
                     only: list[str] | None = None) -> list[tuple[str, str]]:
    """ADR-0053 decision 3's first template: nemo's own impact chart (`core.activity_charts`), its
    look unchanged, its data swapped: one chart per activity, stacked, each (wide, phone).
    r2: `only`, the classes he picked, every class where None."""
    return [core.activity_charts(folder, a, method, only) for a in activities]


def card_and_template(folder: Path, card: str, activities: list[str], why: str,
                      method: dict[str, Any], only: list[str] | None = None
                      ) -> tuple[str, list[str], list[str], dict[str, Any]]:
    """The 'card + template' path: the card (the last of `activities`' chart) stays, the template
    draws the chart before below it. (The card with code's line naming it, the wide charts, the
    phone charts, the turn file's record of the path.) r2: `only`, the classes he picked (`picked`):
    both charts draw those alone, the card counts them, and the turn file names them. r3: the
    asked activity's chart (the card's) first, the charts before below it, as code's line says."""
    drawn = impact_over_time(folder, activities[-1:] + activities[:-1], method, only or None)
    said = TEMPLATE_BESIDE.format(names=", ".join(core.map_name(folder, a)
                                                  for a in activities[:-1]))
    if only:
        every, drawn_on = (core.under_with_year(core.chart_under(core.CHART_UNDER, n), folder,
                                                activities[-1])
                           for n in (len(core.method_lenses(method)), len(only)))
        card = card.replace(every, drawn_on)
        if core.FINANCIAL not in only and (euros := core.euro_said(folder, activities[-1])):
            card = card.replace(f"\n\n{euros}", "")  # 741: the line belongs to what is drawn
    return (f"{card}\n\n{said}", [w for w, _ in drawn], [p for _, p in drawn],
            {"route": CARD_TEMPLATE, "miss": why, "template": IMPACT_OVER_TIME,
             "activities": activities, **({"classes": only} if only else {})})


# ── the name his line means (t493, slice 5) ───────────────────────────────────────────────────────
#: the name his line uses: the words after "the", "our", "a" or "an", up to a word no name holds
_DETERMINER = re.compile(r"\b(the|our|an?)\s+", re.I)
_WORD = re.compile(r"[^\W\d_]+")
#: words that never tell one thing from another on their own
_FILLER = frozenset("the our a an of and or for at in on to with by from system systems".split())
#: a system an interview names in its own lower-case words ("a backup order system")
_INTERVIEW_SYSTEM = re.compile(r"\b(?:an?|the|our)\s+((?:[a-z][a-z-]*\s+){1,3}system)\b")
#: a site as the room's files call it ("our Breitenburg plant")
_SITE_WORDS = ("plant", "site")
#: the one question, with no model call (his answer 5: at most one per answer)
MEANT_ASK = 'By "{said}", do you mean the {a} or the {b}?'


@dataclass(frozen=True)
class Thing:
    """One thing of the room by its own name: an activity, a register row or a system an interview
    names. `words`, the words that name it; `site`, a site's own name (a word that, in another
    thing's name, only says where it is)."""

    label: str
    kind: str
    where: str
    words: frozenset[str]
    site: str = ""


def _words(text: str) -> list[str]:
    """`text`'s words as names are matched: lower case, each plural's "s" off."""
    return [re.sub(r"(\w{3,})s$", r"\1", w.lower()) for w in _WORD.findall(text)]


def _unbracketed(said: Any) -> str:
    return re.sub(r"\s*\(.*", "", str(said or ""))


def _row_thing(i: str, r: dict[str, Any], text: str) -> Thing:
    """A register row by its own name; a site as the files call it ("the Breitenburg plant")."""
    name = _unbracketed(r["name"])
    if str(r.get("asset_type") or "").lower() != "site":
        return Thing(name, str(r.get("asset_type") or "resource"), i, frozenset(_words(name)))
    label = next((f"{name} {w}" for w in _SITE_WORDS if f"{name} {w}".lower() in text), name)
    return Thing(label, str(r["asset_type"]), i, frozenset(_words(label)), name)


def _named(folder: Path, register: dict[str, Any]) -> list[tuple[str, str, str]]:
    """The names the register gives as owners (people by function) and the systems the room's
    interviews name, each with its kind and where it is: (label, kind, where)."""
    owners = [(owner, "function", i) for i, r in register.items() if isinstance(r, dict)
              and (owner := _unbracketed(r.get("owner_name")))]
    return owners + [(m[1], "named", p) for p in core.room_files(folder)
                     if p.startswith("07_Interviews/")
                     for m in _INTERVIEW_SYSTEM.finditer((folder / p).read_text(errors="replace"))]


def things(folder: Path) -> list[Thing]:
    """The room's own names (code, no model): its activities, the register's rows (a name's
    bracket aside), the functions it names as owners, and the systems its interviews name that
    the register does not."""
    text, register = core.room_text(folder).lower(), drafting.read_register(folder)
    out = [Thing(core.map_name(folder, a), "activity", a, frozenset(_words(core.map_name(
        folder, a)))) for a in walk.processes(folder)]
    out += [_row_thing(i, r, text) for i, r in register.items()
            if isinstance(r, dict) and _unbracketed(r.get("name"))]
    known = {t.label.lower() for t in out}
    for label, kind, where in _named(folder, register):
        if label.lower() not in known:
            known.add(label.lower())
            out.append(Thing(label, kind, where, frozenset(_words(label))))
    return out


def _cue(t: Thing, sites: set[str]) -> frozenset[str]:
    """The words that tell `t` apart: a site's name inside another thing's name only places it,
    and a site is told apart by its name alone ("plant" is how the files call it)."""
    return frozenset(_words(t.site)) if t.site else t.words - _FILLER - sites


def _a_name(cue: list[str], run: list[re.Match[str]], room: list[Thing]) -> bool:
    """r2 (42_nemo_check's rule): his words name a thing only on more than one common word, on all
    of a thing's name words, or on a word no ordinary ask uses (a proper name): "the time" alone
    names nothing, "the Breitenburg backup" and "the corporate network" do."""
    return bool(cue) and (len(set(cue)) > 1 or any(m[0][:1].isupper() for m in run)
                          or any(t.words - _FILLER == set(cue) for t in room))


def meant(folder: Path, line: str) -> tuple[str, list[Thing]] | None:
    """t493 (spec slice 5): the first name his line uses after "the", "our" or "a" that matches a
    thing of the room, and what it matches: the thing named by exactly those words, else each thing
    holding every one, else those holding the most (two or more where it is unclear, the one its
    last word names first). None where his line names no thing that way."""
    room = things(folder)
    held = {w for t in room for w in t.words}
    sites = {w for t in room if t.site for w in _words(t.site)}
    for det in _DETERMINER.finditer(line):
        run = list(itertools.takewhile(lambda m: _words(m[0])[0] in held,
                                       _WORD.finditer(line, det.end())))
        cue = [w for m in run for w in _words(m[0]) if w not in _FILLER]
        if not _a_name(cue, run, room):
            continue
        said = line[det.start():run[-1].end()]
        if exact := [t for t in room if t.words - _FILLER == set(cue)]:
            return said, exact[:1]
        score = {t: len(_cue(t, sites) & set(cue)) for t in room}
        if every := [t for t in room if score[t] == len(set(cue))]:
            return said, every
        top = max(score.values())
        if top:
            hits = [t for t in room if score[t] == top]
            last = {t: max(cue.index(w) for w in _cue(t, sites) & set(cue)) for t in hits}
            return said, sorted(hits, key=lambda t: -last[t])
    return None


def meant_question(folder: Path, line: str) -> tuple[str, list[tuple[str, str]]] | None:
    """t493: where the name his line uses matches two things or more, the one short question and
    its two taps (each the thing's label and his line with that name in it); None otherwise."""
    found = meant(folder, line)
    if not found or len(found[1]) < 2:
        return None
    said, (a, b, *_) = found
    det = said.split()[0]
    return MEANT_ASK.format(said=said, a=a.label, b=b.label), [
        (f"The {t.label}", line.replace(said, f"{det} {t.label}")) for t in (a, b)]


# ── the register (t491, 488) ──────────────────────────────────────────────────────────────────────
#: a company form after a supplier's name ("Marshland Fuels GmbH" is said "Marshland Fuels")
COMPANY = re.compile(r"\s+(?:GmbH|AG|KG|SE|Ltd)\.?$")
#: a register row's kind for a supplier outside the company
SUPPLIER = "External supplier"


def resource_row(folder: Path, name: str) -> tuple[str, dict[str, Any]] | None:
    """The register row `name` names: the whole name, case aside, the longest first."""
    register = drafting.read_register(folder)
    rows = sorted(((i, r) for i, r in register.items() if isinstance(r, dict) and r.get("name")),
                  key=lambda ir: -len(str(ir[1]["name"])))
    return next(((i, r) for i, r in rows for said in dict.fromkeys(
        (str(r["name"]), COMPANY.sub("", str(r["name"]))))
                 if re.search(rf"(?<!\w){re.escape(said)}(?!\w)", name, re.I)
                 or said.lower() == name.strip().lower()), None)


def down(register: dict[str, Any], i: str) -> list[str]:
    """r2: every register row an outage of `i` takes down: `i` and all that stand on it, at any
    depth (a generator on the power supply, a system on the generator)."""
    out, grew = [i], True
    while grew:
        more = [j for j, r in register.items() if isinstance(r, dict) and j not in out
                and set(r.get("depends_on") or []) & set(out)]
        out, grew = out + more, bool(more)
    return out


def reached(folder: Path, ids: list[str], register: dict[str, Any]) -> list[str]:
    """The room's activities that use any of `ids`."""
    used = {c["department"] for i in ids for c in register[i].get("consumers") or []}
    return [a for a in walk.processes(folder) if a in used]


# ── the activities his line asks about (t490, t533) ───────────────────────────────────────────────
#: at most this many asked activities are briefed and read (a site or a supply many use names all)
MOST = 3


def _singular(text: str) -> str:
    """A line or a name as `asked` compares them: `core._name_words`', each plural's "s" off."""
    return re.sub(r"(\w{3,})s\b", r"\1", core._name_words(text))


def asked(folder: Path, line: str, earlier: list[str]) -> list[str]:
    """The room's activities his line asks about, at most `MOST`: those it names (t252), else
    those using a register row it names (plurals aside: "technicians" names Technician), else
    those his latest earlier line named (k1-2's "Now only legal and financial."), else those it
    names by a head word of their own (`core.named_by_head`; t566: a word that only modifies a
    name, "is it material?", names none). t533 (521): else the room's focus, nemo's own last pick
    (B2's) as the room keeps it (`shown`)."""
    if named := core.named_in(folder, line):
        return named[:MOST]
    said, room = _singular(line), walk.processes(folder)
    used = [c["department"] for r in drafting.read_register(folder).values()
            if isinstance(r, dict) and (name := _singular(str(r.get("name") or ""))).strip()
            and name in said for c in r.get("consumers") or []]
    if used := [a for a in dict.fromkeys(used) if a in room]:
        return used[:MOST]
    for before in reversed(earlier):
        if named := core.named_in(folder, before) or core.named_by_head(folder, before):
            return named[:MOST]
    if loose := core.named_by_head(folder, line):
        return loose[:MOST]
    kept = shown.last(folder, shown.FOCUS)
    return [a] if kept and (a := kept.get("activity")) in room else []

"""Ticket 518: this year's impact scores as an interview states them in words.

Order picking's and dispatch's 2 Oct 2026 re-interviews state their 2026 scores in sentences
("medium at 72 hours, high after a week"), not as `Impact <class>:` rows, so `nemo.evidence` reads
no grid from them. This reads those sentences by code, never by a model (M13), into the grid the
impact chart (`impact_chart`) draws as this year's lines; which sentences count and which never do
is 19_marschkamp's worded-scores sheet (2026-10-19).
"""
from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from typing import Any, NamedTuple

from nemo.impact import is_score
from nemo.method import SEVERITY_SCALE, horizons, lenses

#: an interview's lines, each "<speaker>: <words>"
TURN = re.compile(r"^(?P<who>[A-Z][^:*>\n]{0,60}): (?P<said>.+)$", re.M)
SENTENCE = re.compile(r"(?<=[.!?])\s+")
FACILITATOR = re.compile(r"^facilitator:\s*(.+)$", re.M)
#: a sentence that quotes last year's figures, never this year's score
LAST_YEAR_SAID = re.compile(r"\blast year\b", re.I)
#: a bare "No." to a question on a class: its lowest level, at every hour
BARE_NO = re.compile(r"^no\.?$", re.I)
#: an hour said straight after a level ("at 72 hours", "at 168", "after a week")
AT_HOUR = re.compile(r"^\s*(?:at|after|from)\s+"
                     r"(?:(?P<n>\d+)(?:\s*h(?:ours?)?\b)?|(?P<week>a week))", re.I)
#: an hour said anywhere in a sentence ("Up to 72 hours …, then low")
HOUR_SAID = re.compile(r"\b(?:(?P<n>\d+)\s*h(?:ours?)?\b|(?P<week>a week))", re.I)
WEEK_HOURS = 7 * 24
#: the interviewer's plain word for a class its name does not hold ("Harm to people?")
ASKED_AS = {"health": ("harm",)}


class Said(NamedTuple):
    """What the answers state per class: a level at an hour, or a level with no hour at all."""

    stated: dict[str, dict[str, int]]
    bare: dict[str, int]


def from_words(transcript: str, method: Mapping[str, Any],
               prior: Mapping[str, Any] | None = None) -> dict[str, dict[str, int]]:
    """This year's grid as an interview states it in words: each answer to the interviewer's
    question on a class, a level word of the method's scale ("medium") at the hour said with it
    ("at 72 hours", "after a week") or, with none, the hour the sentence named before it; a level
    said with no hour at all ("Image I'd leave at none", a bare "No.") holds at every hour. The
    interviewer's own lines (the sum-up), a sentence quoting last year and an answer to no class's
    question are never read. Each class is read over the hours last year's record rates it at
    (`prior`; every hour where it rates none): an hour before its first stated one is the scale's
    lowest level, an hour after its last stated one stays empty, never carried over
    (42_nemo_check's ruling 2026-10-19 08:05)."""
    scale = _scale(method)
    if not scale or not lenses(method):
        return {}
    said = _read(transcript, method, scale)
    hors, lowest = horizons(method), min(scale.values())
    return {lens: _row(said, lens, hors, _rated(prior, lens, hors), lowest)
            for lens in lenses(method) if lens in said.stated or lens in said.bare}


def _scale(method: Mapping[str, Any]) -> dict[str, int]:
    return {str(s["label"]).strip().lower(): s["level"] for s in method.get(SEVERITY_SCALE) or []
            if isinstance(s, dict) and s.get("label") and is_score(s.get("level"))}


def _rated(prior: Mapping[str, Any] | None, lens: str, hors: list[str]) -> list[str]:
    row = (prior or {}).get(lens) or {}
    return [h for h in hors if is_score(row.get(h))] or hors


def _row(said: Said, lens: str, hors: list[str], rated: list[str],
         lowest: int) -> dict[str, int]:
    """One class's cells: stated, else its level said with no hour, else the lowest level before
    its first stated hour; after its last, none."""
    stated = said.stated.get(lens, {})
    first = min((hors.index(h) for h in stated), default=len(hors))
    fill = said.bare.get(lens)
    return {h: stated.get(h, fill if fill is not None else lowest) for h in rated
            if h in stated or fill is not None or hors.index(h) < first}


def _read(transcript: str, method: Mapping[str, Any], scale: dict[str, int]) -> Said:
    said = Said({}, {})
    for about, sentence in _answers(transcript, method):
        for score, at in _levels(sentence, method, scale):
            for lens in about:
                if at is None:
                    said.bare.setdefault(lens, score)
                else:
                    said.stated.setdefault(lens, {}).setdefault(at, score)
    return said


def _levels(sentence: str, method: Mapping[str, Any],
            scale: dict[str, int]) -> Iterator[tuple[int, str | None]]:
    """Each level a sentence says, with the hour it says it at (None for none): a bare "No." the
    scale's lowest."""
    if BARE_NO.match(sentence.strip()):
        yield min(scale.values()), None
        return
    level = re.compile(r"\b(" + "|".join(sorted(map(re.escape, scale), key=len, reverse=True))
                       + r")\b", re.I)
    for found in level.finditer(sentence):
        yield scale[found[1].lower()], _hour(AT_HOUR.match(sentence[found.end():]), method) or \
            _hour([None, *HOUR_SAID.finditer(sentence[:found.start()])][-1], method)


def _answers(transcript: str, method: Mapping[str, Any]) -> Iterator[tuple[list[str], str]]:
    """Each sentence answering the interviewer's question on a class, with the classes it is
    about: those it names, else the one the question names. Never the interviewer's own lines,
    nor a sentence quoting last year."""
    who = found[1].strip() if (found := FACILITATOR.search(transcript)) else ""
    asked: list[str] = []
    for turn in TURN.finditer(transcript):
        if turn["who"].strip() == who:
            asked = _classes(turn["said"], method)
            continue
        for sentence in SENTENCE.split(turn["said"].strip()):
            about = _classes(sentence, method) or (asked if len(asked) == 1 else [])
            if asked and about and not LAST_YEAR_SAID.search(sentence):
                yield about, sentence


def _classes(text: str, method: Mapping[str, Any]) -> list[str]:
    """The classes a line names: a word starting with its id, a word of five letters or more of
    its name ("Financially"), or its `ASKED_AS` word."""
    names = {s["id"]: {w for w in re.findall(r"[a-z]+", f"{s['id']} {s.get('name') or ''}".lower())
                       if len(w) >= 5 or w == s["id"]} | set(ASKED_AS.get(s["id"], ()))
             for s in method.get("scenarios") or [] if isinstance(s, dict) and s.get("id")}
    words = re.findall(r"[a-z]+", text.lower())
    return [lens for lens in lenses(method)
            if any(w.startswith(n) for w in words for n in names.get(lens, ()))]


def _hour(found: re.Match[str] | None, method: Mapping[str, Any]) -> str | None:
    """The method's hour a phrase says, None where it says none of them."""
    if found is None:
        return None
    n = WEEK_HOURS if found["week"] else int(found["n"])
    return next((h for h in horizons(method) if re.fullmatch(rf"{n}\s*h", str(h).strip())), None)

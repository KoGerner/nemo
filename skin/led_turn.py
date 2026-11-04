"""Ticket 546 (ADR-0056, rework S5a, first step 536a) with ticket 536's full build: the turn the
model leads.

One typed line in, one turn out, over the GLM lane (`lanes.chat`, tool choice auto, nothing else;
no model is called in any gate: a scripted fake replays fixed tool calls below `lanes.chat`).

- **The brief** is built by code and handed with his line: today (the story's), the method's rules,
  the file map (one line per room file, from the file), what was last shown with the lines it
  cited, and the focus activity's raw rows (numbered by file and line). Data, never prose.
- **Facts are tools** (605, ADR-0061 d2): 601's fact functions (`core.FACTS`) are offered as
  `FACT_TOOLS`, each returning its values as JSON (`fact`; a sentence is refused), and a value one
  gave stands in the answer with no cite; the brief hands no list. 645: the values come in the
  room's words (a person by function, a date as the room writes it, `room_words`), a count one
  makes (`FACT_COUNTS`) is the count a who or how-many line may say, and a call that needs an
  activity, naming none with none in focus, ends the turn on code's which-activity ask
  (`ask_activity`): the answer is dropped, never given over the whole process map. The lists his
  line asks for (`code_lists`) are the check's alone: an answer may not shorten one. A question
  about people is no invitation (`INVITE_UNASKED`, B3).
- **A day his line names** (536, 544's resolver as data): the day and its interviews go into the
  brief, a day holding interviews hands its interviews' rows and no other day's, a sentence drawn
  on another interview is dropped (`checks.OTHER_DAY`), and 544's own pointer line
  (`core.others_said`) closes the answer.
- **Reads** are capped and line-numbered (`read_file`, 523 absorbed): at most `READ_CAP` lines a
  call, a closing line saying where it was cut and how to read on.
- **Templates are tools** (`TEMPLATES`): a plain answer, a judgement (a verdict, reasons each
  with its cite, what is not stated), the graph answer (at most three plain lines, then code's
  link, 488; 632: the items the drawn graph shows are covered, and a line naming one is never
  cut), and (538) the impact-over-time chart (`CHART_TOOL`, offered beside them in
  `OFFERED`). The model calls one; prose is sent back once.
- **A follow-up changes the last chart** (538): the chart call's arguments are the activities,
  classes and years; one it leaves out keeps the last chart's (this conversation's, else the
  room's, 533), so "only legal and financial" is a call with only the classes and code never reads
  his words for them. Code checks each against the room's data (one send-back), draws nemo's own
  chart (stacked, one per activity), counts its classes and marks what changed from the chart
  before. A call naming no activity takes the turn's focus, else is the which-activity ask
  (603); and a chart is drawn only where his line asks for one or follows one, or a chart is in
  the room and his line holds a word that changes it (rule 10, 742).
- **Letters** (539, S7): the letter frame is a template (`LETTER`): the recipients are functions
  the organisation file names, never an address (one the model typed is sent back once, then the
  plain line), the subject and the body the model's, the greeting and closing code's; 756: one
  person to a call, several calls in one reply, one draft each. A follow-up re-calls it, an
  argument left out keeping the last draft's (696: that person's, none lent to someone with no
  draft): a new version of the same draft while it is not placed, a new draft once it is. Nothing
  is written before his tap (`place`), which puts each draft in Drafts at the mailbox code maps
  the function to.
- **The invitation** (540, S8) is a template too (`INVITATION`): "do it on November 20" is a call
  with the date. Code checks it (a real day in ISO, not before the story's today, the hour only one
  his line names, else the last one's) and writes the weekday itself. His tap (`move`) moves the
  one calendar event, its id kept, and puts a new invitation in Drafts; the earlier one stays.
- **Every reply goes through 535's stack** (`checks.check_call`), and a send-back FREEZES the rest:
  the retry prompt carries the items that passed, and `checks.retry` keeps them (658: a retry's
  change to a passed item is refused, that item stays the first try's; its fix to a failed one
  stands). A dropped sentence costs only itself: a shape whose first line went keeps its parts.
- **Ask, don't guess** (493): a name that fits two things gets one question and two taps, with no
  model call, and his pick is his line as typed right.
- **One retry, then what passed** (606, ADR-0061 decision 6): a failed call (broken JSON, a tool
  not there, a fact or file the room cannot give, a call the checks send back) goes back to the
  model once with its error; a second failure in the turn ends it with no third try, and shows the
  first try's passing parts with what is missing named (a retry stopping on length too, 568).
- A turn where nothing passed gives the plain line (`PLAIN_LINE`), path `plain line`, with
  code's taps (the "Ask again" tap, which resends his line, and a next step or two); one that
  stands is path `model-led`. `Session._led_model_turn` writes either through t532's
  `led_fields`; the asked turn is code's own and carries no path.
- **The activity is his, never code's pick** (566): the focus is the one his line names, else the
  one the interviews of the day it names are about, else the core process it names by a head word
  (758: `_core_head`), else the conversation's, else the one his earlier lines name. The
  conversation's is the activity of the answer that stood (584, 550's
  rule on this path): the turn's own, else the one its first line names (722), else the one
  activity the answer names; the room keeps it
  (533's kept focus, through `Session`), so a reopened room still means it. An answer naming
  several with no such first line sets none, and the next line goes to the model as a first line
  does (584 r2). Where none
  names one, no activity is handed to the model (the plan's next BIA no longer stands in), and a
  follow-up in a conversation under way is code's one-sentence ask (`ASK_ACTIVITY`), made with no
  model call at all, and once in a conversation (614): a line after it that names none goes to the
  model as a first line does.
- **A line he types in a walk** (608, ADR-0061, map N6) comes here too, handed the walk's tools
  (`Walk`, from `Session`) beside the reads and the facts. Each call runs through `Session.dispatch`
  as a model turn, so the record stays code's (ADR-0006): a change is proposed and only his tap
  records it, and a call that would write is refused where it writes. A walk call's values stand
  uncited, as a fact's do; its refusal (or nemo's interview question) ends the turn (`Turn.ended`)
  and `Session` shows it as the brake shows it, the model's words never.
- **The yes or no is code's** (604, ADR-0061 decision 4): a single-point ask on the focus
  activity, or a dependency ask on one register resource, gets code's verdict in the brief
  (`verdict`, from `core.spof`); an answer opening with the other word is sent back, then dropped
  (`VERDICT_OFF`).

- **The turn keeps its time** (537, S5b): a question's turn ends at 45 s, an e-mail's, an
  invitation's or a chart edit's at 45 s too (618, his numbers; `Clock`; the kind is code's read of
  his line and of what was last shown, `_edits`). After 10 s nemo's reply bubble says `CHECKING`
  (`waiting`). At the limit no model call starts, and a reply still out is never read; an answer
  already in hand (a first try sent back) is checked as a last try and shown where it stands (618,
  his "Yes, show it"). Else he reads the time-limit line of the turn's kind with code's taps, and
  nothing is changed. A copy's model calls go through one queue (`QUEUE`), so a burst waits in line
  instead of failing, and the wait is on the turn's clock.

Not here (the slices after 537): the move floor, the model's own next steps, S9. GLM's
reasoning (`reasoning_content`) is neither read nor passed back: a turn keeps message content
only, as today's lane does. `WIRED` is True as 536 lands: with the switch ON
(`agent_fallback.switched_on`, a missing switch file being the brake set) a typed line in free chat
comes here. ADR-0053's agent loop, no longer reached from a turn, was taken out by 599; what this
turn borrowed from it lives in `line_reads`.
"""

from __future__ import annotations

import calendar
import contextvars
import dataclasses
import json
import re
import threading
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, NamedTuple, cast
from urllib.parse import quote

import agent_fallback
import answer_shapes as shapes
import checks
import drafts
import line_reads
import merge_table
import shown as kept
import workspace

from nemo import interview, turn_file, walk

import PROTOTYPE_core as core
import PROTOTYPE_draft as drafting
import PROTOTYPE_lanes as lanes
import PROTOTYPE_words as words

#: the module is reached from `Session` when this is True AND the brake is off the path (the
#: switch is ON); 536's full build sets it, and ADR-0053's agent loop no longer takes a turn
WIRED = True
#: the lane's key: GLM, pinned (no model switch reaches this path; no GPT through litellm)
LANE = "glm"
#: lines one read hands back at most (the spec's capped read)
READ_CAP = 120
#: model calls a turn makes at most; the last offers the templates only
MAX_STEPS = 10
MODEL_LED, PLAIN = "model-led", "plain line"
#: 493: the turn code answers with a question, no model call and no path of its own
ASKED = "asked"
#: today's plain line, where nothing usable came back
PLAIN_LINE = agent_fallback.NO_ANSWER
#: 536: the plain line's first tap, which resends his line as typed (537 draws it at the limit too)
ASK_AGAIN = "Ask again"
#: 537: the wait line, after `Clock.checking_s`, and the time-limit lines (15_nemo_design, 19 Oct)
CHECKING = "Checking your files…"
LATE_EDIT = ("nemo could not finish this in time, and nothing was changed. Ask again, or tap one "
             "of these:")
LATE_QUESTION = "nemo could not answer this in time. Ask again, or tap one of these:"
LATE_REASON = "past the turn's {limit:g} s"
#: 537: model calls one copy has in flight at most; a burst waits in line for a free one
IN_FLIGHT = 8
QUEUE = ThreadPoolExecutor(IN_FLIGHT, thread_name_prefix="nemo-model")
#: 536 (488): the graph answer's own link, as code draws it, over the model's three lines (757)
GRAPH_LINK = agent_fallback.GRAPH_LINK
#: 647: the mark the chat page puts on its graph link (t643), which the graph page reads
FROM_CHAT = "#from-chat"
#: t566: what code asks where a turn's activity resolves to none in a conversation under way;
#: 575: it names the room's core processes (`ask_activity`) and says he may name another
ASK_ACTIVITY = "Which activity is this about: {activities}, or another you name?"
#: 538: the chart template, under the checker's name (`prompt_check.CHART`), and its arguments
CHART = line_reads.IMPACT_OVER_TIME
CHART_ARGS = ("activities", "classes", "years")
#: 538: code's lines under a changed chart's titles, and its ask where no chart came before
CHART_CHANGED = "Changed from the chart before: the {what} shown."
CHART_SAME = "The same chart as before, drawn again."
#: 588 (F2): the line under a title where one year is drawn alone, in place of `core.CHART_UNDER`
CHART_THIS_ALONE = "The {count} impact classes over time, this year's interview alone"
CHART_LAST_ALONE = "The {count} impact classes over time, last year's record alone"
#: 538: why a chart call is sent back (once), and what the send-back says
CHART_OFF = "{what} {value!r} is not one the room holds"
CHART_EMPTY = "{activity} has no scores to draw with these choices"
CHART_BACK = ("nemo checked your {name} call: {why}. Call it again with activities, classes and "
              "years the brief names; an argument left out keeps the last chart's.")

#: 539 (S7) and 540 (S8): the letter frame and the invitation, under the checker's names
#: (`prompt_check.LETTER`, `INVITATION`), and their arguments
LETTER, INVITATION = "letter", "invitation"
LETTER_ARGS, INVITE_ARGS = ("to", "subject", "body"), ("activity", "date", "time")
#: 539: an address, which only code writes (`drafts.function_address`)
ADDRESS = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
#: 539: why a letter call is sent back (once)
LETTER_ADDRESS = "an address is in the call: name each recipient by function, and nemo adds it"
LETTER_NOT_A_FUNCTION = "{value!r} is not a function the organisation file names"
LETTER_EMPTY = "it has no {what}"
#: 588 (L2): a recipient who holds nothing the letter cites
LETTER_NOT_HOLDER = ("{value!r} holds nothing the letter cites: the lines it cites are the "
                     "{holders}'s")
#: 588 (L3): a first name two people of the organisation file share
LETTER_FIRST_NAME = "{value!r} is the first name of {n} people: name the function"
#: 588 (L3): the model's own greeting and sign-off in a body, which code's frame says once
GREETING = re.compile(r"\A\s*(?:Dear|Hello|Hi)\b[^\n]*\n+", re.I)
FAREWELL = re.compile(r"\n+[ \t]*(?:(?:best|kind|warm(?:est)?)\s+(?:regards|wishes)|regards"
                      r"|sincerely|yours\s+\w+|cheers|best)[ \t]*,?[ \t]*(?:\n[^\n]*){0,2}\s*\Z",
                      re.I)
#: 696: said in place of `KEEPS_LAST` to someone with no draft: no other owner's words are kept
KEEPS_LAST = "an argument left out keeps the last draft's."
LETTER_BACK = ("nemo checked your {name} call: {why}. Call it again with each recipient's function "
               f"as the organisation file names it; {KEEPS_LAST}")
NO_DRAFT_YET = ("that person has no draft yet and another person's letter lends them nothing, so "
                "give their own subject and body.")
#: 589: a letter that loses a fact is sent back once, never drawn with what is left
LETTER_FACT_BACK = ("nemo checked your {name} call: {why}. Call it again with each fact as the "
                    f"line it cites states it, or without it; {KEEPS_LAST}")
#: 756: a letter goes to one person; no code splits a body or rewords one
LETTER_SEVERAL = ("a letter goes to one person, so make one call for each person in one reply, "
                  "each body that person's own")
LETTER_SAME_BODY = ("the same body as the letter to the {other}: each letter holds that person's "
                    "own gaps and no one else's")
LETTER_LEFT_BACK = ("nemo checked your {name} calls: those to the {stood} stand, so do not call "
                    "them again. {note} Why: {why}. Call it again for what is lost alone, one "
                    "person to a call, with to, subject and body, each fact as the line it cites "
                    "states it, or without it.")
LETTER_SEVERAL_BACK = "nemo checked your {name} call: {why}. Each call gives to, subject and body."
#: 539: the tap that places the letter's drafts (the A8 drafts' own words), and what he reads
PUT_LETTER = "put_letter"
LETTER_LANDED = "In the Drafts of {box}, unsent:"
LETTER_UNREACHABLE = "The mailbox is not reachable, so this draft is not in its Drafts."
LETTER_ALREADY = "This draft is in the mailbox's Drafts already: nothing is added."
#: 651: under the drafts, where a letter beside them did not stand
LETTER_LEFT = "No new draft for the {who}: nemo could not check {those}."
LETTER_LEFT_ONE = "One letter is not here: nemo could not check it."
LETTER_LEFT_SOME = "{n} letters are not here: nemo could not check them."
LETTER_LEFT_MORE = "No new draft for the {who}, and {more} not here: nemo could not check them."
#: 540: why an invitation call is sent back (once)
INVITE_OFF = "the activity {value!r} is not one the room holds"
INVITE_NO_SLOT = "{activity} has no interview planned to invite to"
INVITE_NOT_A_DAY = "{value!r} is not a real day as YYYY-MM-DD"
INVITE_PAST = "{value} is before today, {today}"
INVITE_HOUR = ("the hour {value!r} is his to name, and his line does not; leave time out to keep "
               "{was}")
#: 631: a day that is not code's for the weekday his line names (`weekday_off`)
INVITE_WEEKDAY = "his line names {said}, so the date is {dates}, not {value}"
#: 631: a date his line names (a day with its month, an ISO date, a weekday with its day of the
#: month): its weekday is no fact to work out. A month by its name or three letters ("May" by its
#: capital), so "3 junior staff" or "at 10 may suit" names none
_MONTH = (r"(?:january|february|march|april|(?-i:May)|june|july|august|september|october|"
          r"november|december|jan|feb|mar|apr|jun|jul|aug|sept?|oct|nov|dec)\b\.?")
NAMED_DATE = re.compile(rf"\b\d{{4}}-\d\d-\d\d\b|\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTH}"
                        rf"|\b{_MONTH}\s+\d{{1,2}}\b|day,?\s+(?:the\s+\d{{1,2}}(?:st|nd|rd|th)?|"
                        r"\d{1,2}(?:st|nd|rd|th))\b|\bon\s+the\s+\d{1,2}(?:st|nd|rd|th)\b", re.I)
#: 631: a weekday code does not read as the next one ("Thursday week", "in two weeks"), left to him
OTHER_WEEK = re.compile(r"\bweeks?\b|\bafter\s+next\b", re.I)
INVITE_BACK = ("nemo checked your {name} call: {why}. Call it again; an argument left out keeps "
               "the last invitation's.")
#: 540: code's card over an invitation, the tap that moves it, and what he reads on the press
#: 605 (B3): a line asking who is a question about people, answered from the facts (once: a
#: second invitation call stands, his line may ask for both)
INVITE_UNASKED = ("he asks who, a question about people, not for an invitation: answer it from the "
                  "fact_ tools (fact_last_participants, fact_invitees)")
INVITE_CARD = "The interview on {activity}: {when}."
#: 588 (I1): a move before his tap, which alone moves it (U5): where it would go, never "moved"
INVITE_MOVE = "The interview on {activity}.\n\nNow planned for {when}. Tap to move it from {was}."
MOVE_INVITE = "move_invite"
MOVE_TAP = "Move the invitation" + core.MAIL_MARK
MOVED = "The interview is in nemo's calendar: {when}."
NOT_MOVED = "The calendar is not reachable, so the interview is not moved in nemo's calendar."
NEW_INVITE = "A new invitation is in the Drafts of {box}, unsent."
NO_NEW_INVITE = "The mailbox is not reachable, so no new invitation is in its Drafts."
OLD_INVITE_STAYS = "The earlier invitation stays in Drafts: delete it there if you like."

Lane = Callable[[list[dict[str, Any]], list[dict[str, Any]] | None], dict[str, Any]]

NOT_A_FILE = "{path} is not one of the room's files. The file map lists them."
BAD_JSON = "Those arguments are not valid JSON; call the tool again."
NO_TOOL = "There is no tool {name}. The tools are: {names}."
#: 646: a template call with a required part missing or blank (`{}` the plainest) is a failed call
EMPTY_CALL = "the call carried no answer"
EMPTY_BACK = EMPTY_CALL + ": call {name} again with {need} filled in."
#: 602 (F5): a second template call in one reply: the first is the answer, never `NO_TOOL`
ALREADY = "Already answered by your first {name} call in this reply; nemo checks that one."
#: 604: code's yes or no for his line, in the brief, and an opening against it
VERDICT_SAID = ("Code's yes or no for {about}: {verdict} ({rows}). The answer's first word is "
                "{verdict}.")
NONE_FLAGGED = "the register flags no row"
NONE_DEPENDS = "nothing in the register depends on it"
VERDICT_OFF = "it opens with '{said}', but code's answer for {about} is {verdict} ({rows})"
#: 604: a line asking for a yes or a no ("Does …?", "Is …?", "Has …?"), and what it asks of one
#: register resource: whether anything depends on it (the resource after the verb)
YES_NO_ASK = re.compile(r"^\W*(?:and\s+|so\s+)?(?:does|do|did|is|are|has|have|can|will|would)\b",
                        re.I)
DEPENDS_ON = r"\b(?:depends?|depending|rel(?:y|ies)|relying) on\b[^.?!]*?"
#: an opening saying yes, and one saying no ("Nothing depends on it" is a no)
OPENS = {True: re.compile(r"\W*yes\b", re.I), False: re.compile(r"\W*(?:no|nothing|none)\b", re.I)}
#: 679: what gives a briefing's title (the word opening it, or the activity it names) and its why
#: now, in any form: a re-interview is part of a title, "before you go in" is no reason
BRIEFING_TITLE = re.compile(r"\W*(?:(?:the|your)\s+)?briefing\b", re.I)
BRIEFING_WHY_NOW = re.compile(
    r"\b(?:why now|overdue|because|due\b(?! to\b)|(?:since|before|ahead of)\s+"
    r"(?:(?:the|its|their)\s+)?(?:\d|(?:Mon|Tues?|Wed(?:nes)?|Thu(?:rs)?|Fri|Sat(?:ur)?|Sun)(?:day)?\b"
    r"|(?:re-?)?interview))", re.I)
#: 679: the one first line that goes: it gives neither
BRIEFING_NEITHER = "its first line gives neither the title nor why now"
#: 700: what never opens an answer: a line not starting on a word or an opening quote (a bullet,
#: an arrow, a table row, a heading, any mark), a checkbox, a numbered point
NOT_OPENING = re.compile(r"\s*(?:[*_]*[^\w\s*_\"'\u2018\u201c\u201e(\[]|\*\s|\[[ xX]\]"
                         r"|[*_]*\(?(?:\d+|[a-zA-Z])[.)][*_]*\s)")
#: 700: a label of up to five words, and the words after it that let it open ("Technicians: six."
#: opens nothing); a colon later than that is prose
LABELLED = re.compile(r"\s*[^\s:]+(?:\s+[^\s:]+){0,4}\s*:[*_]*(?:\s|$)")
LABEL_OPENS_AT = 6
#: 700: a point with nothing but a heading's job: it ends on a colon, or is a heading or all bold
#: with no stop
LONE_LABEL = re.compile(r"#.*|.*:[\s*_]*|(?:[*+-]\s+)?\*\*[^*]*[^*.!?]\*\*")
MISSING = "Not in this answer: {items}, from {what}."
#: 757: what stands beside a briefing's PDF link, in place of its text; "" for nothing (his to pick)
BESIDE_PDF = "Ready to print."
#: 602 (ADR-0061 d8): a cite as he sees it, a numbered link to the room's own file at its line
CITE_LINK = "[[{n}]]({link})"
#: t638 Amend 4: the space before a cite link, which never breaks a line
NBSP = "\u00a0"
_A_CITE = checks.CITE.pattern.replace("(?P<path>", "(?:").replace("(?P<at>", "(?:")
_BETWEEN_CITES = r"[ \t]*[,;/&]?[ \t]*(?:(?:and|or)\b[ \t]*)?"
#: 721: the cites at one place in a point, what the model put between them, and a bracket round
#: them (its "see" too), which goes with them where nothing is shown in it
_CITE_RUN = re.compile(rf"([ \t]*)(\([ \t]*(?:(?i:see|cf\.?|source:?)[ \t]+)?)?"
                       rf"({_A_CITE}(?:{_BETWEEN_CITES}{_A_CITE})*)(\))?")
#: 721: a comma, semicolon or colon a cut left with only the stop or the line's end to come; never
#: inside a drawn link, which holds no space and ends in its bracket
_LEFT_BEHIND = re.compile(r"[ \t]*(?:[,;:]+[ \t]*(?=[.!?]+(?:[ \t]|$))|[,;]+[ \t]*$)")
#: 602: a made-up label in brackets ("[due list]"): no line, so it cites nothing; never a link's
#: text, nor a number
LABEL = re.compile(r"[ \t]*\[(?=[^\]\d]*[A-Za-z])[^\[\]\d:\n]*\](?!\()")


# ── what code hands the model ───────────────────────────────────────────────────────────────────
def _lines(folder: Path, path: str) -> list[str]:
    return (folder / path).read_text(encoding="utf-8", errors="replace").splitlines()


def _json_what(lines: list[str]) -> str:
    try:
        data = json.loads("\n".join(lines))
    except ValueError:
        return "JSON"
    held = [k for k, v in data.items() if isinstance(v, dict)] if isinstance(data, dict) else []
    return f"JSON, {len(held)} entries" + (f" ({', '.join(held[:3])}, ...)" if held else "")


def _md_what(lines: list[str]) -> str:
    front = dict(re.findall(r"^(department|date|type): (.+)$", "\n".join(lines)[:800], re.M))
    title = next((t.lstrip("# ").strip() for t in lines if t.startswith("#")), "")
    return "; ".join(filter(None, [title, *(f"{k} {v}" for k, v in front.items())]))


def file_map(folder: Path) -> str:
    """One line per room file, built by code from the file: its title, front matter, size (so a
    swapped file changes its line)."""
    out = []
    for path in core.room_files(folder):
        lines = _lines(folder, path)
        what = _json_what(lines) if path.endswith(".json") else _md_what(lines)
        out.append(f"{path}: {what} ({len(lines)} lines)")
    return "\n".join(out)


def method_rules(folder: Path) -> str:
    """The method's rules as data, from `method.json`: the classes, the scale, the horizons, the
    threshold and the MTPD and RTO rules in the method's own words."""
    m = {**walk._read_json(folder / walk.METHOD)}  # the file whole: its rules in its own words
    classes = "; ".join(f"{s.get('name') or s['id']} ({s['id']})" for s in m.get("scenarios") or [])
    scale = ", ".join(f"{s['level']} {s['label']}" for s in m.get("severity_scale") or [])
    return "\n".join([
        "The method's rules:", f"- Impact classes: {classes}.", f"- Scale: {scale}.",
        f"- Time horizons: {', '.join(m.get('time_horizons') or [])}; beyond them: "
        f"{m.get('beyond_horizons')}.",
        f"- Intolerability threshold: {m.get('intolerability_threshold')}.",
        f"- {m.get('mtpd_rule')}", f"- {m.get('rto_rule')}"])


def _numbered(folder: Path, path: str, numbers: list[int], read: checks.Read) -> list[str]:
    """`path:n | text` for each non-blank line of `numbers`; each is a line read."""
    lines, out = _lines(folder, path), []
    for n in numbers:
        if 0 < n <= len(lines) and lines[n - 1].strip():
            read[(path, n)] = lines[n - 1]
            out.append(f"{path}:{n} | {lines[n - 1]}")
    return out


def _interview_rows(folder: Path, activity: str, read: checks.Read) -> list[str]:
    return [row for p in drafting.own_interviews(folder, activity)
            for row in _numbered(folder, p, list(range(1, len(_lines(folder, p)) + 1)), read)]


def _day_rows(folder: Path, interviews: list[str], read: checks.Read) -> list[str]:
    """536 (544): the interviews of the day his line names, every line numbered: its rows and no
    other day's."""
    return [row for p in interviews
            for row in _numbered(folder, p, list(range(1, len(_lines(folder, p)) + 1)), read)]


def _record_rows(folder: Path, activity: str, read: checks.Read) -> list[str]:
    """Last year's record: the sections of the prior record that name the activity."""
    source = core.last_year(folder, activity).get("source")
    if not source:
        return []
    rec = _lines(folder, str(source))
    heads = [i for i, t in enumerate(rec, 1) if t.startswith("### ")] + [len(rec) + 1]
    return [row for a, b in zip(heads, heads[1:], strict=False)
            if f"`{activity}`" in "\n".join(rec[a - 1:b - 1])
            for row in _numbered(folder, str(source), list(range(a, b)), read)]


def _plan_rows(folder: Path, activity: str, read: checks.Read) -> list[str]:
    plan = _lines(folder, core.PROGRAMME_PLAN)
    name = core.map_name(folder, activity)
    return _numbered(folder, core.PROGRAMME_PLAN,
                     [i for i, t in enumerate(plan, 1) if f"| {name} |" in t], read)


def _asset_of(text: str, parsed: list[tuple[int, int, dict[str, Any]]], at: int) -> dict[str, Any]:
    """The register entry (the innermost object with a name) that holds the object at `at`."""
    around = [(s, o) for s, e, o in parsed if s < at < e and "name" in o]
    return max(around, key=lambda x: x[0])[1] if around else {}


def _consumer_fact(asset: dict[str, Any], row: dict[str, Any]) -> str:
    """A register consumer as one row of facts: its resource's name, type and owner, then the
    consumer's own cells (the row's RTO, need, workaround)."""
    skipped = ("department", "dept", "activity")
    own = (f"{k}: {v}" for k, v in row.items()
           if not isinstance(v, (dict, list)) and k not in skipped)
    return "; ".join([f"name: {asset.get('name')}", f"type: {asset.get('asset_type')}",
                      f"owner: {asset.get('owner_name')}", *own])


def _register_rows(folder: Path, activity: str, read: checks.Read) -> list[str]:
    """One row per consumer of the activity in the register, cited at the consumer's first line (a
    cite there reads the whole consumer row and its resource, `checks.evidence`)."""
    text = (folder / core.REGISTER).read_text(encoding="utf-8")
    lines = text.splitlines()
    spans = checks._objects(text)
    parsed = sorted(((start, end, json.loads(text[start:end])) for _, _, start, end in spans),
                    key=lambda x: x[0])
    first = {start: line for line, _, start, _ in spans}
    out = []
    for start, _, row in parsed:
        if row.get("department") == activity and "need" in row:
            n = first[start]
            read[(core.REGISTER, n)] = lines[n - 1]
            out.append(f"{core.REGISTER}:{n} | "
                       f"{_consumer_fact(_asset_of(text, parsed, start), row)}")
    return out


def raw_rows(folder: Path, activity: str | None, read: checks.Read,
             interviews: list[str] | None = None) -> list[str]:
    """The focus activity's raw rows, numbered by file and line: its interviews (or, where his
    line names a day, that day's interviews and no other's), its prior record's section, its
    programme-plan row, and a row per register consumer. Facts as the files hold them, never
    sentences; every row is a line read."""
    rows = _day_rows(folder, interviews, read) if interviews is not None else \
        _interview_rows(folder, activity or "", read)
    if activity is None:
        return rows
    return [*rows, *_record_rows(folder, activity, read),
            *_plan_rows(folder, activity, read), *_register_rows(folder, activity, read)]


def _closing(path: str, last: int, total: int) -> str:
    if last >= total:
        return f"[end of {path}: {total} lines]"
    return f"[cut at line {last} of {total}; read on with read_file(path=\"{path}\", " \
        f"start={last + 1})]"


def read_file(folder: Path, path: str, start: Any, end: Any, read: checks.Read) -> str:
    """523, absorbed: lines `start`..`end` of one room file, every line numbered, at most
    `READ_CAP` of them, a closing line saying where it was cut and how to read on. Each line shown
    is a line read."""
    if path not in core.room_files(folder):
        return NOT_A_FILE.format(path=path)
    lines = _lines(folder, path)
    first = max(1, int(start or 1))
    last = min(len(lines), int(end or len(lines)), first + READ_CAP - 1)
    for n in range(first, last + 1):
        read[(path, n)] = lines[n - 1]
    return "\n".join([*(f"{n}\t{lines[n - 1]}" for n in range(first, last + 1)),
                      _closing(path, last, len(lines))])


# ── the lists the check reads whole (605: never handed in the brief) ──────────────────────────────
ASKS_LAST = re.compile(r"\blast (?:time|interview|participants)\b|\bwho was there\b|\bwere there\b"
                       r"|\battended\b", re.I)


def _function(role: str) -> str:
    return role.split(",")[0].strip()


def _mtpd(folder: Path, activity: str | None, line: str) -> list[str]:
    reading = checks.method_reading(checks.Room(folder, {}, line), activity) if activity else None
    return [reading] if reading else []


def _due(folder: Path, activity: str | None, line: str) -> list[str]:
    _, rows = core._plan_table(folder)
    return [r[1] for r in core._due_and_others(rows)[0]]


def _last_participants(folder: Path, activity: str | None, line: str) -> list[str]:
    return [_function(role) for _, role in core.last_participants(folder, activity)
            if "interviewer" not in role] if activity else []


def _invitees(folder: Path, activity: str | None, line: str) -> list[str]:
    return [_function(role) for _, role, _ in core.invitees(folder, activity)] if activity else []


def _suppliers(folder: Path, activity: str | None, line: str) -> list[str]:
    return [str(a["name"]) for a in drafting.read_register(folder).values()
            if isinstance(a, dict) and a.get("asset_type") == line_reads.SUPPLIER
            and any(c.get("department") == activity for c in a.get("consumers") or [])]


#: (the list, whether his line asks for it, how code reads it): each from the files, never typed
LISTS: list[tuple[str, Callable[[str], Any], Callable[[Path, str | None, str], list[str]]]] = [
    ("the method's MTPD reading",
     lambda line: core.asks_how_long_down(line) is not None or checks.MTPD.search(line), _mtpd),
    ("the due list", core.asks_which_due, _due),
    ("the last participants", ASKS_LAST.search, _last_participants),
    ("the invitees", lambda line: core.WHO_COMES.search(line) or core.INVITE_WORDS.search(line),
     _invitees),
    ("the suppliers", core.DEPENDENCY_WORDS.search, _suppliers),
]


def drawn(folder: Path, activity: str | None) -> list[str]:
    """632: what the activity's graph draws by the one company-wide table
    (`merge_table.this_bia`), its boxes' members and the suppliers drawn as a line on a box: each
    counts as covered on an answer that draws the graph. What it lists beside the graph
    (`notDrawn`'s other rules) is not drawn; no activity, nothing."""
    if not activity:
        return []
    register = drafting.read_register(folder)
    return [*dict.fromkeys(str(x) for box in merge_table.this_bia(register, activity)[
        "boxes"].values() for x in [*(register[k].get("name") for k in box["members"]),
                                    *(box.get("lines") or [])])]


def code_lists(folder: Path, line: str, activity: str | None) -> dict[str, list[str]]:
    """The whole lists his line asks for, as code reads them from the files (each item once): the
    check's must-cover, never handed to the model (605: it calls the fact tools)."""
    out = {label: list(dict.fromkeys(items(folder, activity, line)))
           for label, asks, items in LISTS if asks(line)}
    return {label: items for label, items in out.items() if items}


# ── state, the brief ────────────────────────────────────────────────────────────────────────────
@dataclass
class State:
    """What a room's conversation carries from turn to turn: the focus activity, his earlier lines,
    the exchange as he saw it, and what was last shown with the lines it cited."""

    focus: str | None = None
    #: 584 r2: the answer that stood named several activities, so the next line is not asked
    several: bool = False
    #: 614: code's which-activity ask was sent, so no later line is asked it again
    asked: bool = False
    #: 758: this turn a walk is on the table (`run`'s `walking`), so a head word moves nothing
    walk: bool = False
    lines: list[str] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    shown: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Brief:
    text: str
    #: 605: the lists his line asks for, the check's alone: never in `text` (the facts are tools)
    lists: dict[str, list[str]]
    focus: str | None
    #: 536 (544): the day his line names, and that day's interviews (empty where it holds none)
    day: Any = None
    day_interviews: list[str] = field(default_factory=list)
    #: 604: code's yes or no for his line (`verdict`), None where it asks for none
    verdict: dict[str, Any] | None = None


@dataclass(frozen=True)
class Walk:
    """608: the walk's tools, offered while the conversation is on a walk, and `Session`'s call of
    one as a model turn: its result as the model reads it, and the result that ends the turn (a
    standing refusal, nemo's interview question) or None."""

    tools: list[dict[str, Any]]
    call: Callable[[str, dict[str, Any]], tuple[str, dict[str, Any] | None]]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(t["function"]["name"] for t in self.tools)


def verdict(folder: Path, line: str, focus: str | None) -> dict[str, Any] | None:
    """604 (ADR-0061 decision 4): code's yes or no for his line, from `core.spof`, where it asks
    for one: on a single-point ask, whether the focus activity has a row the register flags (the
    rows of the resources it names, where it names any of them); on whether anything depends on
    one register resource, whether an activity's row uses it (those his line names, else any) or
    another entry depends on it. None where his line asks neither."""
    if not YES_NO_ASK.search(line):
        return None
    register = {k: a for k, a in drafting.read_register(folder).items()
                if isinstance(a, dict) and a.get("name")}
    named = [k for k, a in register.items()
             if re.search(rf"(?<!\w){re.escape(str(a['name']))}(?!\w)", line, re.I)]
    named = [k for k in named if not any(k != o and str(register[k]["name"]).lower() in
                                         str(register[o]["name"]).lower() for o in named)]
    if core.SPOF_WORDS.search(line):
        if focus is None:
            return None
        rows = core.spof(folder, focus)["rows"]
        one = [r for r in rows if r["resource"] in {register[k]["name"] for k in named}]
        return {"verdict": any(r["flagged"] for r in one or rows),
                "about": core._dot_listed(sorted({r["resource"] for r in one}))
                or core.map_name(folder, focus),
                "rows": sorted({r["resource"] for r in one or rows if r["flagged"]}),
                "none": NONE_FLAGGED}
    if len(named) != 1 or not re.search(
            DEPENDS_ON + re.escape(str(register[named[0]]["name"])), line, re.I):
        return None
    name, asked = str(register[named[0]]["name"]), core.named_in(folder, line)
    users = [core.map_name(folder, a) for a in asked or walk.processes(folder)
             if any(r["resource"] == name for r in core.spof(folder, a)["rows"])]
    users += [] if asked else [str(a["name"]) for a in register.values()
                               if named[0] in (a.get("depends_on") or [])]
    return {"verdict": bool(users), "about": name, "rows": users, "none": NONE_DEPENDS}


def _verdict_said(v: dict[str, Any], says: str = VERDICT_SAID, **kw: str) -> str:
    return says.format(about=v["about"], verdict="Yes" if v["verdict"] else "No",
                       rows=core._dot_listed(v["rows"]) or v["none"], **kw)


def _day_owner(folder: Path, line: str) -> list[str]:
    """536 (544, t550): the one activity the interviews of the day his line names are about, where
    they name exactly one."""
    day = core.named_day(folder, line)
    owners = ({a for p in core.day_interviews(folder, day)
               for a in interview._named_in(folder / p)} if day else set())
    return list(owners) if len(owners) == 1 else []


#: 758: a word pointing back at what is on the table, and the years that hold one and do not
POINTS_BACK = re.compile(r"\b(?:this|that|it|these|those|here)\b", re.I)
A_YEAR = re.compile(r"\b(?:this|last|next) year\b", re.I)
#: 758 (49, tick 19:39:03): the only words that may touch a head word for it to stand bare
AFTER_BARE = frozenset("a an about and or if when can could would will does do did is are was were "
                       "be how what which who down".split())
BEFORE_BARE = (AFTER_BARE | {"of", "for"}) - {"down"}  # 49, tick 20:19:25: "shut down production"
#: 758 (49, tick 18:00:16): a mark that ends the touch on its side; an apostrophe or slash joins
ENDS_TOUCH = frozenset(".,?!:;")


def _stands_bare(said: list[str], at: int) -> bool:
    """758: each word touching `said[at]` is absent, a mark ending the touch, or on its side's list.
    """
    return all(n in BEFORE_BARE or n in ENDS_TOUCH for n in said[max(at - 1, 0):at]) \
        and all(n in AFTER_BARE or n in ENDS_TOUCH for n in said[at + 1:at + 2])


def _core_head(folder: Path, line: str) -> list[str]:
    """758: the one core process (`core.core_pick`, the list `ask_activity` offers) his line names
    by a head word no other core process is called by; none where the line points back at what is
    on the table ("does this hit production?"), two are named, or a word touching it says it is
    not the process ("production manager"). Read among the core alone, so "procurement" names Raw
    material procurement and "support" names nothing."""
    if POINTS_BACK.search(A_YEAR.sub("", line)):
        return []
    # 49, tick 19:59:37: not core._map_key, whose spaces would hide a hyphen from the two lists
    said = re.findall(r"\w+|[^\w\s]", line.lower())
    heads = {a: core._name_heads(name, 5)
             for name, a in core.core_pick(folder, walk.processes(folder))}
    own = {a: words - set().union(*(w for b, w in heads.items() if b != a))
           for a, words in heads.items()}
    named = [a for a, words in own.items() if words & set(said)]
    return named if len(named) == 1 and all(
        _stands_bare(said, i) for i, w in enumerate(said) if w in own[named[0]]) else []


def _focus(folder: Path, line: str, state: State) -> str | None:
    """The activity the turn is about: the one his line names, else the one the interviews of the
    day it names are about (544's card activity), else the core process it names by a head word
    (758, never during a walk), else the conversation's (584: the activity of the answer that
    stood, where its first line or the whole of it named exactly one: `_stood_on`), else the one
    his earlier lines name. None
    where none of them does: code never picks one for him (566: the plan's next BIA was handed to
    every turn that named none)."""
    named = core.named_in(folder, line) or _day_owner(folder, line) \
        or ([] if state.walk else _core_head(folder, line)) \
        or ([state.focus] if state.focus else []) \
        or line_reads.asked(folder, line, state.lines)
    return named[0] if named else None


def _today(folder: Path) -> str:
    today = core.story_today(folder)
    return f"Today is {today:%A}, {today.day} {today:%B %Y}." if today else ""


def last_chart(folder: Path, state: State) -> dict[str, Any] | None:
    """538: the last chart shown, this conversation's, else the room's (533's store: a reopened
    room or the brake's chart)."""
    return next((a for a in reversed(state.shown) if a["template"] == CHART), None) \
        or kept.last(folder, kept.CHART)


def _last_shown(folder: Path, state: State, read: checks.Read) -> str:
    """One line per artefact last shown, with the lines it cited (read again this turn: a cite of
    them stands); the room's last chart where this conversation showed none (538)."""
    out = []
    chart = last_chart(folder, state)
    were = [*([] if chart is None or chart in state.shown else [{**chart, "cites": []}]),
            *state.shown]
    for a in were[-5:]:
        out.append(f"- {a['template']} {json.dumps(a['arguments'], ensure_ascii=False)[:600]}")
        for path, n, text in a["cites"]:
            read[(path, n)] = text
            out.append(f"  cited then: {path}:{n} | {text}")
    return "Last shown:\n" + ("\n".join(out) if out else "nothing yet")


def _day_block(day: Any, held: list[str]) -> str:
    """536 (544): the day his line names, as data: its interviews where it holds any, the fact
    that it holds none where it does not. The control is the stack's (`checks.OTHER_DAY`)."""
    said = f"He names {day:%A}, {day.day} {day:%B %Y}"
    if not held:
        return (f"{said}, a day holding no interview: the files as usual, and say the day holds "
                "none.")
    return "\n".join([
        f"{said}: the answer stands on that day's interview"
        f"{'s' if len(held) > 1 else ''} and on no other day's:",
        *(f"- {p}" for p in held)])


def ask_activity(folder: Path) -> str:
    """566's ask, 575's list: the room's core processes (its process map's section-1 rows,
    `core.core_pick`), each in his words, never typed here; a room whose map has none names all."""
    activities = walk.processes(folder)
    named = [a for _, a in core.core_pick(folder, activities)] or activities
    return ASK_ACTIVITY.format(activities=", ".join(core.map_name(folder, a) for a in named))


def brief(folder: Path, line: str, state: State, read: checks.Read) -> Brief:
    """The turn's brief, by code: today, the method's rules, the file map, what was last shown, the
    focus activity's raw rows, and (536, 544) the day his line
    names, whose interviews are the rows where it names one that holds any. Every row shown is a
    line read."""
    focus = _focus(folder, line, state)
    day = core.named_day(folder, line)
    held = core.day_interviews(folder, day) if day else []
    rows = raw_rows(folder, focus, read, interviews=held or None) if held or focus else []
    lists = code_lists(folder, line, focus)
    yes_no = verdict(folder, line, focus)
    said = f"Focus activity: {core.map_name(folder, focus)}. Its raw rows, each as " \
        "path:line | text:" if focus else "No focus activity yet."
    named = "\n".join(filter(None, [_day_block(day, held) if day else "", said,
                                    "\n".join(rows)]))
    text = "\n\n".join(filter(None, [
        _today(folder), method_rules(folder), "File map (path: what it holds):\n" +
        file_map(folder), _last_shown(folder, state, read), named,
        _verdict_said(yes_no) if yes_no else ""]))
    return Brief(text, lists, focus, day, held, yes_no)


# ── the tools: one read, two templates ──────────────────────────────────────────────────────────
def _fn(name: str, says: str, props: dict[str, Any], need: list[str]) -> dict[str, Any]:
    return {"type": "function", "function": {"name": name, "description": says, "parameters": {
        "type": "object", "properties": props, "required": need}}}


_S: dict[str, Any] = {"type": "string"}
_L: dict[str, Any] = {"type": "array", "items": _S}
READ_TOOL = _fn("read_file", "Read lines of one room file; every line comes numbered. At most "
                f"{READ_CAP} lines a call; a closing line says where it was cut.",
                {"path": _S, "start": {"type": "integer"}, "end": {"type": "integer"}}, ["path"])
#: 603 (ADR-0061 d3): one template per kind of question, the page's shapes, and the free answer
TEMPLATES = shapes.tools()
TEMPLATE_NAMES = tuple(t["function"]["name"] for t in TEMPLATES)
#: 603: the two old templates, no longer offered: a call by their name is still read (610 deletes)
OLD = ("judgement", "graph_link")
# 538: the chart is a template tool too, kept apart from the text shapes
CHART_TOOL = _fn(
    CHART, "nemo's impact-over-time chart, its look fixed: one chart per activity, stacked. "
    "activities: the activities' ids or names; classes: impact class ids, an empty list for "
    "every class; years: \"last\" and/or \"this\". To change the last chart, call it with only "
    "the arguments that change: one left out keeps the last chart's.",
    {"activities": _L, "classes": _L, "years": _L}, [])
# 539, 540: the letter frame and the invitation, beside them
LETTER_TOOL = _fn(
    LETTER, "A letter in nemo's frame to one person, shown as a draft; nemo adds the greeting, "
    "the closing and the address, and only his tap puts it in Drafts. to: one function as the "
    "organisation file names it, never an address, one who holds what the body cites. Several "
    "people take several calls in one reply: every holder fact_gap_owners names gets a call, each "
    "body that holder's own gaps and no one else's. subject; body: the letter's own words, with "
    "no greeting or sign-off, each figure with the [path:line] cite of a line you read (nemo "
    "checks it and takes the cite out). To change the last draft, call it with only what changes: "
    "an argument left out keeps the last draft's.", {"to": _L, "subject": _S, "body": _S}, [])
INVITE_TOOL = _fn(
    INVITATION, "The interview invitation, its frame nemo's; only his tap moves it in the "
    "calendar and puts it in Drafts. activity: its id or name; date: the day as YYYY-MM-DD, "
    "for a weekday his line names the date fact_weekday gives; "
    "time: the start as HH:MM, only where his line names the hour. To move the last invitation, "
    "call it with only what changes: an argument left out keeps the last invitation's.",
    {"activity": _S, "date": _S, "time": _S}, [])
OFFERED = [*TEMPLATES, CHART_TOOL, LETTER_TOOL, INVITE_TOOL]
# 605 (ADR-0061 d2): 601's facts, each a tool returning values (`fact`)
FACT = "fact_"
#: the facts of the room as a whole, called with no activity
ROOM_FACTS = ("due", "next_bia")
#: 631: the day a weekday falls on, called with the word
DAY_FACT = "weekday"
FACT_SAYS = {
    "compare": "what this year's interview says changed since last year's record",
    "mismatches": "what does not match: this year's interview against last year's record and the "
                  "impact grid, cell by cell",
    "gap_owners": "who owns the activity's gaps, and who decides",
    "mtpd_reading": "the method's MTPD reading of this year's grid, with the record's RTO",
    "last_participants": "who was there last time: the people of the last interview, as (name, "
                         "role)",
    "invitees": "whom to invite to the interview, as (name, role, from the register)",
    "due": "the BIAs due or overdue for review, by the programme plan",
    "next_bia": "the BIA to do next, by the programme plan",
    "spof": "each register resource the activity uses, its workaround and whether it is flagged "
            "a single point of failure",
    "risk_controls": "what the risk register states for each resource the dependencies fact "
                     "lists for the activity: each risk row naming it, with the row's id, risk, "
                     "activities, marking and existing controls. A row's activities say whom its "
                     "controls are for. It can state a workaround where the dependency register "
                     "gives none for this activity: say what each register says. "
                     "Give the rows of the resources he asks about",
    "dependencies": "what the activity depends on, group by group (the suppliers too), and the "
                    "process map's upstream and downstream",
    "quotes": "the interview's words behind each open finding",
    "focus": "what the activity's BIA should focus on now",
    "unrated_last_year": "the hours of last year's grid left not rated (the cell holds \"–\"), by "
                         "class, to read before saying what last year rated across its hours; "
                         "empty where it holds no such cell or no grid",
    DAY_FACT: "the date a weekday his line names falls on, as YYYY-MM-DD: the next one after the "
              "room's today, today's own weekday the one a week on"}
#: each fact's arguments and what the model is told of them
FACT_ARGS = {n: ({}, "") if n in ROOM_FACTS else (
    {DAY_FACT: _S}, " weekday: the word as his line says it, e.g. Thursday.") if n == DAY_FACT
    else ({"activity": _S}, " activity: its id or name; left out, the focus activity's.")
    for n in core.FACTS}
FACT_TOOLS = [_fn(FACT + n, f"Code's values, read from the files: {FACT_SAYS[n]}." +
                  FACT_ARGS[n][1], FACT_ARGS[n][0], []) for n in core.FACTS]
FACT_NAMES = tuple(FACT + n for n in core.FACTS)
FACT_SENTENCE = "{name} gave a sentence, not values: nemo does not hand it on."
FACT_WHICH = "{name} needs an activity: call it again with its id or name."
FACT_OFF = ("{name}: {value!r} names no one activity the room holds: call it again with one "
            "activity's id or name.")
FACT_FAILED = "{name} could not be read from the room's files."
FACT_NO_DAY = "{name} needs a weekday, Monday to Sunday: call it again with the word his line says."
#: 645: what a fact's result counts, by the thing a who or how-many line counts (`checks.Room`)
FACT_COUNTS: dict[str, Callable[[Any], dict[str, int]]] = {
    "gap_owners": lambda v: {"people": len(v["holders"]),
                             "gaps": sum(len(h["gaps"]) for h in v["holders"])},
    "mismatches": lambda v: {"mismatches": len(v["moved"])} if v and v["moved"] else {},  # 759
    # 655 (49's ruling): the activity's single points of failure, the resources `core.spof` flags
    "spof": lambda v: {"flagged": len({r["resource"] for r in v["rows"] if r["flagged"]})}}


def fact(folder: Path, name: str, args: dict[str, Any], focus: str | None) -> str:
    """605: a fact tool's call, the fact function's values as JSON (the activity it names, else
    the turn's focus); a fact that comes back a sentence is refused, never handed on."""
    if name == DAY_FACT:  # 631
        if (found := core.FACTS[name](folder, str(args.get(DAY_FACT) or ""))) is None:
            return FACT_NO_DAY.format(name=FACT + name)
    elif name in ROOM_FACTS:
        found = core.FACTS[name](folder)
    else:
        said = args.get("activity")
        activity = fact_activity(folder, name, args, focus)
        if activity is None:
            return (FACT_OFF.format(name=FACT + name, value=said) if said
                    else FACT_WHICH.format(name=FACT + name))
        found = core.FACTS[name](folder, activity)
    if isinstance(found, str):
        return FACT_SENTENCE.format(name=FACT + name)
    return json.dumps(found if name == DAY_FACT else room_words(folder, found), ensure_ascii=False)


def room_words(folder: Path, value: Any) -> Any:
    """645: a fact's values in the room's words: each person the organisation file names by their
    function (`words.functions_only`), each ISO date as the room writes it ("Mon 9 Nov 2026"); a
    quote stays as said."""
    held = words.people(folder)

    def said(x: Any, key: Any = None) -> Any:
        if isinstance(x, dict):
            return {k: said(v, k) for k, v in x.items()}
        if isinstance(x, list | tuple):
            return [said(v) for v in x]
        if not isinstance(x, str) or key == "quote":
            return x
        return words.functions_only(checks.ISO_DATE.sub(_room_date, x), folder, held=held)
    return said(value)


def _room_date(m: re.Match[str]) -> str:
    """645: an ISO date as the room writes it, "Mon 9 Nov 2026" (no locale); one that is no day
    stays as written."""
    try:
        d = date(int(m["year"]), int(m["month"]), int(m["day"]))
    except ValueError:
        return m[0]
    return f"{checks.WEEKDAYS[d.weekday()][:3]} {d.day} {checks.MONTHS[d.month - 1]} {d.year}"


def fact_activity(folder: Path, name: str, args: dict[str, Any], focus: str | None) -> str | None:
    """The activity a fact call reads (the one it names, else the focus); "" for the room's."""
    if name in ROOM_FACTS or name == DAY_FACT:
        return ""
    return _one_activity(folder, args["activity"]) if args.get("activity") else focus


def _leaves(value: Any) -> set[str]:
    """605: a fact's values, each as text: what an answer may state from it with no cite. A bare
    number (a count, a line number) is no such value: it would stand for any claim."""
    if isinstance(value, dict | list):
        return {x for v in (value.values() if isinstance(value, dict) else value)
                for x in _leaves(v)}
    return {value} if isinstance(value, str) and re.search(r"[^\W\d_]", value) else set()


OFFERED_NAMES = (*TEMPLATE_NAMES, CHART, LETTER, INVITATION)
READ_NAMES = (*OFFERED_NAMES, *OLD)
#: 646: each offered template's required parts: the answer shapes' first line, and none for the
#: chart, the letter and the invitation (a part left out keeps the last one's)
REQUIRED: dict[str, list[str]] = {t["function"]["name"]: t["function"]["parameters"]["required"]
                                  for t in OFFERED}


def _blank(value: Any) -> bool:
    return not any(str(x).strip() for x in checks.as_list(value))


#: 677: a letter's parts it needs where no last draft holds them (A8: a body alone is no letter)
LETTER_NEEDS = ("to", "subject")


def _no_items(name: str, args: dict[str, Any]) -> bool:
    """677: a first line that heads a list (A9's "check these yourself:", markdown and all) with
    nothing under it: no item and nothing the files do not say."""
    heads = str(args.get("answer") or "").rstrip(" *_").endswith(":")
    return name in REQUIRED and heads and _blank(args.get("details")) \
        and _blank(args.get("not_stated"))


def missing(name: str, args: dict[str, Any], kept: tuple[str, ...] = ()) -> list[str]:
    """646: the required parts a template call leaves out or blank: one is a failed call. 677: a
    letter's recipient and subject where the last draft does not hold them (`kept`), and a list's
    items."""
    if name == LETTER:
        return [k for k in LETTER_NEEDS if k not in kept and _blank(args.get(k))]
    need = [k for k in REQUIRED.get(name, []) if _blank(args.get(k))]
    return need or (["details"] if _no_items(name, args) else [])


def carries_no_answer(reply: dict[str, Any], kept: tuple[str, ...] = ()) -> bool:
    """646: a reply whose template calls all leave a required part out (`missing`): the lane asks
    the next provider for it (`lanes.NO_ANSWER`), as it does an empty reply (615)."""
    said = [(str(fn.get("name")), _args(fn)) for c in reply.get("tool_calls") or []
            for fn in [c.get("function") or {}] if fn.get("name") in REQUIRED]
    return bool(said) and all(a is not None and missing(n, checks.arrived(a), kept)
                              for n, a in said)

SYSTEM = " ".join([
    "You are nemo, a colleague who knows business continuity, answering a business continuity "
    "manager from his company's files. You lead the turn: decide what he asks for, read what you "
    "need, then answer by calling exactly one template tool. Never answer in prose.",
    "Each user turn starts with what nemo's code hands you: today's date, the method's rules, the "
    "file map, what was last shown and the focus activity's raw rows, each as path:line | text. "
    "read_file reads more. For a fact (who was there last time, whom to invite, what is due, "
    "what does not match, the MTPD reading, the dependencies and suppliers), call its fact_ "
    "tool: its values are code's read of the files.",
    "End every sentence that states a figure, date, count, impact class or name with the "
    "[path:line] cite of a line you read this turn, e.g. [07_Interviews/x.md:12]; each figure in "
    "it must stand on that line. nemo checks this and removes sentences that fail.",
    "Where a fact_ tool gives a list, write all of it; never shorten it, never build one of "
    "your own. A question about people is answered from the fact_ tools, never an invitation.",
    "Where the files do not say something, write 'not named' or 'not stated', never that it does "
    "not exist. Say a thing was done only if a tool did it this turn; nothing is ever sent.",
    "Name people by their function (Plant Manager), not their name, unless he asks for names.",
    "To change something shown before, call the same template again with only that changed.",
    "Each kind of question has its shape tool: call the one that fits; where none fits, call "
    "answer. The first line answers the question (a yes/no starts with Yes or No, a 'how long' "
    "with the time), with no preamble; then the reasons one per line, at most six; what the files "
    "do not say goes in not_stated. Where a figure is a proposal, name who decides. Two figures "
    "that disagree are both shown, each with who said it. A table holds figures only; its "
    "explanation goes under it. Draw a chart only when he asks for one.",
    "A letter calls letter with its recipients by function, never an address: nemo adds each "
    "address. A day for the interview calls invitation with the date. His tap places either.",
])
#: 608: said to the model only while it is handed the walk's tools
WALK_SAYS = ("He is walking a BIA. The walk's tools read where it stands (get_step, "
             "get_evidence); a change he asks for is proposed through its tool (decide), nemo "
             "shows it as his tap, and only his tap records it. Never say a change is recorded.")
PROSE = ("You answered in prose. Call the shape template that fits the question (answer where "
         "none does), or letter, invitation or impact_over_time, with your answer in its "
         "arguments.")
SEND_BACK = (
    "nemo checked your {name}. These items failed:\n{failed}\nEverything else PASSED and is "
    "FROZEN: call {name} again with exactly these arguments, changing only the failed items (fix "
    "each with a line you read, or leave it out). Every other item must stay as it is, word for "
    "word:\n{frozen}")


def _bullets(items: list[Any]) -> list[str]:
    return [f"- {x}" for x in items if str(x).strip()]


def _reason(r: Any) -> str:
    """One reason as shown: its text, its cite once (the model may put it in the text too)."""
    if not isinstance(r, dict):
        return f"- {r}"
    text = checks.CITE.sub("", str(r.get("text", ""))).strip()
    cite = str(r.get("cite") or "").strip("[] ")
    return f"- {text} [{cite}]" if cite else f"- {text}"


#: 647: a speaker's "First Last:" at a line's start, which a cite's fragment leaves out
_WORD = r"[A-ZÄÖÜ][^\s:]*[a-zäöüß][^\s:]*"
SPEAKER = re.compile(rf"^(?:{_WORD}\s+){{1,3}}{_WORD}:\s+")


def _at_line(folder: Path, path: str, at: int) -> str:
    """602: the text fragment that opens the reader at the cited line, as t638 draws it (a table
    row's longest cell, no `**` or backticks), and marks all of it: start and end words; a
    speaker's name is never in it, the quoted words are (647)."""
    lines = _lines(folder, path)
    said = lines[at - 1] if 0 < at <= len(lines) else ""
    said = max(said.split("|"), key=len) if said.lstrip().startswith("|") else said
    said = re.sub(r"^\s*(?:[#>*-]+|\d+\.)\s+", "", said.replace("**", "").replace("`", ""))
    words = SPEAKER.sub("", said).split()
    ends = [words] if len(words) <= 8 else [words[:4], words[-4:]]
    return "#:~:text=" + ",".join(quote(" ".join(w), safe="").replace("-", "%2D")
                                  for w in ends) if words else ""


def cited(text: str, folder: Path, root: str, read: checks.Read | None = None,
          links: bool = True) -> str:
    """602 (ADR-0061 d8), 721: each point, one line of `text`, shows its first cite that holds as a
    numbered link to the room's own file at that line under the room's `root` (`<root>/w/<code>/
    read/…`, t638's reader; one number a line, the number alone where there is no root); its other
    cites go and leave no comma. A cite holds on a line the room's file has. With no `links` (a
    briefing, Q16) no point shows one. A made-up label in brackets goes too. A cite resolves as the
    check did, by the lines read (`read`)."""
    held: set[str] = set(workspace._files(folder))
    numbers: dict[tuple[str, int], int] = {}

    def holds(m: re.Match[str]) -> tuple[str, int] | None:
        path = checks._resolve(m["path"].strip(), read or {})
        ends = [f for f in held if f.endswith("/" + path)]
        path = path if path in held else ends[0] if len(ends) == 1 else ""
        ats = [int(re.split(r"\D", part.strip(), maxsplit=1)[0]) for part in m["at"].split(",")]
        size = len(_lines(folder, path)) if path else 0
        return next(((path, at) for at in ats if 0 < at <= size), None)

    def point(line: str) -> str:
        shown = not links

        def link(m: re.Match[str]) -> str:
            nonlocal shown
            first = None if shown else next(filter(None, map(holds, checks.CITE.finditer(m[3]))),
                                            None)
            opened, closed = m[2] or "", m[4] or ""
            if first is None:
                return "" if opened and closed else m[1] + opened if opened else closed
            shown = True
            path, at = first
            n = numbers.setdefault(first, len(numbers) + 1)
            # Amend 4 (t638): a no-break space, so "[1]." never wraps alone from the word before it
            return (NBSP if m[1] and root and not opened else m[1]) + opened + (CITE_LINK.format(
                n=n, link=f"{root}/read/{quote(path)}{_at_line(folder, path, at)}")
                if root else f"[{n}]") + closed
        kept = _CITE_RUN.sub(link, LABEL.sub("", line))
        return line if kept == line else _LEFT_BEHIND.sub("", kept)
    # a cite's list of lines may break over two: one point still
    one = checks.CITE.sub(lambda m: m[0].replace("\n", " "), checks.each_cite(text))
    return "\n".join(map(point, one.split("\n")))


def render(name: str, a: dict[str, Any], link: str = "") -> str:
    """What he sees: the template's fixed structure around the model's checked content; a graph
    answer's link is code's, drawn first (757)."""
    if name in shapes.TEXT or name == shapes.FREE:
        return shapes.render(name, a, link)
    if name == "judgement":
        unsaid = _bullets(checks.as_list(a.get("not_stated")))
        said = "\n".join(filter(None, [str(a.get("verdict") or "").strip(),
                                       *(_reason(r) for r in checks.as_list(a.get("reasons")))]))
        if not unsaid:
            return said
        # 584: a blank line before the heading, or it reads as the last reason's own line
        return "\n\n".join(filter(None, [said, "\n".join(["Not stated in the files:", *unsaid])]))
    if name == "graph_link":  # 632: the check cut it to its plain lines, nothing re-caps it
        kept = checks.graph_lines(a.get("lines"))
        said = "\n".join(x for x in (str(v).strip() for v in kept) if x)
        return f"{link}\n\n{said}" if link else said
    return ""


# ── 757: his pick B, drawn where the app sends a message and in the replay, nowhere earlier ─────
def _link_line(link: str) -> re.Pattern[str]:
    return re.compile(re.escape(link).replace(re.escape("{link}"), r"[^)\n]*"))


_GRAPH_LINE, _PDF_LINE = _link_line(GRAPH_LINK), _link_line(core.BRIEFING_PDF)
_STAGE_LINE = re.compile(r"\[[^\]\n]+\]\([^)\n]*#stage-\d+\)")
#: 722: where a link goes, which he does not read
_LINK_ADDRESS = re.compile(r"\]\([^)\n]*\)")
#: a point's opening label, as `LABELLED` reads one: no figure ("72 h:"), no table, quote or heading
#: and a term named at its first use ("RTO (recovery time objective):", `drawn_turn` runs first)
_POINT_LABEL = re.compile(r"( {0,3}(?:[-+]\s+|\d+\.\s+)?)(?!')(Not stated in the files:|"
                          r"(?:[^\s:*\[\]|#>.()\d\"\u201c\u201d\u201e\u2018]+\s+){0,2}"
                          r"[^\s:*\[\]|#>.()\d\"\u201c\u201d\u201e\u2018]+"
                          r"(?:\s+\([^()\n\d]*\))?:)(?=\s|$)")
#: a stop that ends no sentence
_ABBREVIATED = re.compile(r"(?<!\w)(?:Co|Dr|Prof|Mr|Mrs|Ms|St|Nr|Ltd|Inc)\.$")
#: a first line that is no verdict: a table, a heading, a quote, a list, an indent, a code span
_NO_VERDICT = re.compile(r"[|#>\-+\s]|\d+[.)\\]\s|.*`")


def _verdict_bold(line: str) -> str:
    """The first line's opening clause: to its first `;` or its first sentence's end
    (`core._sentences`, so never inside a quotation), and before any cite or link."""
    head, end = line.partition("[")[0].partition(";")[0], 0
    for sentence in core._sentences(head):
        end = head.index(sentence, end) + len(sentence)
        if not _ABBREVIATED.search(sentence):
            break
    said = head[:end].rstrip(" \t\u00a0(")
    return f"**{said}**{line[len(said):]}" if said else line


def in_bold(reply: str) -> str:
    """757: `reply` as he reads it on a phone: the link, the opening verdict and the label opening
    each point in bold; figures plain. It adds marks and changes no word. A line with marks of its
    own stands as written, as a stage label and what stands beside a PDF do; a fenced block's
    answer stands whole."""
    if "```" in reply:
        return reply
    drawn, opening = [], True
    for line in reply.split("\n"):
        if not line.strip() or _STAGE_LINE.fullmatch(line) or "*" in line:
            opening = opening and "*" not in line
            drawn.append(line)
        elif _GRAPH_LINE.fullmatch(line) or _PDF_LINE.fullmatch(line):
            opening = opening and not _PDF_LINE.fullmatch(line)
            drawn.append(f"**{line}**")
        elif opening and not _NO_VERDICT.match(line) and not _POINT_LABEL.match(line):
            opening = False
            drawn.append(_verdict_bold(line))
        else:
            opening = False
            m = _POINT_LABEL.match(line)
            drawn.append(f"{m[1]}**{m[2]}**{line[m.end():]}" if m else line)
    return "\n".join(drawn)


def bolds(record: dict[str, Any]) -> bool:
    """757: a turn the model led to an answer's shape; a letter, a chart, an invitation, the plain
    line and the brake's answers stand as today. By the record, so the replay reads it the same."""
    return record.get("path") == MODEL_LED and any(
        a.get("template") in {*shapes.TEXT, shapes.FREE, "judgement", "graph_link"}
        for a in record.get("artefacts_shown") or [])


def cut_for_pdf(turn: Turn) -> bool:
    """757: a briefing whose text stands in the model's history alone, its PDF link in its place."""
    return turn.template == "briefing" and bool(_PDF_LINE.match(turn.text))


def bold_turns(folder: Path) -> set[str]:
    """757: the ids of the turns on file that `bolds`, for the replay (`turn_file.Past` keeps no
    path). One line at a time, as `turn_file.past` reads: a line can hold hundreds of KB, so one
    that is no led turn is not parsed."""
    ids: set[str] = set()
    try:
        f = turn_file.path(folder).open("rb")
    except FileNotFoundError:
        return ids
    with f:
        for line in f:
            try:
                turn = json.loads(line) if MODEL_LED.encode() in line else None
            except ValueError:
                continue
            if isinstance(turn, dict) and bolds(turn) and turn.get(core.TURN_ID):
                ids.add(str(turn[core.TURN_ID]))
    return ids


# ── one turn ────────────────────────────────────────────────────────────────────────────────────
@dataclass
class Turn:
    """What a turn leaves: the text he sees, its path, and what the record keeps (`led_fields`)."""

    text: str
    path: str = MODEL_LED
    template: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    artefacts: list[dict[str, Any]] = field(default_factory=list)
    drops: list[dict[str, str]] = field(default_factory=list)
    must_cover_misses: list[str] = field(default_factory=list)
    sent_back: list[dict[str, str]] = field(default_factory=list)
    clock_s: float = 0.0
    model_s: float = 0.0
    tool_s: float = 0.0
    #: 536: the taps code draws with the turn (493's two, or the plain line's "Ask again" and
    #: next steps), each as (label, action); an answer that stands draws none yet (S5b)
    taps: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    #: 538: the charts a chart call drew (wide, one per activity, stacked) and their phone splits
    charts: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    #: 588: code's card over each chart, in its order (the text is these, joined)
    cards: list[str] = field(default_factory=list)
    #: 608: the walk call's result that ended the turn (`Walk.call`), shown by `Session`
    ended: dict[str, Any] | None = None


@dataclass(frozen=True)
class Clock:
    """537: a question's limit, an e-mail's, invitation's or chart edit's, and when the wait line
    shows, in seconds (his, 618; tests scale them down rather than wait)."""

    question_s: float = 45
    edit_s: float = 45
    checking_s: float = 10


#: 719: what `_done` tries: a template call, and what the checks said of it where they have read it
Try = tuple[str, dict[str, Any], checks.CheckedCall | None]


class _Held(NamedTuple):
    """756: a reply's letters that stood while one beside them went back, kept for its retry."""

    stood: list[dict[str, Any]]
    shown: list[dict[str, Any]]
    misses: list[list[str]]
    lost: list[dict[str, Any]]
    drops: list[dict[str, str]]


class _Late(Exception):
    """537: the turn's clock ran out before the model's reply came back."""


class _Run:
    """One turn's working state: the messages, what was read, the first try if it was sent back."""

    def __init__(self, folder: Path, line: str, chat: Lane, state: State,
                 graph: Callable[[str | None], str], next_taps: Callable[[], list[Any]],
                 clock: Clock, walking: Walk | None = None):
        self.folder, self.line, self.chat, self.state = folder, line, chat, state
        self.walking = walking
        self.ended: dict[str, Any] | None = None
        self.graph, self.next_taps = graph, next_taps
        self.link: str | None = None  # 632: the graph's link, drawn once a turn (`_link`)
        self.drawn: list[str] | None = None  # 632: what that graph draws, read once a turn
        self.t0 = time.time()
        self.edit = self._edits()
        self.limit = clock.edit_s if self.edit else clock.question_s
        self.read: checks.Read = {}
        self.said = ""  # 602: a model-led answer as checked, its cites as written
        self.brief = brief(folder, line, state, self.read)
        self.messages: list[dict[str, Any]] = [
            {"role": "system", "content": f"{SYSTEM} {WALK_SAYS}" if walking else SYSTEM},
            *state.history,
            {"role": "user", "content": f"{self.brief.text}\n\nHe typed: {line}"}]
        self.room = checks.Room(folder, self.read, line, said=list(state.lines),
                                activity=self.brief.focus, day=tuple(self.brief.day_interviews))
        self.calls: list[dict[str, Any]] = []
        self.sent_back: list[dict[str, str]] = []
        self.model_s = self.tool_s = 0.0
        self.retried = False  # 606: the turn's one send-back, of any kind, is made
        self.failed: list[dict[str, str]] = []  # 606: this reply's failed calls
        self.asked = False  # 614: this turn is code's which-activity ask
        self.unnamed: str | None = None  # 645: a fact call refused for want of an activity
        self.first: tuple[str, dict[str, Any], checks.CheckedCall] | None = None
        self.part: Try | None = None  # 646: a call its first line left
        self.passed: dict[str, Any] = {}  # 630: a sent-back letter's parts that passed
        self.to_failed = False  # 696: a letter sent back for naming someone else; see _draft_for
        self.later: list[dict[str, Any]] = []  # 651: the reply's letter calls after its first
        self.unwritten: list[dict[str, Any]] = []  # 651: its letter calls that failed as empty
        self.held = _Held([], [], [], [], [])  # 756
        #: every item of a list code handed: one the answer leaves out is recorded as a miss
        self.must_cover = [i for items in self.brief.lists.values() for i in items]

    def go(self) -> Turn:
        if (asked := line_reads.meant_question(self.folder, self.line)):
            # 493: a name that fits two things gets one question and two taps, and no model call
            question, taps = asked
            return self._turn(question, ASKED, None, {}, [], [], [],
                              [(label, {"kind": "meant", "line": said})
                               for label, said in taps])
        if self.brief.focus is None and self.state.lines and not self.state.several \
                and not self.state.asked and not self._drafting():
            return self._asking()
        try:
            return self._steps()
        except _Late:
            return self._in_hand() or self._late()
        except lanes.LaneDown:  # 727: a retry the lane lost, or a 402: the first try stands
            if (turn := self._in_hand()) is None:
                raise
            return turn

    def _steps(self) -> Turn:
        for n in range(1, MAX_STEPS + 1):
            calls = self._ask(n)
            if not calls:
                if self._prose(n):
                    continue
                break
            final, was = self._tools(calls), self.retried
            if self.unnamed and not self.held.stood:  # 645: no answer over the whole map
                return self._which()
            if self.ended:  # 608: the walk's refusal is the turn, the model's words never
                return self._turn(self.ended["say"], PLAIN, None, {}, [], [], [])
            if final and (turn := self._judge(*final, n >= MAX_STEPS or was)):
                return turn
            if self.failed and was:  # 606: a retry that fails ends the turn: never a third try
                return self._plain(self.failed)
            self.retried = self.retried or bool(self.failed)
        return self._plain([f for f in self.failed if f["reason"].startswith(EMPTY_CALL)])

    def _drafting(self) -> bool:
        """539: the last artefact shown is a letter or an invitation: a follow-up changes it."""
        return bool(self.state.shown) and self.state.shown[-1]["template"] in (LETTER, INVITATION)

    def _edits(self) -> bool:
        """537: an e-mail, invitation or chart edit, on the edit's clock: his line asks to write,
        to invite or for a chart, or it follows one of them shown last."""
        line = self.line
        return core.asks_to_write(line) or core.asks_for_chart(line) \
            or bool(core.INVITE_WORDS.search(line)) \
            or bool(self.state.shown) and self.state.shown[-1]["template"] in (LETTER, INVITATION,
                                                                              CHART)

    def _late(self) -> Turn:
        """537: the clock ran out: the time-limit line of the turn's kind with code's taps, and
        nothing shown, drawn or kept."""
        late = [{"text": "the turn", "reason": LATE_REASON.format(limit=self.limit)}]
        return self._turn(LATE_EDIT if self.edit else LATE_QUESTION, PLAIN, None, {}, late, [], [],
                          [(str(label), dict(action)) for label, action in self.next_taps()])

    def _in_hand(self) -> Turn | None:
        """618: the answer already back when the clock ran out (a first try sent back, its retry
        still out), standing as a last try does on its checks: the turn where it stands, else
        None."""
        if self.first is None and not self.held.stood:
            return None
        turn = self._plain([])
        return turn if turn.path == MODEL_LED else None

    def _asking(self) -> Turn:
        """566: a conversation under way whose activity resolves to none, so code asks which one
        and the lane is never called (M13: it is out of the model's hands). One plain sentence
        naming the room's activities in his words. A first line is not asked: with no exchange
        behind it, the model answers from the file map as 546 drew it. Nor is the line after an
        answer that named several (584 r2): it goes to the model as a first line does. Nor any line
        after the ask was sent once (614): a line that is not an activity name never loops on it."""
        self.asked = True
        return self._turn(ask_activity(self.folder), PLAIN, None, {}, [], [], [])

    def _which(self) -> Turn:
        """645: a fact call that needs an activity named none, and none is in focus: the answer is
        dropped and the turn is code's which-activity ask, as 566's is."""
        self.asked = True
        return self._turn(ask_activity(self.folder), PLAIN, None, {}, [*(
            f for f in self.failed if f["text"] != self.unnamed), {
            "text": "the answer", "reason": FACT_WHICH.format(name=self.unnamed)}], [], [])

    def _ask(self, n: int) -> list[dict[str, Any]]:
        """One model call; only message content and tool calls are kept (the reasoning, which the
        lane may send back, is neither read nor passed on). 537: the call waits in the copy's
        queue and is awaited until the turn's limit; past it the turn is late, a call still in line
        is never made, and one in flight is left to finish unread. 618: none starts past it."""
        m0 = time.time()
        if (left := self.t0 + self.limit - m0) <= 0:
            raise _Late
        ctx = contextvars.copy_context()
        kept = self._kept()  # 646: an empty call, to the next provider
        ctx.run(lanes.NO_ANSWER.set, lambda reply: carries_no_answer(reply, kept))
        pending = QUEUE.submit(ctx.run, self.chat, list(self.messages),
                               OFFERED if n >= MAX_STEPS else [READ_TOOL, *FACT_TOOLS, *(
                                   self.walking.tools if self.walking else []), *OFFERED])
        try:
            reply = pending.result(timeout=left)
        except TimeoutError:
            pending.cancel()
            raise _Late from None
        finally:
            self.model_s += time.time() - m0
        calls = reply.get("tool_calls") or []
        self.calls += calls
        self.messages.append({k: v for k, v in reply.items()
                              if k in ("role", "content", "tool_calls")})
        return list(calls)

    def _prose(self, n: int) -> bool:
        """Prose, not a template: sent back once. True where it was."""
        said = str(self.messages[-1].get("content") or "").strip()
        if not said or self.retried or n >= MAX_STEPS:
            return False
        self.retried = True
        self.sent_back.append({"kind": "prose", "said": said})
        self.messages.append({"role": "user", "content": PROSE})
        return True

    def _tools(self, calls: list[dict[str, Any]]) -> tuple[str, dict[str, Any]] | None:
        """Run the reads and answer every call; the first template call is the turn's answer, and
        a second is told so (602), but for a later letter call to someone new, a letter of its
        own (651)."""
        final, self.failed, self.later, self.unwritten, kept = None, [], [], [], self._kept()
        for c in calls:
            fn = c.get("function") or {}
            name = str(fn.get("name"))
            args = _args(fn)
            if args is not None and name in READ_NAMES:
                args = checks.arrived(args)  # 625: a list sent as a string, read once here
                if final is None and (need := missing(name, args, kept)):  # 646
                    result = self._empty(name, args, need)
                elif final and final[0] == name == LETTER \
                        and _new_to(args, [final[1], *self.later]):
                    self.later.append(args)
                    result = "Checking."
                else:
                    result = ALREADY.format(name=final[0]) if final else "Checking."
                    final, self.part = final or (name, args), None
            else:
                result = self._one(name, args)
            self.messages.append({"role": "tool", "tool_call_id": c.get("id"), "content": result})
            if self.ended:  # 608: the calls after it are not run
                break
        return final

    def _kept(self) -> tuple[str, ...]:
        """677: the letter parts a call may leave out: those the last draft holds, and every one
        on a send-back's retry (630 keeps what passed, and `letter_args` names what it lacks) and
        on a briefing's line with no draft (603 sends it back as no letter at all)."""
        before = self._again(LETTER, lambda a: True)
        if self.retried or before is None and shapes.asks_briefing(self.line):
            return LETTER_ARGS
        held = (before or {}).get("arguments") or {}
        return tuple(k for k in LETTER_ARGS if not _blank(held.get(k)))

    def _fail(self, name: str, said: str) -> str:
        """606: a failed call: its error goes to the model, and the turn keeps it as a drop."""
        self.failed.append({"text": name, "reason": said})
        return said

    def _empty(self, name: str, args: dict[str, Any], need: list[str]) -> str:
        """646: a template call that carried no answer: a failed call (606's one retry, with its
        reason), its other parts kept for what passed where the retry brings none."""
        if name == LETTER:  # 677: its parts that came, kept for the retry as 630 keeps them
            said = {k: v for k, v in args.items() if k in LETTER_ARGS and not _blank(v)}
            self.passed = checks.passed(said, letter_failed(self.folder, said))  # 696
            self.unwritten.append(args)
        elif not all(map(_blank, args.values())):
            self.part = (name, args, None)
        return self._fail(name, EMPTY_BACK.format(name=name, need=" and ".join(need)))

    def _one(self, name: str, args: dict[str, Any] | None) -> str:
        if args is None:
            return self._fail(name, BAD_JSON)
        walked = self.walking.names if self.walking else ()
        if name in walked:
            return self._walked(name, args)
        if name != "read_file" and name not in FACT_NAMES:
            return self._fail(name, NO_TOOL.format(name=name, names=", ".join([
                "read_file", *FACT_NAMES, *walked, *OFFERED_NAMES])))
        t0 = time.time()
        try:
            if name in FACT_NAMES:
                said = fact(self.folder, name.removeprefix(FACT), args, self.brief.focus)
                on_none = fact_activity(self.folder, name.removeprefix(FACT), args,
                                        self.brief.focus) is None
                if on_none and not args.get("activity"):
                    self.unnamed = name
                elif self.unnamed == name and not on_none:  # its call again, naming the activity
                    self.unnamed = None
                try:  # its values stand as read, with no cite, about its activity (607 Amend 2)
                    on = str(fact_activity(self.folder, name.removeprefix(FACT), args,
                                           self.brief.focus))
                    value = json.loads(said)
                    self.room.known_by[on] = self.room.known_by.get(on, set()) | _leaves(value)
                    self.room.marked |= checks.marked_values(said)  # 720
                except ValueError:
                    return self._fail(name, said)
                # 680: who was there, as it returned them
                self.room.participants |= {on: value} if name == FACT + "last_participants" else {}
                # 652: last year's unrated hours, as it returned them
                self.room.unrated |= {on: value} if name == FACT + "unrated_last_year" else {}
                if counts := FACT_COUNTS.get(name.removeprefix(FACT)):  # 645: its counts too
                    self.room.counts[on] = {**self.room.counts.get(on, {}), **counts(value)}
                return said
            path = str(args.get("path") or "")
            said = read_file(self.folder, path, args.get("start"), args.get("end"), self.read)
            return self._fail(name, said) if said == NOT_A_FILE.format(path=path) else said
        except (ValueError, TypeError):
            return self._fail(name, FACT_FAILED.format(name=name) if name in FACT_NAMES
                              else BAD_JSON)
        finally:
            self.tool_s += time.time() - t0

    def _walked(self, name: str, args: dict[str, Any]) -> str:
        """608: a walk tool's call, made by `Session` as a model turn. Its values and the figures in
        them stand uncited about the activity it names, as a fact's do (605) and as what nemo
        handed a tap's narration does (607); a result that ends the turn is kept."""
        assert self.walking is not None
        t0 = time.time()
        try:
            said, self.ended = self.walking.call(name, args)
        finally:
            self.tool_s += time.time() - t0
        named = args.get("activity")  # one no activity resolves to stands about none (not "")
        on = (_one_activity(self.folder, named) or str(named)) if named else self.brief.focus
        values = _leaves(json.loads(said))
        self.room.known_by[on or ""] = self.room.known_by.get(on or "", set()) | values | {
            f for v in values for f in checks.facts(v, self.room.classes, self.folder)}
        return said

    def _judge(self, name: str, args: dict[str, Any], last: bool) -> Turn | None:
        """The template call through the stack. A first try that fails is sent back with the rest
        frozen (None: ask again); a retry is held to the failed items and stands as it is."""
        if self.held.stood and name != LETTER:  # 756: the retry was for the letter sent back
            return self._plain([])
        if name == CHART:
            return self._chart(args, last)
        if name == LETTER:
            return self._letter(args, last)
        if name == INVITATION:
            return self._invitation(args, last)
        self.room.ran = [name]
        if self.first is None:
            checked = self._check(name, args)
            if last or self.retried or not (checked.failed or checked.refused):
                return self._done([(name, args, checked)], [])
            self.first = (name, args, checked)
            self._send_back(name, args, checked)
            return None
        (first_name, first_args, was), self.first = self.first, None
        if name != first_name:
            standing, refused = first_args, [{"text": "the template", "reason":
                                              checks.RETRY_CHANGED.format(path="the template")}]
        else:
            standing, refused = checks.retry(first_args, args, was.failed or [
                (k,) for k in first_args])
        return self._done([(first_name, standing, None)], refused)

    def _check(self, name: str, args: dict[str, Any]) -> checks.CheckedCall:
        """535's stack on a template call, then (603) the page's rules on a shape's or the free
        answer's arguments: a part that fails one goes, with its reason, as a dropped sentence
        does. A list's numbers are no figures to the stack (591), and come back after it."""
        shaped = name in shapes.TEXT or name == shapes.FREE
        said = checks.arrived(args)
        if shaped:
            args = {k: [shapes.unnumbered(str(x)) for x in checks.as_list(v)]
                    if isinstance(v, list) else shapes.unnumbered(v) if isinstance(v, str) else v
                    for k, v in checks.arrived(args).items()}
        if self._link(name) and self.drawn is None:  # 632: what the drawn graph covers
            self.drawn = drawn(self.folder, self.brief.focus)
        shown = (self.drawn or []) if self._link(name) else []
        checked = checks.check_call(name, args, self.room, self.must_cover, self.brief.lists, shown)
        if shaped:
            checked.args = {k: [shapes.numbered(str(x)) for x in v] if isinstance(v, list)
                            else shapes.numbered(v) if isinstance(v, str) else v
                            for k, v in checked.args.items()}
            failed = shapes.judge(name, said, self.folder, self._before(name),
                                  self.brief.focus)
            shapes.apply(checked, _briefing_first(
                failed, str(checked.args.get("answer") or ""), self.folder)
                if name == "briefing" else failed, said)
            if stale := _stale(name, said, checked.args, self.folder, self.brief.focus):
                shapes.apply(checked, [(("answer",), stale)], said)
        if why := _verdict_off(self.brief.verdict, name, said):
            shapes.apply(checked, [why], said)
        return checked

    def _no_row(self, said: str) -> bool:
        """719: no caller here since the move; test_t700's ruling 1 holds the rule through it."""
        return _names_no_row(self.brief.verdict, said)

    def _before(self, name: str) -> list[str]:
        """603 (rule 11): the first lines of the answers of this kind before this one, on the
        turn's activity."""
        return [str(a["arguments"].get("answer") or "") for a in self.state.shown
                if self.brief.focus and a.get("focus") == self.brief.focus
                and a["template"] == name]

    def _chart(self, args: dict[str, Any], last: bool) -> Turn | None:
        """538: the chart call over the last chart's arguments, checked against the room's data
        (sent back once, then what passed: 606), drawn by code; no activity and no chart before is
        code's ask, and nothing is drawn."""
        chart = last_chart(self.folder, self.state)
        before = (chart or {}).get("arguments") or {}
        said = {k: args[k] for k in CHART_ARGS if k in args}
        merged = {"activities": None, "classes": None, "years": kept.YEARS, **before, **said}
        if not merged["activities"]:  # 603: the turn's focus, else the which-activity ask
            if self.brief.focus is None:
                return self._asking()
            merged["activities"] = [self.brief.focus]
        shown_last = self.state.shown[-1]["template"] if self.state.shown else \
            CHART if chart else None
        method = walk._read_json(self.folder / walk.METHOD)
        if shapes.drawn_unasked(self.line, shown_last, chart is not None,  # 603, rule 10
                                core.method_lenses(method)):
            return self._back("the chart", shapes.UNASKED, last, shapes.UNASKED_BACK.format(
                name=CHART, why=shapes.UNASKED))
        merged, why = chart_args(self.folder, merged, method)
        if why:
            return self._back("the chart", why, last, CHART_BACK.format(name=CHART, why=why))
        drawn = [core.activity_charts(self.folder, a, method, merged["classes"], merged["years"])
                 for a in merged["activities"]]
        n = 1 + sum(a["template"] == CHART for a in self.state.shown)
        cards = chart_cards(self.folder, merged, before, method)
        turn = self._turn("\n\n".join(cards), MODEL_LED, CHART, merged, [], [],
                          [{"id": f"a{len(self.state.shown) + 1}", "template": CHART,
                            "arguments": merged, "version": n}])
        turn.charts, turn.phones = [w for w, _ in drawn], [p for _, p in drawn]
        turn.cards = cards
        return turn

    def _back(self, what: str, why: str, last: bool, says: str,
              passed: dict[str, Any] | None = None) -> None | Turn:
        """538: a tool call off the room's data, sent back once (None: ask again) where the turn
        has not had its retry (606); then what passed, else the plain line, the reason its drop.
        630: the parts of it that `passed`, which its retry keeps where it leaves them out."""
        if last or self.retried:
            return self._plain([{"text": what, "reason": why}])
        self.retried, self.passed = True, passed or {}
        self.sent_back.append({"kind": "checks", "said": why})
        self.messages.append({"role": "user", "content": says})
        return None

    def _again(self, template: str, same: Callable[[dict[str, Any]], bool]
               ) -> dict[str, Any] | None:
        """The artefact of `template` this conversation showed last, where `same` holds for it:
        the one a follow-up changes."""
        return next((a for a in reversed(self.state.shown)
                     if a["template"] == template and same(a)), None)

    def _draft_for(self, said: dict[str, Any]) -> dict[str, Any] | None:
        """651: the draft a letter call changes: the last to someone it names, or the last where
        it names no one, unless it has a body and the call before went back for naming someone else
        (696)."""
        named = _said_to(said)
        if self.to_failed and not named and not _blank(said.get("body")):
            return None
        return self._again(LETTER, lambda a: not named or bool(named & _said_to(a["arguments"])))

    def _artefact(self, template: str, args: dict[str, Any], before: dict[str, Any] | None,
                  nth: int = 1) -> dict[str, Any]:
        """A new version of `before` (its id kept), else the turn's `nth` new artefact."""
        if before is not None:
            return {"id": before["id"], "template": template, "arguments": args,
                    "version": before["version"] + 1}
        return {"id": f"a{len(self.state.shown) + nth}", "template": template, "arguments": args,
                "version": 1}

    def _letter(self, args: dict[str, Any], last: bool) -> Turn | None:
        """539: the letter call over the last draft's arguments, its recipients checked against
        the organisation file and no address in it (sent back once, then what passed: 606), the
        subject and body through the stack (a sentence lost is sent back once, then what passed,
        never a remnant: 589); one draft per function in code's frame, with the tap that
        places them. The same draft while not placed, a new one once it is. 630: a retry leaving
        out a part of the first try that passed keeps it; one that failed is never carried over.
        696: only the draft of the person it names is merged under it, so no body is lent."""
        if self._again(LETTER, lambda a: True) is None and shapes.asks_briefing(self.line):  # 603
            return self._back("the letter", shapes.BRIEFING_BACK, last, shapes.BRIEFING_BACK)
        if self.held.lost:  # 756: this is the retry of those sent back, each its own parts
            return self._letters([{**self.passed, **c} if _keeps_parts(c, self.passed) else c
                                  for c in (args, *self.later)], last)
        whole = {**self.passed, **args} if _keeps_parts(args, self.passed) else args
        if self.later or len(_said_to(whole)) > 1 \
                or any(f["text"] == LETTER for f in self.failed):  # 651: a call failed beside it
            return self._letters([whole, *self.later], last)
        said = {k: whole[k] for k in LETTER_ARGS if k in whole}
        before = self._draft_for(said)
        merged, why = letter_args(self.folder, {**(before or {}).get("arguments", {}), **said})
        held = "" if why else not_holders(self.folder, merged, self.read)
        if why := why or held:  # 630: a recipient its holders fail is `to`'s failure
            failed = ["to"] if held else letter_failed(self.folder, said)
            newest = self._again(LETTER, lambda a: True) or {"arguments": {}}
            self.to_failed = "to" in failed and _new_to(said, [newest["arguments"]])
            return self._back("the letter", why, last, self._told(LETTER_BACK, why, said, failed),
                              checks.passed(said, failed))
        checked = self._letter_checked(merged)
        merged = {**merged, **checked.args, "body": shapes.numbered(checked.args["body"])}
        drops = [*checked.drops, *({"text": "the letter", "reason": r} for r in checked.refused)]
        if checked.drops and not (last or self.retried):
            why = "; ".join(f"{d['text']!r}: {d['reason']}" for d in checked.drops)
            return self._back("the letter", why, last,
                              self._told(LETTER_FACT_BACK, why, said),
                              checks.passed(said, (str(at[0]) for at in checked.failed)))
        if drops or not merged["subject"] or not merged["body"]:
            return self._plain(drops, checked.must_cover_misses)
        if before is not None and kept.all_placed(self.folder, letter_key(before["arguments"])):
            before = None  # 539: placed, so a change is a new draft and the old one stays
        text = letter_text(self.folder, merged)
        self.said = core.no_list_escape(text)  # 747: the history, never the escape to copy
        return self._turn(text, MODEL_LED, LETTER, merged, drops,
                          checked.must_cover_misses, [self._artefact(LETTER, merged, before)],
                          [(core.PUT_DRAFTS_TAP, {"kind": PUT_LETTER, "letter": merged})])

    def _owes_its_own(self, said: dict[str, Any], failed: Iterable[str] = ()) -> bool:
        """696: a call whose person has no draft while another's is in hand; a name the fault lies
        in (`failed`) may yet be someone with one."""
        return "to" not in failed and self._draft_for(said) is None \
            and self._again(LETTER, lambda a: True) is not None

    def _told(self, back: str, why: str, said: dict[str, Any], failed: Iterable[str] = ()) -> str:
        """A letter's send-back, promising no keeping where the call `_owes_its_own`."""
        says = back.format(name=LETTER, why=why)
        return says.replace(KEEPS_LAST, NO_DRAFT_YET) if self._owes_its_own(said, failed) else says

    def _letter_checked(self, merged: dict[str, Any]) -> checks.CheckedCall:
        """A letter through the stack. 591: a list's numbers are no figures, and a date the room
        holds stands as cited."""
        self.room.ran = [LETTER]
        set_dates = [f"{d.day} {d:%b %Y}" for a in self.state.shown if a["template"] == INVITATION
                     for d in [date.fromisoformat(a["arguments"]["date"])]]
        room = dataclasses.replace(self.room, known=self.room.known | shapes.held_dates(
            self.folder, [*self.state.lines, self.line], set_dates))
        return checks.check_call(LETTER, {**merged, "body": shapes.unnumbered(merged["body"])},
                                 room, self.must_cover, self.brief.lists)

    def _letters(self, calls: list[dict[str, Any]], last: bool) -> Turn | None:
        """651: a reply's several letter calls, each its own letter, over the draft it changes if
        any. One that fails is dropped with its reason (a remnant never: 589) and the others stand,
        one tap placing them all; where none stands, sent back once, then the plain line. 756: one
        to several people, or with the body of one that stood, fails; one lost beside others is
        sent back once, alone, and those that stood are held, whatever the retry comes to."""
        stood, shown, misses = [*self.held.stood], [*self.held.shown], [*self.held.misses]
        drops = [f for f in self.failed if f["text"] == LETTER]
        lost = [*self.unwritten, *({} for f in drops if f["reason"] == BAD_JSON)]
        for said in calls:
            one = self._one_of_letters(said, stood)
            if one is None:  # a second try at those with a draft already (602)
                continue
            merged, before, cut, missed = one
            if cut:
                drops += cut
                lost.append(said)
                continue
            stood.append(merged)
            misses.append(missed)
            if before is not None and kept.all_placed(self.folder,
                                                      letter_key(before["arguments"])):
                before = None  # 539: placed, so a change is a new draft and the old one stays
            shown.append(self._artefact(LETTER, merged, before, len(stood)))
        missed = [m for m in (misses or [[]])[0] if all(m in x for x in misses)]
        lost, drops = self._after_retry(stood, lost, drops)
        note = letters_left(self.folder, lost, stood)
        if not (last or self.retried) and (note or not stood):
            self.held = _Held(stood, shown, misses, lost, drops)
            return self._letters_back(stood, lost, drops, note)
        if not stood:
            return self._plain(drops)
        args = stood[0] if len(stood) == 1 else {"to": _recipients(stood), "letters": stood}
        text = letter_text(self.folder, args) + (f"\n\n{note}" if note else "")
        self.said = core.no_list_escape(text)  # 747: the history, never the escape to copy
        return self._turn(text, MODEL_LED, LETTER, args, drops, missed, shown,
                          [(core.PUT_DRAFTS_TAP, {"kind": PUT_LETTER, "letter": args})])

    def _one_of_letters(self, said: dict[str, Any], stood: list[dict[str, Any]]) -> tuple[
            dict[str, Any], dict[str, Any] | None, list[dict[str, str]], list[str]] | None:
        """651: one call of a reply's: (its letter, the draft it changes, why it failed, what it
        missed), None where it is a second try at someone who stood. 756: a retry naming no one
        never lands on a draft of an earlier turn, to someone else."""
        if _said_to(said) and _said_to(said) <= _said_to(*stood):
            return None
        before = None if self.held.lost and not _said_to(said) else self._draft_for(said)
        merged, why = letter_args(self.folder, {**(before or {}).get("arguments", {}), **{
            k: said[k] for k in LETTER_ARGS if k in said}})
        if not why and len(_said_to(said)) > 1:
            why = LETTER_SEVERAL
        if not why:
            merged["to"] = [f for f in merged["to"] if f not in _recipients(stood)]
            if not merged["to"]:
                return None
            why = not_holders(self.folder, merged, self.read)
        if why:
            return merged, before, [{"text": "the letter", "reason": why}], []
        checked = self._letter_checked(merged)
        merged = {**merged, **checked.args, "body": shapes.numbered(checked.args["body"])}
        cut = [*checked.drops, *({"text": "the letter", "reason": r} for r in checked.refused)]
        if not cut and not (merged["subject"] and merged["body"]):
            cut = [{"text": "the letter", "reason": LETTER_EMPTY.format(what="subject or body")}]
        if not cut and (twin := next((a for a in stood if _same_body(a, merged)), None)):
            cut = [{"text": "the letter", "reason": LETTER_SAME_BODY.format(other=twin["to"][0])}]
        return merged, before, cut, checked.must_cover_misses

    def _letters_back(self, stood: list[dict[str, Any]], lost: list[dict[str, Any]],
                      drops: list[dict[str, str]], note: str) -> Turn | None:
        """756: the reply's one send-back: what stood stays and what is lost goes back; where none
        stood, the letter as a whole (651)."""
        passed = _parts_kept(self.folder, lost) if stood else {}
        self.failed, self.unwritten = [], []
        if not stood:
            why = "; ".join(d["reason"] for d in drops)
            own = any(self._owes_its_own(c, letter_failed(self.folder, c)) for c in lost)
            back = LETTER_SEVERAL_BACK if LETTER_SEVERAL in why or own else LETTER_BACK
            return self._back("the letter", why, False, back.format(name=LETTER, why=why))
        why = "; ".join(d["reason"] if d["text"] in (LETTER, "the letter")
                        else f"{d['text']!r}: {d['reason']}" for d in drops)
        return self._back("the letter", why, False, LETTER_LEFT_BACK.format(
            name=LETTER, stood=" and the ".join(_recipients(stood)), note=note, why=why), passed)

    def _after_retry(self, stood: list[dict[str, Any]], lost: list[dict[str, Any]],
                     drops: list[dict[str, str]]
                     ) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        """756: what is lost once a retry has come back, or not: those the send-back named, less
        each one a new letter made good, and any the retry lost to someone else it could name. A
        retry's unnamed failure is one of those sent back, counted, where one is still owed."""
        if not self.held.lost:
            return lost, drops
        held = {f.lower() for f in words.functions(self.folder)}
        named = [c for c in self.held.lost if _said_to(c) & held]
        unnamed = [c for c in self.held.lost if not _said_to(c) & held]
        new = [a for a in stood[len(self.held.stood):] if not _said_to(a) & _said_to(*named)]
        owed = [c for c in named if _said_to(c) - _said_to(*stood)] + unnamed[len(new):]
        more = [c for c in lost if not _said_to(c) & held][len(owed):]  # beyond those sent back
        left = [*named, *unnamed[len(new):], *more, *(c for c in lost if _said_to(c) & held)]
        untried = letters_left(self.folder, [c for c in left if not _said_to(c) & _said_to(*lost)],
                               stood)  # the retry's own failure speaks for those it tried again
        return left, [*drops, *(d for d in self.held.drops if untried and d not in drops)]

    def _invitation(self, args: dict[str, Any], last: bool) -> Turn | None:
        """540: the invitation call over the last invitation's arguments (this conversation's,
        else the activity's slot the room keeps or plans), checked (sent back once, then what
        passed: 606); code's card with the weekday it computes, and the tap that moves it. The same
        artefact on a move."""
        if core.WHO_WORDS.search(self.line) and not any(  # 605 (B3): a question about people
                b["said"] == INVITE_UNASKED for b in self.sent_back):
            return self._back("the invitation", INVITE_UNASKED, last, shapes.UNASKED_BACK.format(
                name=INVITATION, why=INVITE_UNASKED))
        said = {k: args[k] for k in INVITE_ARGS if k in args}
        before = self._again(INVITATION, lambda a: said.get("activity") in (
            None, a["arguments"]["activity"]))
        merged = {"activity": self.brief.focus, **(before or {}).get("arguments", {}), **said}
        activity = _one_activity(self.folder, merged["activity"])
        hour = (before or {}).get("arguments", {}).get("time")  # 588 (I2): the conversation's
        was, now, why = invite_args(self.folder, activity, merged, self.line, hour) \
            if activity else (None, None, INVITE_OFF.format(value=merged["activity"]))
        why = why or (weekday_off(self.folder, self.line, now[0].date()) if now else "")
        if why or was is None or now is None:
            return self._back("the invitation", why, last, INVITE_BACK.format(name=INVITATION,
                                                                              why=why))
        merged = {**merged, "activity": activity, **_day(now)}
        before = self._again(INVITATION, lambda a: a["arguments"]["activity"] == merged["activity"])
        text = (INVITE_CARD if was == now else INVITE_MOVE).format(
            activity=core.map_name(self.folder, merged["activity"]), when=_when(now, weekday=True),
            was=_when(was))
        return self._turn(text, MODEL_LED, INVITATION, merged, [], [],
                          [self._artefact(INVITATION, merged, before)],
                          [(MOVE_TAP, {"kind": MOVE_INVITE, "activity": merged["activity"],
                                       "slot": [t.isoformat() for t in now]})])

    def _send_back(self, name: str, args: dict[str, Any], checked: checks.CheckedCall) -> None:
        self.retried = True
        failed = [f'- "{d["text"]}": {d["reason"]}' for d in checked.drops] + [
            f"- {r}" for r in checked.refused]
        self.sent_back.append({"kind": "checks", "said": "\n".join(failed)})
        self.messages.append({"role": "user", "content": SEND_BACK.format(
            name=name, failed="\n".join(failed), frozen=json.dumps(args, ensure_ascii=False))})

    def _link(self, name: str) -> str:
        """The graph's link where the answer `name` draws it (`graph_link`, 603's dependencies
        shape), "" where it draws none or no graph is drawn; code draws it once a turn."""
        if not (name == "graph_link" or shapes.BY_NAME.get(name, shapes.SHAPES[0]).link
                and name in shapes.TEXT):
            return ""
        if self.link is None:  # 647: the chat page's mark (t643), so "← Chat" closes the tab
            self.link = (graph + FROM_CHAT) if (graph := self.graph(self.brief.focus)) else ""
        return self.link

    def _done(self, tries: list[Try], drops: list[dict[str, str]],
              misses: list[str] | None = None) -> Turn:
        """719: the first of `tries` that reads; the plain line only where none can (606)."""
        for name, args, checked in tries:
            checked = checked or self._check(name, args)
            drops = [*drops, *checked.drops, *({"text": "the answer", "reason": r}
                                               for r in checked.refused)]
            misses = checked.must_cover_misses
            # 536 (544 r2): the pointer line closes the answer, only the demo mark under it (720)
            reads = what_he_reads(name, checked, self.brief, self._link(name),
                                  core.others_said(self.folder, self.brief.day_interviews)
                                  if self.brief.day_interviews else "",
                                  checks.marked_call(name, checked.args, self.room))
            if reads is None:
                continue
            root = self.graph(None).rpartition("/")[0] if name == "briefing" \
                or checks.CITE.search(checks.each_cite(reads[0])) else ""
            # 602: the model's history keeps each [path:line]; 720: not the mark, or it copies it
            self.said = "\n\n".join(r for r in reads if r != checks.DEMO_MARK.strip())
            shown = {"id": f"a{len(self.state.shown) + 1}", "template": name,
                     "arguments": checked.args,
                     "version": 1 + sum(a["template"] == name for a in self.state.shown)}
            # 757: a briefing with its PDF opens on the link; its text stays in `said`
            pdf = self._briefing_pdf(name, root, reads[0])
            return self._turn("\n\n".join(filter(None, [
                *([*pdf, BESIDE_PDF] if pdf else
                  [cited(reads[0], self.folder, root, self.read, name != "briefing")]),
                *reads[1:]])),
                              MODEL_LED, name, checked.args, drops,
                              misses, [shown], shapes.taps(checked.args))  # 603 (rule 8)
        return self._turn(PLAIN_LINE, PLAIN, None, {}, drops, misses or [],
                          [], [(str(label), dict(action)) for label, action in self.next_taps()])

    def _briefing_pdf(self, name: str, root: str, said: str) -> list[str]:
        """721 (627): under the briefing shape alone, 405's route for this room and its activity, in
        `BRIEFING_PDF`'s words where the print can run: the one row of the map his line names, by a
        whole name, the day's owner or a head word; else the first the lead he reads names, among
        those his line names where it names several; else the focus, else the answer. Only a row:
        nothing else has a PDF. Code's, so never in the model's history."""
        if name != "briefing" or not root:
            return []
        import briefing  # t405: it imports PROTOTYPE_core, so not at the top
        rows = core.process_map_rows(self.folder)
        slugs = {r.slug for r in rows}

        def spelled(words: str) -> str:  # its words, whatever joins them, as `core.named_in` reads
            return r"\W+".join(re.findall(r"\w+", words))

        def named(text: str) -> list[str]:
            bare = checks._uncited(checks.each_cite(text))
            where = {r.slug: (m.start(), -m.end()) for r in rows if (m := re.search(
                rf"(?<!\w)(?:{spelled(r.name)}|{spelled(r.slug)})(?!\w)", bare, re.I))}
            return sorted(where, key=where.__getitem__)  # as he reads them, the longer name first
        his = named(self.line) or [a for a in _day_owner(self.folder, self.line)
                                   or core.named_loosely(self.folder, self.line) if a in slugs]
        lead = [a for a in named(said.split("\n\n")[0]) if not his or a in his][:1]
        focus = [f for f in [self.brief.focus] if f in slugs]
        about = next((n[0] for n in (his, lead, focus, named(said)) if len(n) == 1), None)
        return [core.BRIEFING_PDF.format(link=f"{root}/briefing/{about}.pdf")] \
            if about and briefing.chrome() else []

    def _plain(self, drops: list[dict[str, str]], misses: list[str] | None = None) -> Turn:
        """606, 646: first what is in hand: the try sent back, the call with no first line."""
        if self.held.stood:  # 756: never a plain line while one letter stands
            return cast(Turn, self._letters([], True))
        return self._done([x for x in (self.first, self.part) if x], drops, misses)

    def _turn(self, text: str, path: str, template: str | None, args: dict[str, Any],
              drops: list[dict[str, str]], misses: list[str], shown: list[dict[str, Any]],
              taps: list[tuple[str, dict[str, Any]]] | None = None) -> Turn:
        # 755: the last call's no-text lines, so a retry's are not counted twice
        drops = [*drops, *next(filter(None, (
            checks.no_text_drops(_args(c.get("function") or {}) or {})
            for c in reversed(self.calls))), [])]
        return Turn(text, path, template, args, self.calls, shown, drops, misses, self.sent_back,
                    round(time.time() - self.t0, 2), self.model_s, self.tool_s, taps or [],
                    ended=self.ended)


def _verdict_off(v: dict[str, Any] | None, name: str, said: dict[str, Any]
                 ) -> tuple[shapes.Place, str] | None:
    """604: an answer opening with the opposite of code's yes or no for his line (`verdict`)."""
    key = "verdict" if name == "judgement" else "answer"
    first = checks.CITE.sub("", str(said.get(key) or ""))
    if v is None or not (m := OPENS[not v["verdict"]].match(first)):
        return None
    return (key,), _verdict_said(v, VERDICT_OFF, said=m[0].strip())


def _names_no_row(v: dict[str, Any] | None, said: str) -> bool:
    """700: an opening on code's yes names one of the rows behind that yes: with no "Yes" in it,
    anything else can deny the answer in other words."""
    words = shapes._bare(said)
    return bool(v and v["verdict"] and not any(
        re.search(rf"(?<!\w){re.escape(r)}(?!\w)", words, re.I) for r in v["rows"]))


def what_he_reads(name: str, checked: checks.CheckedCall, known: Brief, link: str = "",
                  pointer: str = "", marked: bool = False) -> list[str] | None:
    """719 (ADR-0061 d3): a checked answer as he reads it, cites as written: the answer, the notes,
    the day's `pointer`, then (720) the demo mark once where a fact that stands is `marked`; None
    where it cannot stand. Pure: no model, no file, no room state."""
    shaped = name in shapes.TEXT or name == shapes.FREE
    # 700: a first line cut or never come: the body's first prose opens what he reads
    args = _opened(checked.args, lambda said: _verdict_off(known.verdict, name, {"answer": said})
                   or _names_no_row(known.verdict, said)) if shaped else checked.args
    # 754: after the check, so no check runs differently and the record keeps the call as it came
    text = shapes.without_stray_bars(
        render(name, args, GRAPH_LINK.format(link=link) if link else "")).strip()
    # 603: no first line. 677: no item under its heading. 602: a list he asked for left out whole
    if not text or shaped and not shapes.without_stray_bars(str(args.get("answer") or "")).strip() \
            or _no_items(name, checked.args) \
            or any(set(items) <= set(checked.must_cover_misses) for items in known.lists.values()):
        return None
    notes = [MISSING.format(items=", ".join(left), what=what) for what, items in known.lists.items()
             if (left := [i for i in items if i in checked.must_cover_misses])]
    return [text, *notes, *filter(None, [pointer]), *checks.mark_line(text, marked)]


def _opened(args: dict[str, Any], off: Callable[[str], Any]) -> dict[str, Any]:
    """700 (ADR-0061 d3): code writes no first line. Where none stands, the body's first point that
    is prose moves up whole and unchanged (never cut at a stop: "Co. KG" has one): one line, three
    words or more, a stop at its end, no `NOT_OPENING`, no label short of `LABEL_OPENS_AT`, not
    right under a lone label (it heads that point), no preamble, not against code's yes or no
    (`off`). The arguments as they were where a first line stands or no point is prose."""
    if shapes.without_stray_bars(str(args.get("answer") or "")).strip():  # 754: a bar is no line
        return args
    details, above = checks.as_list(args.get("details")), ""
    for i, item in enumerate(details):
        said = str(item).strip()
        words = checks._uncited(checks.each_cite(said)).strip()  # a cite is no word
        bare = words.rstrip("\"'\u201c\u201d\u2019)*_")  # a stop inside a quote or bold is a stop
        label = LABELLED.match(bare)
        if bare.endswith(".") and "\n" not in said and len(bare.split()) > 2 \
                and not (label and len(bare[label.end():].split()) < LABEL_OPENS_AT) \
                and not LONE_LABEL.fullmatch(above) \
                and not (NOT_OPENING.match(bare) or shapes.PREAMBLE.match(bare) or off(said)):
            return {**args, "answer": said, "details": [*details[:i], *details[i + 1:]]}
        above = words or above
    return args


def _briefing_first(failed: list[tuple[shapes.Place, str]], first: str, folder: Path
                    ) -> list[tuple[shapes.Place, str]]:
    """679: a briefing's first line by what it gives, never by its form (`Shape.opens`, the length
    `answer_shapes._first` reads): both stand, one is a note on the other (640 (a)), neither goes.
    `first` is the line after the check's cuts, as he reads it. A line the check cut whole, or
    already refused for another reason, needs no second reason."""
    place: shapes.Place = ("answer",)
    shape, bare = shapes.BY_NAME["briefing"], shapes._bare(first).strip()
    opens = shapes.OPENS.format(first="{}", kind=shape.kind.lower()).format
    others = [x for x in failed if x != (place, opens(shape.first))]
    if not bare or any(at == place and not shapes.noted(why) for at, why in others):
        return others
    title = bool(BRIEFING_TITLE.match(bare) or core.named_in(folder, bare))
    why_now = bool(BRIEFING_WHY_NOW.search(bare))
    said = [] if title and why_now else [(place, BRIEFING_NEITHER if not title and not why_now
                                          else opens("why now" if title else "the title"))]
    return [*said, *others]


def _stale(name: str, said: dict[str, Any], kept: dict[str, Any], folder: Path,
           activity: str | None) -> str | None:
    """658 (4): a first line whose count matched the points under it and no longer matches the
    points a drop left: its reason (`shapes.LISTED_OFF`), so it is dropped, never re-counted. 738: a
    true mismatch count was never the points' (`shapes.true_mismatches`)."""
    lead = checks.LISTED.sub(lambda m: f"{shapes._n(m[1])} {m[2]}",
                             shapes._bare(str(kept.get("answer") or "")), count=1)
    was, left = (checks.as_list(a.get("details")) for a in (said, kept))
    shape, m = shapes.BY_NAME.get(name), checks.LISTED.search(lead)
    if not m or len(left) == len(was) or shapes._listed(shape, lead, was) \
            or shapes.true_mismatches(lead, folder, activity):
        return None
    return shapes._listed(shape, lead, left) if left else shapes.LISTED_OFF.format(
        said=f"{m[1]} {m[2]}", listed=0)


def _one_activity(folder: Path, said: Any) -> str | None:
    """The one room activity a call names, by its id or its name; None where it names none or
    several."""
    named = [said] if said in walk.processes(folder) else core.named_in(folder, str(said or ""))
    return named[0] if len(named) == 1 else None


def chart_args(folder: Path, args: dict[str, Any], method: dict[str, Any]
               ) -> tuple[dict[str, Any], str]:
    """538: a chart call's arguments as the room holds them (each activity by its id, the classes
    and years in the method's order, every class where none is named) and why it fails, "" where
    it does not: an activity, class or year the room does not hold, or an activity with nothing
    to draw."""
    order = core.method_lenses(method)
    activities = []
    for a in args["activities"]:
        if (one := _one_activity(folder, a)) is None:
            return args, CHART_OFF.format(what="the activity", value=a)
        activities.append(one)
    classes, years = args["classes"] or None, args["years"] or kept.YEARS
    for what, given, held in (("the class", classes or [], order), ("the year", years, kept.YEARS)):
        if off := [x for x in given if x not in held]:
            return args, CHART_OFF.format(what=what, value=off[0])
    activities = list(dict.fromkeys(activities))
    classes = [c for c in order if c in classes] if classes else None
    years = [y for y in kept.YEARS if y in years]
    for a in activities:
        if not core.activity_charts(folder, a, method, classes, years)[0]:
            return args, CHART_EMPTY.format(activity=core.map_name(folder, a))
    return {"activities": activities, "classes": classes, "years": years}, ""


def _under(folder: Path, activity: str, args: dict[str, Any], method: dict[str, Any]) -> str:
    """588: the line under an activity's title, as the brake card says it: `core.CHART_UNDER`
    where this year's scores are drawn beside last year's, `core.no_scores_line` where the activity
    has none this year (F1), and a line that fits one year drawn alone (F2)."""
    if not core.this_years_scores(folder, activity, method)[0]:
        return core.no_scores_line(folder, activity)
    count = len(args["classes"] or core.method_lenses(method))
    said = {("this",): CHART_THIS_ALONE, ("last",): CHART_LAST_ALONE}.get(
        tuple(args["years"]), core.CHART_UNDER)
    return core.under_with_year(core.chart_under(said, count), folder, activity)


def chart_cards(folder: Path, args: dict[str, Any], before: dict[str, Any],
                method: dict[str, Any]) -> list[str]:
    """538: code's cards over the charts, one per activity so each title sits over its own chart
    (588): the title, the brake's line under it (`_under`) and its euro line (`core.euro_said`,
    F3); the last card closes on what changed from a chart before (or that it is the same).
    741: no euro line on a chart that leaves Financial out, or of last year alone."""
    changed = [k for k in CHART_ARGS if args[k] != before.get(k)]
    mark = (CHART_CHANGED.format(what=" and ".join(changed)) if changed else CHART_SAME) \
        if before else ""
    euros = args["years"] != ["last"] and (not args["classes"] or core.FINANCIAL in args["classes"])
    cards = ["\n\n".join(filter(None, [core.CHART_TITLE.format(activity=core.map_name(folder, a)),
                                       _under(folder, a, args, method),
                                       core.euro_said(folder, a) if euros else ""]))
             for a in args["activities"]]
    return [*cards[:-1], "\n\n".join(filter(None, [cards[-1], mark]))]


# ── 539: the letter ─────────────────────────────────────────────────────────────────────────────
def _said_function(x: Any) -> str:
    return re.sub(r"^the\s+", "", str(x).strip(), flags=re.I).lower()


def _said_to(*calls: dict[str, Any]) -> set[str]:
    return {_said_function(x) for a in calls for x in checks.as_list(a.get("to"),
                                                                     checks.SPLITS["to"])}


def _new_to(args: dict[str, Any], earlier: list[dict[str, Any]]) -> bool:
    """651: a later letter call is a letter of its own where it names someone the reply's earlier
    calls do not; to the same people or to no one it is a second try (602)."""
    return bool(_said_to(args) - _said_to(*earlier))


def _same_body(one: dict[str, Any], other: dict[str, Any]) -> bool:
    """756: two checked bodies, their cites already out, with case and white space aside."""
    return " ".join(one["body"].casefold().split()) == " ".join(other["body"].casefold().split())


def _parts_kept(folder: Path, lost: list[dict[str, Any]]) -> dict[str, Any]:
    """756: what a retry of the one letter sent back may leave out, those that passed (630); of a
    call to several, nothing."""
    if len(lost) != 1 or len(_said_to(lost[0])) != 1:
        return {}
    said = {k: v for k, v in lost[0].items() if k in LETTER_ARGS and not _blank(v)}
    return checks.passed(said, letter_failed(folder, said))


def _keeps_parts(call: dict[str, Any], passed: dict[str, Any]) -> bool:
    """756: a retry's call takes the parts kept where it is to the one they were written for, or
    they name no one the organisation file holds."""
    return not _said_to(passed) or _said_to(call) <= _said_to(passed)


def letters_left(folder: Path, lost: list[dict[str, Any]], stood: list[dict[str, Any]]) -> str:
    """651 (23's amend): the line under the drafts for the `lost` calls: those it can name by the
    organisation file, each other call counted, and none for someone with a draft after all."""
    functions = words.functions(folder)
    held, has = {f.lower() for f in functions}, {f.lower() for f in _recipients(stood)}
    named: set[str] = set()
    others = 0
    for call in lost:
        said = _said_to(call)
        no_draft = (said & held) - has
        named |= no_draft
        others += not no_draft and (not said or bool(said - held))
    who = " and the ".join(f for f in functions if f.lower() in named)
    if who and others:
        more = "one more letter is" if others == 1 else f"{others} more letters are"
        return LETTER_LEFT_MORE.format(who=who, more=more)
    if who:
        return LETTER_LEFT.format(who=who, those="that letter" if len(named) == 1
                                  else "those letters")
    return LETTER_LEFT_ONE if others == 1 else \
        LETTER_LEFT_SOME.format(n=others) if others else ""


def letter_args(folder: Path, args: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """539: a letter call's arguments as code takes them (each recipient the function as the
    organisation file spells it, once) and why it fails, "" where it does not: an address anywhere
    in it, no recipient, one the file does not name, or no subject or body."""
    if ADDRESS.search(json.dumps(args, ensure_ascii=False)):
        return args, LETTER_ADDRESS
    held = {f.lower(): f for f in words.functions(folder)}
    named = []
    for x in checks.as_list(args.get("to"), checks.SPLITS["to"]):
        function = held.get(_said_function(x))
        if function is None:
            return args, LETTER_NOT_A_FUNCTION.format(value=x)
        named.append(function)
    body, why = first_names(FAREWELL.sub("", GREETING.sub("", str(args.get("body") or ""))),
                            folder)
    out = {"to": list(dict.fromkeys(named)), "subject": str(args.get("subject") or "").strip(),
           "body": body.strip()}
    missing = [k for k, v in out.items() if not v]
    return out, why or (LETTER_EMPTY.format(what=" or ".join(missing)) if missing else "")


def letter_failed(folder: Path, args: dict[str, Any]) -> list[str]:
    """630: the parts of a letter call `letter_args` fails on their own (an address in one, a
    recipient the organisation file does not name, a first name two people share), not counting
    the parts it lacks."""
    out = []
    for k, v in args.items():
        alone, why = letter_args(folder, {k: v})
        if why != LETTER_EMPTY.format(what=" or ".join(m for m, x in alone.items() if not x)):
            out.append(k)
    return out


def first_names(text: str, folder: Path) -> tuple[str, str]:
    """588 (L3): `text` with each bare first name of the organisation file said as its holder's
    function ("Petra" is the Head of Production), and why it fails, "" where it does not: a first
    name two people share. A full name is `words.functions_only`'s; "Jan" in a date is no one."""
    by: dict[str, list[str]] = {}
    for person, function in words.people(folder).items():
        by.setdefault(person.split()[0], []).append(function)
    for name, functions in by.items():
        bare = re.compile(rf"(?<!\d )\b{re.escape(name)}\b(?!\s+(?:\d|[A-ZÄÖÜ]))")
        if bare.search(text):
            if len(functions) > 1:
                return text, LETTER_FIRST_NAME.format(value=name, n=len(functions))
            text = bare.sub(f"the {functions[0]}", text)
    return text, ""


def not_holders(folder: Path, args: dict[str, Any], read: checks.Read) -> str:
    """588 (L2): why a letter's recipients fail, "" where they do not: one who is not among the
    functions the lines its body cites name (a speaker, an owner), the BCM Officer, its sender,
    aside. A body citing no holder holds no one to it."""
    functions = words.functions(folder)
    holders = []
    for path, n in checks.cites(args["body"], read):
        said = words.functions_only(" ".join([read.get((path, n), ""), *(
            v for _, v, _ in checks.evidence(folder, path, n))]), folder)
        holders += [f for f in functions if re.search(rf"\b{re.escape(f)}\b", said)]
    holders = [f for f in dict.fromkeys(holders) if f != core.bcm_officer(folder)]
    off = [f for f in args["to"] if holders and f not in holders]
    return LETTER_NOT_HOLDER.format(value=off[0], holders=" or the ".join(holders)) if off else ""


def letter_key(args: dict[str, Any]) -> str:
    """539: which letter the room keeps placed or not (`shown.keep_drafts`): a digest of it."""
    return kept.digest(LETTER, args)


def _letter_lines(folder: Path, function: str, args: dict[str, Any]) -> list[str]:
    """594: the letter one owner gets: his part of the body alone where it holds a part each."""
    return core.letter(function, shapes.section(args["body"], function, words.functions(folder)),
                       core.bcm_officer(folder))


def _recipients(letters: list[dict[str, Any]]) -> list[str]:
    return [f for a in letters for f in a["to"]]


def _each_draft(args: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """651: (function, its letter) per draft of a tap's letter, which holds `letters` where the
    reply's several calls stood."""
    return [(f, a) for a in args.get("letters") or [args] for f in a["to"]]


def letter_text(folder: Path, args: dict[str, Any]) -> str:
    """539: what he sees: one draft per function, as the A8 drafts show (`core.draft_block`),
    with no address in it; 603: under the drafts kind's first line, and naming who has no address
    in the files."""
    none = shapes.unaddressed(folder, args["to"])
    return "\n\n".join([shapes.drafts_first(len(args["to"]), unchanged=all(
        kept.all_placed(folder, letter_key(a)) for a in args.get("letters") or [args])),
        *(core.draft_block(
        core.DRAFT_TO.format(function=f), a["subject"], _letter_lines(folder, f, a))
        for f, a in _each_draft(args)),
        *([shapes.NO_ADDRESS.format(functions=" and the ".join(none))] if none else [])])


def place(folder: Path, tap: dict[str, Any], now: datetime, *, password: Path | None = None,
          connect: Callable[[], Any] | None = None) -> str:
    """539: his tap: each draft of the letter put once in the mailbox's Drafts, at the mailbox
    code maps its function to (`drafts.function_address`); the room keeps whether it landed, and
    he reads where they are, or that the mailbox is not reachable."""
    args = tap["letter"]
    letters = [a for a in args.get("letters") or [args]
               if not kept.all_placed(folder, letter_key(a))]  # 651: each draft put once
    if not letters:
        return LETTER_ALREADY
    waiting = _each_draft({"letters": letters})
    made = [drafts.letter_draft(f, drafts.function_address(f), a["subject"],
                                _letter_lines(folder, f, a), now) for f, a in waiting]
    landed = drafts.appended(made, now, password=password, connect=connect) == len(made)
    for each in [*letters, *([args] if "letters" in args else [])]:  # 651: each found placed (539)
        kept.keep_drafts(folder, letter_key(each), None,
                         [drafts.function_address(f).partition("@")[0] for f in each["to"]], landed)
    if not landed:
        return LETTER_UNREACHABLE
    return "\n".join([LETTER_LANDED.format(box=drafts.MAILBOX_USER),
                      *(f"- {core.DRAFT_TO.format(function=f)}: {a['subject']}"
                        for f, a in waiting)])


# ── 540: the invitation ─────────────────────────────────────────────────────────────────────────
Slot = tuple[datetime, datetime]


def _when(slot: Slot, weekday: bool = False) -> str:
    start, end = slot
    return f"{f'{start:%A}, ' if weekday else ''}{start.day} {start:%B %Y}, " \
        f"{start:%H:%M}–{end:%H:%M}"


def _day(slot: Slot) -> dict[str, str]:
    return {"date": slot[0].date().isoformat(), "time": f"{slot[0]:%H:%M}"}


def _slot_kept(folder: Path, activity: str) -> Slot | None:
    """The activity's slot as the room keeps it placed (533), else as the programme plan has it."""
    was = kept.last(folder, kept.INVITATION, activity=activity)
    if was:
        start, end = (datetime.fromisoformat(t) for t in was["slot"])
        return start, end
    return core.interview_slot(folder, activity)


def _his_hour(line: str, time_: str) -> bool:
    """The hour `time_` (HH:MM) is one his line names ("14:00", "2 pm", "2 o'clock", 588's "at
    9")."""
    def said(x: re.Match[str]) -> str:
        h = int(x["h"]) % 12 + 12 * x["ap"].lower().startswith("p") if x["ap"] else int(x["h"])
        return f"{h:02d}:{x['m'] or '00'}"
    return any(said(x) == time_.zfill(5) for x in checks.HOUR.finditer(line)) \
        or any(f"{int(h):02d}:00" == time_.zfill(5) for h in checks.AT_HOUR.findall(line))


def invite_args(folder: Path, activity: str, args: dict[str, Any], line: str,
                hour: str | None = None) -> tuple[Slot | None, Slot | None, str]:
    """540: (the slot the activity's invitation had, the one the call asks for) and why the call
    fails, "" where it does not: no interview planned to invite to, a date that is no real day as
    YYYY-MM-DD or lies before the story's today, an hour his line does not name. Its length and,
    where the call names none, its day (588, I3) and its hour are the slot's before; `hour`, the
    last invitation's in this conversation, is kept over the slot's (I2)."""
    was = _slot_kept(folder, activity)
    if was is None:
        return None, None, INVITE_NO_SLOT.format(activity=core.map_name(folder, activity))
    said = str(args.get("date") or f"{was[0]:%Y-%m-%d}")
    kept_hour = hour or f"{was[0]:%H:%M}"
    time_ = str(args.get("time") or kept_hour)
    try:
        day = date.fromisoformat(said) if re.fullmatch(r"\d{4}-\d\d-\d\d", said) else None
    except ValueError:
        day = None
    today = core.story_today(folder)
    if day is None:
        return was, None, INVITE_NOT_A_DAY.format(value=said)
    if today and day < today:
        return was, None, INVITE_PAST.format(value=day, today=today)
    if not re.fullmatch(r"\d\d?:\d\d", time_) or time_ != kept_hour and not _his_hour(line, time_):
        return was, None, INVITE_HOUR.format(value=time_, was=kept_hour)
    h, m = map(int, time_.split(":"))
    start = was[0].replace(year=day.year, month=day.month, day=day.day, hour=h, minute=m)
    return was, (start, start + (was[1] - was[0])), ""


def weekday_off(folder: Path, line: str, day: date) -> str:
    """631: why `day` is not the day of a weekday his line names (`core.weekday_date`, code's
    calendar), "" where it is one, or where his line names a date or no weekday. A past weekday
    ("last Thursday") and one whose thing it names ("Tuesday's interview") name no new day, and
    another week (`OTHER_WEEK`) is his to read, so neither is checked."""
    if NAMED_DATE.search(line) or OTHER_WEEK.search(line):
        return ""
    found = [d for w in calendar.day_name if re.search(rf"(?<!last )\b{w}\b(?!['’]s)", line, re.I)
             and (d := core.weekday_date(folder, w))]
    if not found or day.isoformat() in {d["date"] for d in found}:
        return ""
    return INVITE_WEEKDAY.format(said=" or ".join(d["weekday"] for d in found),
                                 dates=" or ".join(d["date"] for d in found), value=day)


def move(folder: Path, tap: dict[str, Any], now: datetime, *, password: Path | None = None,
         connect: Callable[[], Any] | None = None, calendar: Path | None = None) -> str:
    """540: his tap: the activity's one calendar event moved to the slot (its id kept), and a new
    invitation in Drafts (`drafts.move_invitation`); he reads what moved and landed, and that the
    earlier invitation stays where there was one."""
    start, end = (datetime.fromisoformat(t) for t in tap["slot"])
    had = kept.last(folder, kept.INVITATION, activity=tap["activity"]) is not None
    landed, moved = drafts.move_invitation(folder, tap["activity"], (start, end), now,
                                           password=password, connect=connect, calendar=calendar)
    return " ".join([MOVED.format(when=_when((start, end), weekday=True)) if moved else NOT_MOVED,
                     NEW_INVITE.format(box=drafts.MAILBOX_USER) if landed else NO_NEW_INVITE,
                     *([OLD_INVITE_STAYS] if had and landed else [])])


def _args(fn: dict[str, Any]) -> dict[str, Any] | None:
    """A tool call's arguments; None where GLM broke the JSON (or sent no object)."""
    try:
        args = json.loads(fn.get("arguments") or "{}")
    except ValueError:
        return None
    return args if isinstance(args, dict) else None


def _first_line(turn: Turn) -> str:
    """722: the first line he reads, from the text shown (a first line 700 moved up is in it, and
    not in `turn.args` as one): code's graph link is no line of it, and a link's address no word.
    "" where the model drew no words (what follows the link is code's pointer, a letter opens on
    code's line) and where the line could not open by 700's rule (a row, a short label), so the
    model's order picks none (584 r2)."""
    line = next((x for x in turn.text.split("\n")
                 if x.strip() and not _GRAPH_LINE.fullmatch(x)), "")
    label = LABELLED.match(line)
    if not shapes.without_stray_bars(render(str(turn.template), turn.args)).strip() \
            or NOT_OPENING.match(line) \
            or (label and len(line[label.end():].split()) < LABEL_OPENS_AT):
        return ""
    return _LINK_ADDRESS.sub("]", line)


def _stood_on(run: _Run, turn: Turn) -> list[str]:
    """584 (550's rule on the model-led path): the activities an answer that stood names; none
    where it did not stand. Exactly one is the room's focus from now on where the turn had none of
    its own; several set none (r2: which one leads is the model's ordering, never his). 722: a first
    line naming exactly one stands on that one, whatever the body names. Else read from the answer
    as the template drew it: code's link and pointer line name activities of their own. A chart
    stands on the activities it draws (538)."""
    if turn.path != MODEL_LED or turn.template is None:
        return []
    if turn.template == CHART:
        return list(turn.args["activities"])
    if turn.template == INVITATION:  # 540: as a chart, on the activity it invites to
        return [turn.args["activity"]]
    opening = core.named_in(run.folder, re.split(r"\s*[;—–]\s*", _first_line(turn))[0])
    return opening if len(opening) == 1 else core.named_in(
        run.folder, turn.text if turn.template == LETTER else render(turn.template, turn.args))


def _remember(state: State, run: _Run, turn: Turn) -> None:
    """What the next turn starts from: his line and what he saw, the focus, and (where an answer
    stood) the artefact with the lines its text cited."""
    state.lines.append(run.line)
    named = [] if run.brief.focus else _stood_on(run, turn)
    state.focus = run.brief.focus or (named[0] if len(named) == 1 else None)
    state.asked = state.asked or run.asked
    # a turn that did not stand (the plain line, 493's question) keeps the next line unasked
    state.several = len(named) > 1 or (state.several and turn.path != MODEL_LED
                                       and state.focus is None)
    said = run.said or turn.text
    state.history += [{"role": "user", "content": f"He typed: {run.line}"},
                      {"role": "assistant", "content": said}]
    for a in turn.artefacts:
        state.shown.append({"id": a["id"], "version": a["version"], "template": a["template"],
                            "arguments": a["arguments"], "focus": state.focus, "cites": [
            (p, n, run.read[(p, n)]) for p, n in dict.fromkeys(checks.cites(said, run.read))
            if (p, n) in run.read]})


def run(folder: Path, line: str, chat: Lane, state: State,
        graph: Callable[[str | None], str] | None = None,
        next_taps: Callable[[], list[tuple[str, dict[str, Any]]]] | None = None,
        clock: Clock | None = None, waiting: Callable[[str], Any] | None = None,
        walking: Walk | None = None) -> Turn:
    """One model-led turn: the brief, the model's reads and template call through 535's stack, one
    send-back with the rest frozen. `chat` is the lane (a fake one in every test); `state` carries
    the conversation and is updated. `graph` draws the graph answer's link for an activity (the
    room's page, from `Session`); `next_taps` is code's taps for a turn that fails or runs out of
    `clock` (537); `waiting` shows `CHECKING` in his reply bubble once the turn passes its mark;
    `walking` hands the walk's tools while the conversation is on one (608)."""
    # the timer's thread starts with an empty context, and the phone's bubble reads chainlit's (182)
    clock = clock or Clock()
    state.walk = walking is not None
    wait = threading.Timer(clock.checking_s, contextvars.copy_context().run,
                           (waiting or (lambda said: None), CHECKING))
    wait.start()
    try:
        turn = (r := _Run(folder, line, chat, state, graph or (lambda a: ""),
                          next_taps or (lambda: []), clock, walking)).go()
    finally:
        wait.cancel()
    _remember(state, r, turn)
    return turn
